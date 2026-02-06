#!/usr/bin/env python3
"""
Watershed parameter sensitivity sweep for LiDAR penguin detection.

Evaluates watershed splitting parameters to optimize instance separation
in dense colonies. Sweeps h_maxima_h and min_split_area_cells to find
combinations that improve split rates without reducing precision.

Usage:
    python scripts/watershed_parameter_sweep.py \
        --las-file "data/2025/Caleta Tiny Island/cloud0.las" \
        --out-dir qc/panels/watershed_sweep \
        --verbose

    # With labeled data for precision analysis
    python scripts/watershed_parameter_sweep.py \
        --las-file "data/2025/Caleta Tiny Island/cloud0.las" \
        --labels data/labels/caleta_tiny_labels.csv \
        --out-dir qc/panels/watershed_sweep \
        --verbose
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
for p in [str(_ROOT / "src"), str(_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.run_lidar_hag import (
    build_ground_dem,
    build_hag_grid,
    detect_penguins_from_hag,
    read_bounds_and_counts,
)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False


# Default sweep ranges based on evaluation recommendations
DEFAULT_H_MAXIMA_RANGE = [0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
DEFAULT_MIN_SPLIT_AREA_RANGE = [8, 10, 12, 15, 18, 20, 25, 30]

# Baseline detection parameters
DEFAULT_CELL_RES = 0.25
DEFAULT_HAG_MIN = 0.28
DEFAULT_HAG_MAX = 0.48
DEFAULT_MIN_AREA_CELLS = 3
DEFAULT_MAX_AREA_CELLS = 60


def run_watershed_sweep(
    las_path: Path,
    h_maxima_range: List[float],
    min_split_area_range: List[int],
    cell_res: float = DEFAULT_CELL_RES,
    hag_min: float = DEFAULT_HAG_MIN,
    hag_max: float = DEFAULT_HAG_MAX,
    min_area_cells: int = DEFAULT_MIN_AREA_CELLS,
    max_area_cells: int = DEFAULT_MAX_AREA_CELLS,
    chunk_size: int = 1_000_000,
    verbose: bool = False,
) -> List[Dict]:
    """Run watershed parameter combinations and return results.

    Returns a list of dicts with:
    - sweep_id: unique identifier
    - h_maxima_h: h-maxima parameter for seed extraction
    - min_split_area_cells: minimum blob area to attempt split
    - count_baseline: detection count without watershed
    - count_watershed: detection count with watershed
    - split_gain: count_watershed - count_baseline
    - split_gain_pct: percentage increase from watershed
    - n_splits: number of blobs that were split
    - runtime_s: detection time
    """
    # Pre-compute DEM and HAG once
    mins, maxs, npts = read_bounds_and_counts(las_path, chunk_size)
    if verbose:
        print(f"File: {las_path.name} ({npts:,} points)")
        print(f"Grid: {cell_res}m cells, HAG window [{hag_min}, {hag_max}]m")

    dem, meta = build_ground_dem(
        las_path, cell_res, chunk_size,
        verbose=False, ground_method="p05",
        bounds=(mins, maxs),
    )
    hag = build_hag_grid(las_path, dem, meta, chunk_size)

    # Baseline detection (no watershed)
    t0 = time.time()
    count_baseline, labeled_baseline, dets_baseline, _ = detect_penguins_from_hag(
        hag, hag_min, hag_max,
        min_area_cells, max_area_cells,
        cell_res=cell_res, mins=np.array(meta["mins"]),
        apply_watershed=False,
    )
    dt_baseline = time.time() - t0
    if verbose:
        print(f"Baseline (no watershed): {count_baseline} detections in {dt_baseline:.2f}s")

    # Identify potentially merged blobs (large blobs that might benefit from splitting)
    large_blob_threshold = min_area_cells * 2.5  # Blobs > 2.5x min are "likely merged"
    baseline_large_blobs = [d for d in dets_baseline if d.get("area_cells", 0) >= large_blob_threshold]
    n_large_blobs = len(baseline_large_blobs)
    if verbose:
        print(f"Large blobs (area >= {large_blob_threshold:.0f} cells): {n_large_blobs}")

    results: List[Dict] = []
    sweep_id = 0

    # Sweep all combinations of h_maxima and min_split_area
    total_combos = len(h_maxima_range) * len(min_split_area_range)
    if verbose:
        print(f"Running {total_combos} parameter combinations...")

    for h_maxima_h, min_split_area in product(h_maxima_range, min_split_area_range):
        t0 = time.time()
        count_ws, labeled_ws, dets_ws, _ = detect_penguins_from_hag(
            hag, hag_min, hag_max,
            min_area_cells, max_area_cells,
            cell_res=cell_res, mins=np.array(meta["mins"]),
            apply_watershed=True,
            h_maxima_h=h_maxima_h,
            min_split_area_cells=min_split_area,
        )
        dt = time.time() - t0

        # Compute split statistics
        split_gain = count_ws - count_baseline
        split_gain_pct = 100.0 * split_gain / max(count_baseline, 1)

        # Estimate number of splits by comparing labeled regions
        # A split increases the max label value
        n_splits_approx = max(0, int(labeled_ws.max()) - int(labeled_baseline.max()))

        results.append({
            "sweep_id": sweep_id,
            "h_maxima_h": h_maxima_h,
            "min_split_area_cells": min_split_area,
            "count_baseline": count_baseline,
            "count_watershed": count_ws,
            "split_gain": split_gain,
            "split_gain_pct": round(split_gain_pct, 2),
            "n_splits_approx": n_splits_approx,
            "n_large_blobs": n_large_blobs,
            "runtime_s": round(dt, 3),
        })
        sweep_id += 1

        if verbose and sweep_id % 10 == 0:
            print(f"  {sweep_id}/{total_combos}: h={h_maxima_h:.2f}, split_area={min_split_area} -> +{split_gain} ({split_gain_pct:.1f}%)")

    return results


def save_results_csv(results: List[Dict], out_path: Path) -> None:
    """Save sweep results to CSV."""
    if not results:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(results[0].keys())
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


def save_results_json(results: List[Dict], out_path: Path, metadata: Dict) -> None:
    """Save sweep results to JSON with metadata."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1",
        "purpose": "watershed_parameter_sweep",
        "metadata": metadata,
        "results": results,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)


