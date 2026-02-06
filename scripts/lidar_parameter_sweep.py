#!/usr/bin/env python3
"""
Parameter sensitivity sweep for LiDAR penguin detection.

Runs detection with varying parameter combinations on a single tile to
quantify how thresholds affect counts. Outputs a CSV of results and
generates sensitivity plots.

Usage:
    python scripts/lidar_parameter_sweep.py \
        --las-file "data/2025/Caleta Tiny Island/cloud0.las" \
        --out-dir qc/panels/parameter_sensitivity \
        --verbose

    # Quick sweep on golden AOI
    python scripts/lidar_parameter_sweep.py \
        --las-file data/legacy_ro/penguin-2.0/data/raw/LiDAR/sample/cloud3.las \
        --out-dir qc/panels/parameter_sensitivity
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


# Default sweep ranges
DEFAULT_HAG_MIN_RANGE = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35]
DEFAULT_HAG_MAX_RANGE = [0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
DEFAULT_MIN_AREA_RANGE = [1, 2, 3, 4, 5]
DEFAULT_MAX_AREA_RANGE = [30, 40, 50, 60, 70, 80, 90, 100]


def run_sweep(
    las_path: Path,
    hag_min_range: List[float],
    hag_max_range: List[float],
    min_area_range: List[int],
    max_area_range: List[int],
    cell_res: float = 0.25,
    chunk_size: int = 1_000_000,
    verbose: bool = False,
) -> List[Dict]:
    """Run parameter combinations and return results."""
    # Pre-compute DEM and bounds once
    mins, maxs, npts = read_bounds_and_counts(las_path, chunk_size)
    if verbose:
        print(f"File: {las_path.name} ({npts:,} points)")

    dem, meta = build_ground_dem(las_path, cell_res, chunk_size, verbose=False, bounds=(mins, maxs))

    # 1D sweeps: vary one parameter at a time, hold others at baseline
    baseline = {
        "hag_min": 0.20,
        "hag_max": 0.60,
        "min_area_cells": 2,
        "max_area_cells": 80,
    }

    results: List[Dict] = []
    sweep_id = 0

    # Sweep hag_min
    if verbose:
        print("Sweeping hag_min...")
    for hag_min in hag_min_range:
        if hag_min >= baseline["hag_max"]:
            continue
        hag = build_hag_grid(las_path, dem, meta, chunk_size)
        t0 = time.time()
        count, _, _, _ = detect_penguins_from_hag(
            hag, hag_min, baseline["hag_max"],
            baseline["min_area_cells"], baseline["max_area_cells"],
            cell_res=cell_res, mins=np.array(meta["mins"]),
        )
        dt = time.time() - t0
        results.append({
            "sweep_id": sweep_id,
            "sweep_param": "hag_min",
            "hag_min": hag_min,
            "hag_max": baseline["hag_max"],
            "min_area_cells": baseline["min_area_cells"],
            "max_area_cells": baseline["max_area_cells"],
            "count": count,
            "runtime_s": round(dt, 3),
        })
        sweep_id += 1

    # Sweep hag_max
    if verbose:
        print("Sweeping hag_max...")
    for hag_max in hag_max_range:
        if baseline["hag_min"] >= hag_max:
            continue
        hag = build_hag_grid(las_path, dem, meta, chunk_size)
        t0 = time.time()
        count, _, _, _ = detect_penguins_from_hag(
            hag, baseline["hag_min"], hag_max,
            baseline["min_area_cells"], baseline["max_area_cells"],
            cell_res=cell_res, mins=np.array(meta["mins"]),
        )
        dt = time.time() - t0
        results.append({
            "sweep_id": sweep_id,
            "sweep_param": "hag_max",
            "hag_min": baseline["hag_min"],
            "hag_max": hag_max,
            "min_area_cells": baseline["min_area_cells"],
            "max_area_cells": baseline["max_area_cells"],
            "count": count,
            "runtime_s": round(dt, 3),
        })
        sweep_id += 1

    # Sweep min_area_cells
    if verbose:
        print("Sweeping min_area_cells...")
    hag = build_hag_grid(las_path, dem, meta, chunk_size)
    for min_area in min_area_range:
        if min_area >= baseline["max_area_cells"]:
            continue
        t0 = time.time()
        count, _, _, _ = detect_penguins_from_hag(
            hag, baseline["hag_min"], baseline["hag_max"],
            min_area, baseline["max_area_cells"],
            cell_res=cell_res, mins=np.array(meta["mins"]),
        )
        dt = time.time() - t0
        results.append({
            "sweep_id": sweep_id,
            "sweep_param": "min_area_cells",
            "hag_min": baseline["hag_min"],
            "hag_max": baseline["hag_max"],
            "min_area_cells": min_area,
            "max_area_cells": baseline["max_area_cells"],
            "count": count,
            "runtime_s": round(dt, 3),
        })
        sweep_id += 1

    # Sweep max_area_cells
    if verbose:
        print("Sweeping max_area_cells...")
    for max_area in max_area_range:
        if baseline["min_area_cells"] >= max_area:
            continue
        t0 = time.time()
        count, _, _, _ = detect_penguins_from_hag(
            hag, baseline["hag_min"], baseline["hag_max"],
            baseline["min_area_cells"], max_area,
            cell_res=cell_res, mins=np.array(meta["mins"]),
        )
        dt = time.time() - t0
        results.append({
            "sweep_id": sweep_id,
            "sweep_param": "max_area_cells",
            "hag_min": baseline["hag_min"],
            "hag_max": baseline["hag_max"],
            "min_area_cells": baseline["min_area_cells"],
            "max_area_cells": max_area,
            "count": count,
            "runtime_s": round(dt, 3),
        })
        sweep_id += 1

    # 2D sweep: hag_min x hag_max
    if verbose:
        print("Sweeping hag_min x hag_max (2D)...")
    for hag_min, hag_max in product(hag_min_range, hag_max_range):
        if hag_min >= hag_max:
            continue
        t0 = time.time()
        count, _, _, _ = detect_penguins_from_hag(
            hag, hag_min, hag_max,
            baseline["min_area_cells"], baseline["max_area_cells"],
            cell_res=cell_res, mins=np.array(meta["mins"]),
        )
        dt = time.time() - t0
        results.append({
            "sweep_id": sweep_id,
            "sweep_param": "hag_min_x_hag_max",
            "hag_min": hag_min,
            "hag_max": hag_max,
            "min_area_cells": baseline["min_area_cells"],
            "max_area_cells": baseline["max_area_cells"],
            "count": count,
            "runtime_s": round(dt, 3),
        })
        sweep_id += 1

    return results


def plot_sensitivity(results: List[Dict], out_dir: Path, title_prefix: str = "") -> None:
    """Generate sensitivity plots from sweep results."""
    if not MATPLOTLIB_AVAILABLE:
        print("WARNING: matplotlib not available, skipping plots")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    # 1D plots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    params_1d = ["hag_min", "hag_max", "min_area_cells", "max_area_cells"]
    for ax, param in zip(axes.flat, params_1d):
        subset = [r for r in results if r["sweep_param"] == param]
        if not subset:
            ax.set_title(f"{param} (no data)")
            continue
        x = [r[param] for r in subset]
        y = [r["count"] for r in subset]
        ax.plot(x, y, "o-", linewidth=2, markersize=6)
        ax.set_xlabel(param)
        ax.set_ylabel("Detection Count")
        ax.set_title(f"{title_prefix}{param}")
        ax.grid(True, alpha=0.3)

    fig.suptitle(f"{title_prefix}Parameter Sensitivity (1D)", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_dir / "sensitivity_1d.png", dpi=150)
    plt.close(fig)

    # 2D heatmap: hag_min x hag_max
    subset_2d = [r for r in results if r["sweep_param"] == "hag_min_x_hag_max"]
    if subset_2d:
        hag_mins = sorted(set(r["hag_min"] for r in subset_2d))
        hag_maxs = sorted(set(r["hag_max"] for r in subset_2d))
        grid = np.full((len(hag_mins), len(hag_maxs)), np.nan)
        for r in subset_2d:
            i = hag_mins.index(r["hag_min"])
            j = hag_maxs.index(r["hag_max"])
            grid[i, j] = r["count"]

        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(grid, aspect="auto", origin="lower", cmap="viridis")
        ax.set_xticks(range(len(hag_maxs)))
        ax.set_xticklabels([f"{v:.2f}" for v in hag_maxs], rotation=45)
        ax.set_yticks(range(len(hag_mins)))
        ax.set_yticklabels([f"{v:.2f}" for v in hag_mins])
        ax.set_xlabel("hag_max (m)")
        ax.set_ylabel("hag_min (m)")
        ax.set_title(f"{title_prefix}HAG Window: Detection Count")
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("Detection Count")
        # Annotate cells
        for i in range(len(hag_mins)):
            for j in range(len(hag_maxs)):
                val = grid[i, j]
                if not np.isnan(val):
                    ax.text(j, i, f"{int(val)}", ha="center", va="center",
                            fontsize=7, color="white" if val < np.nanmedian(grid) else "black")
        fig.tight_layout()
        fig.savefig(out_dir / "sensitivity_2d_hag.png", dpi=150)
        plt.close(fig)

    print(f"Sensitivity plots saved to {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LiDAR parameter sensitivity sweep")
    parser.add_argument("--las-file", required=True, help="Single LAS file to sweep on")
    parser.add_argument("--out-dir", default="qc/panels/parameter_sensitivity", help="Output directory")
    parser.add_argument("--cell-res", type=float, default=0.25, help="Cell resolution")
    parser.add_argument("--chunk-size", type=int, default=1_000_000, help="Chunk size")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    las_path = Path(args.las_file).resolve()
    if not las_path.exists():
        raise SystemExit(f"LAS file not found: {las_path}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = run_sweep(
        las_path,
        hag_min_range=DEFAULT_HAG_MIN_RANGE,
        hag_max_range=DEFAULT_HAG_MAX_RANGE,
        min_area_range=DEFAULT_MIN_AREA_RANGE,
        max_area_range=DEFAULT_MAX_AREA_RANGE,
        cell_res=args.cell_res,
        chunk_size=args.chunk_size,
        verbose=args.verbose,
    )

    # Write CSV
    csv_path = out_dir / "sweep_results.csv"
    fieldnames = ["sweep_id", "sweep_param", "hag_min", "hag_max",
                  "min_area_cells", "max_area_cells", "count", "runtime_s"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"Sweep results: {csv_path} ({len(results)} combinations)")

    # Summary
    counts = [r["count"] for r in results]
    print(f"Detection count range: [{min(counts)}, {max(counts)}]")

    # Plot
    title_prefix = f"{las_path.stem}: "
    plot_sensitivity(results, out_dir, title_prefix=title_prefix)

    # Write JSON summary
    json_path = out_dir / "sweep_summary.json"
    json_path.write_text(json.dumps({
        "file": str(las_path),
        "n_combinations": len(results),
        "count_range": [min(counts), max(counts)],
        "total_runtime_s": round(sum(r["runtime_s"] for r in results), 2),
    }, indent=2))


if __name__ == "__main__":
    main()