def plot_watershed_sensitivity(
    results: List[Dict],
    out_dir: Path,
    title_prefix: str = "",
) -> List[Path]:
    """Generate watershed sensitivity visualizations."""
    if not MATPLOTLIB_AVAILABLE or not results:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []

    # Extract unique parameter values
    h_values = sorted(set(r["h_maxima_h"] for r in results))
    split_area_values = sorted(set(r["min_split_area_cells"] for r in results))

    # Build 2D arrays for heatmaps
    gain_matrix = np.zeros((len(split_area_values), len(h_values)))
    gain_pct_matrix = np.zeros_like(gain_matrix)

    for r in results:
        h_idx = h_values.index(r["h_maxima_h"])
        sa_idx = split_area_values.index(r["min_split_area_cells"])
        gain_matrix[sa_idx, h_idx] = r["split_gain"]
        gain_pct_matrix[sa_idx, h_idx] = r["split_gain_pct"]

    # Figure 1: Split gain heatmap
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    ax = axes[0]
    im = ax.imshow(gain_matrix, cmap='RdYlGn', aspect='auto', origin='lower')
    ax.set_xticks(range(len(h_values)))
    ax.set_xticklabels([f"{h:.2f}" for h in h_values], rotation=45)
    ax.set_yticks(range(len(split_area_values)))
    ax.set_yticklabels(split_area_values)
    ax.set_xlabel("h_maxima_h (m)")
    ax.set_ylabel("min_split_area_cells")
    ax.set_title(f"{title_prefix}Split Gain (absolute)")
    fig.colorbar(im, ax=ax, label="Additional detections")

    # Annotate cells
    for i in range(len(split_area_values)):
        for j in range(len(h_values)):
            val = gain_matrix[i, j]
            color = 'white' if abs(val) > gain_matrix.max() * 0.6 else 'black'
            ax.text(j, i, f"{val:.0f}", ha='center', va='center', fontsize=7, color=color)

    ax = axes[1]
    im = ax.imshow(gain_pct_matrix, cmap='RdYlGn', aspect='auto', origin='lower')
    ax.set_xticks(range(len(h_values)))
    ax.set_xticklabels([f"{h:.2f}" for h in h_values], rotation=45)
    ax.set_yticks(range(len(split_area_values)))
    ax.set_yticklabels(split_area_values)
    ax.set_xlabel("h_maxima_h (m)")
    ax.set_ylabel("min_split_area_cells")
    ax.set_title(f"{title_prefix}Split Gain (%)")
    fig.colorbar(im, ax=ax, label="Percentage increase")

    # Annotate cells
    for i in range(len(split_area_values)):
        for j in range(len(h_values)):
            val = gain_pct_matrix[i, j]
            color = 'white' if abs(val) > gain_pct_matrix.max() * 0.6 else 'black'
            ax.text(j, i, f"{val:.1f}%", ha='center', va='center', fontsize=6, color=color)

    path = out_dir / "watershed_split_gain_heatmap.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    saved.append(path)

    # Figure 2: 1D sensitivity curves
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Sensitivity to h_maxima_h (average across split_area values)
    ax = axes[0]
    avg_gain_by_h = [np.mean([r["split_gain_pct"] for r in results if r["h_maxima_h"] == h]) for h in h_values]
    ax.plot(h_values, avg_gain_by_h, marker='o', linewidth=2, color='steelblue')
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel("h_maxima_h (m)")
    ax.set_ylabel("Average Split Gain (%)")
    ax.set_title("Sensitivity to h_maxima_h")
    ax.grid(True, alpha=0.3)

    # Sensitivity to min_split_area_cells
    ax = axes[1]
    avg_gain_by_sa = [np.mean([r["split_gain_pct"] for r in results if r["min_split_area_cells"] == sa]) for sa in split_area_values]
    ax.plot(split_area_values, avg_gain_by_sa, marker='s', linewidth=2, color='coral')
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel("min_split_area_cells")
    ax.set_ylabel("Average Split Gain (%)")
    ax.set_title("Sensitivity to min_split_area_cells")
    ax.grid(True, alpha=0.3)

    path = out_dir / "watershed_sensitivity_curves.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    saved.append(path)

    return saved


def find_optimal_parameters(results: List[Dict]) -> Dict:
    """Find parameters that maximize split gain without over-splitting.

    Heuristic: prefer moderate gains (5-15%) over extreme values,
    as very high gains may indicate false splits.
    """
    if not results:
        return {}

    # Filter for reasonable gain range
    reasonable = [r for r in results if 0 < r["split_gain_pct"] < 25]
    if not reasonable:
        reasonable = results

    # Sort by split gain percentage (target ~5-15%)
    # Penalize values too far from 10% target
    def score(r):
        pct = r["split_gain_pct"]
        if pct <= 0:
            return -1000
        # Favor ~10% gain, penalize extremes
        target = 10.0
        return -abs(pct - target)

    sorted_results = sorted(reasonable, key=score, reverse=True)
    best = sorted_results[0]

    return {
        "recommended_h_maxima_h": best["h_maxima_h"],
        "recommended_min_split_area_cells": best["min_split_area_cells"],
        "expected_gain_pct": best["split_gain_pct"],
        "expected_additional_detections": best["split_gain"],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Watershed parameter sensitivity sweep for LiDAR penguin detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--las-file", required=True, help="Input LAS/LAZ file")
    parser.add_argument("--out-dir", default="qc/panels/watershed_sweep", help="Output directory")

    # Detection parameters
    parser.add_argument("--cell-res", type=float, default=DEFAULT_CELL_RES, help="Cell resolution (m)")
    parser.add_argument("--hag-min", type=float, default=DEFAULT_HAG_MIN, help="Min HAG threshold (m)")
    parser.add_argument("--hag-max", type=float, default=DEFAULT_HAG_MAX, help="Max HAG threshold (m)")
    parser.add_argument("--min-area-cells", type=int, default=DEFAULT_MIN_AREA_CELLS, help="Min blob area (cells)")
    parser.add_argument("--max-area-cells", type=int, default=DEFAULT_MAX_AREA_CELLS, help="Max blob area (cells)")

    # Sweep ranges
    parser.add_argument("--h-maxima-range", type=float, nargs="+", default=DEFAULT_H_MAXIMA_RANGE,
                       help="h_maxima_h values to sweep")
    parser.add_argument("--min-split-area-range", type=int, nargs="+", default=DEFAULT_MIN_SPLIT_AREA_RANGE,
                       help="min_split_area_cells values to sweep")

    parser.add_argument("--chunk-size", type=int, default=1_000_000, help="LAS chunk size")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    las_path = Path(args.las_file)
    if not las_path.exists():
        print(f"ERROR: File not found: {las_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Run sweep
    results = run_watershed_sweep(
        las_path,
        h_maxima_range=args.h_maxima_range,
        min_split_area_range=args.min_split_area_range,
        cell_res=args.cell_res,
        hag_min=args.hag_min,
        hag_max=args.hag_max,
        min_area_cells=args.min_area_cells,
        max_area_cells=args.max_area_cells,
        chunk_size=args.chunk_size,
        verbose=args.verbose,
    )

    # Save results
    csv_path = out_dir / "watershed_sweep_results.csv"
    save_results_csv(results, csv_path)

    # Find optimal parameters
    optimal = find_optimal_parameters(results)

    json_path = out_dir / "watershed_sweep_results.json"
    save_results_json(results, json_path, metadata={
        "las_file": str(las_path),
        "cell_res": args.cell_res,
        "hag_min": args.hag_min,
        "hag_max": args.hag_max,
        "min_area_cells": args.min_area_cells,
        "max_area_cells": args.max_area_cells,
        "optimal": optimal,
    })

    # Generate plots
    if MATPLOTLIB_AVAILABLE:
        title_prefix = f"{las_path.stem}: "
        plots = plot_watershed_sensitivity(results, out_dir, title_prefix)
        if args.verbose and plots:
            print(f"Saved {len(plots)} plots to {out_dir}")

    # Print summary
    print(json.dumps({
        "file": str(las_path),
        "n_combinations": len(results),
        "optimal": optimal,
        "csv_output": str(csv_path),
    }, indent=2))


if __name__ == "__main__":
    main()
