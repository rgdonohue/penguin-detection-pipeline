#!/usr/bin/env python3
"""HAG histogram analysis for data-driven threshold selection.

For a given tile:
1. Build ground DEM (configurable method)
2. Compute full HAG grid
3. Extract all HAG values > 0 (above-ground)
4. Compute histogram (0.01 m bins from 0 to 2.0 m)
5. Smooth with Gaussian kernel, find peaks via scipy.signal.find_peaks()
6. Plot histogram with current threshold band overlaid, peaks marked
7. Output JSON: bin edges, counts, detected peaks with heights, suggested threshold range

Usage:
    python scripts/experiments/hag_histogram.py \
        --tile "data/2025/Caleta Tiny Island/cloud0.las" \
        --out data/interim/hag_histogram.json \
        --plot data/interim/hag_histogram.png \
        --crs-epsg 32720
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.signal import find_peaks

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT / "scripts"), str(ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import run_lidar_hag as lidar


def _compute_hag_histogram(
    las_path: Path,
    cell_res: float,
    chunk_size: int,
    ground_method: str = "min",
    bin_width: float = 0.01,
    max_hag: float = 2.0,
    smooth_sigma: float = 3.0,
    peak_prominence: float = 0.003,
) -> dict:
    """Compute HAG histogram and detect peaks."""
    mins, maxs, npts = lidar.read_bounds_and_counts(las_path, chunk_size)
    ny, nx = lidar._grid_shape(mins, maxs, cell_res)

    dem, meta = lidar.build_ground_dem(
        las_path, cell_res, chunk_size, verbose=False,
        ground_method=ground_method, bounds=(mins, maxs),
    )
    hag = lidar.build_hag_grid(las_path, dem, meta, chunk_size, top_method="max")

    # Extract all above-ground values
    hag_flat = hag.ravel()
    above_ground = hag_flat[hag_flat > 0]

    # Histogram
    bin_edges = np.arange(0, max_hag + bin_width, bin_width)
    counts, edges = np.histogram(above_ground, bins=bin_edges)
    bin_centers = (edges[:-1] + edges[1:]) / 2

    # Normalize to density
    total = counts.sum()
    density = counts / max(total, 1)

    # Smooth for peak detection
    smoothed = ndimage.gaussian_filter1d(density.astype(float), sigma=smooth_sigma)

    # Find peaks
    peaks_idx, properties = find_peaks(
        smoothed,
        prominence=peak_prominence,
        distance=int(0.05 / bin_width),  # min 5cm between peaks
    )

    peaks = []
    for idx in peaks_idx:
        peaks.append({
            "hag_m": round(float(bin_centers[idx]), 3),
            "density": round(float(smoothed[idx]), 6),
            "prominence": round(float(properties["prominences"][list(peaks_idx).index(idx)]), 6),
        })

    # Sort peaks by prominence
    peaks.sort(key=lambda p: p["prominence"], reverse=True)

    # Suggest threshold range based on peaks
    suggested_range = None
    penguin_peaks = [p for p in peaks if 0.15 <= p["hag_m"] <= 0.70]
    if penguin_peaks:
        primary = penguin_peaks[0]
        # Suggest range centered on the most prominent peak in penguin range
        center = primary["hag_m"]
        suggested_range = {
            "hag_min": round(max(0.1, center - 0.15), 2),
            "hag_max": round(min(1.0, center + 0.15), 2),
            "center_peak": center,
            "note": f"Centered on most prominent peak at {center:.3f} m",
        }

    return {
        "tile": str(las_path),
        "grid_shape": [ny, nx],
        "total_above_ground_cells": int(above_ground.size),
        "total_cells": int(hag_flat.size),
        "pct_above_ground": round(100.0 * above_ground.size / max(hag_flat.size, 1), 2),
        "hag_stats": {
            "mean": round(float(np.mean(above_ground)), 4) if above_ground.size else None,
            "median": round(float(np.median(above_ground)), 4) if above_ground.size else None,
            "std": round(float(np.std(above_ground)), 4) if above_ground.size else None,
            "p25": round(float(np.percentile(above_ground, 25)), 4) if above_ground.size else None,
            "p75": round(float(np.percentile(above_ground, 75)), 4) if above_ground.size else None,
            "p95": round(float(np.percentile(above_ground, 95)), 4) if above_ground.size else None,
            "max": round(float(np.max(above_ground)), 4) if above_ground.size else None,
        },
        "histogram": {
            "bin_edges": [round(float(e), 3) for e in edges.tolist()],
            "counts": counts.tolist(),
            "bin_width": bin_width,
        },
        "peaks": peaks,
        "suggested_threshold_range": suggested_range,
        "ground_method": ground_method,
        "cell_res": cell_res,
        # Store for plotting (not serialized)
        "_bin_centers": bin_centers,
        "_density": density,
        "_smoothed": smoothed,
        "_peaks_idx": peaks_idx,
    }


def _save_plot(
    result: dict,
    out_png: Path,
    hag_min: float = 0.28,
    hag_max: float = 0.48,
) -> None:
    """Save histogram plot with threshold band and peaks."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("WARNING: matplotlib not available; skipping plot", file=sys.stderr)
        return

    bin_centers = result.get("_bin_centers")
    density = result.get("_density")
    smoothed = result.get("_smoothed")
    peaks_idx = result.get("_peaks_idx")

    if bin_centers is None:
        return

    fig, ax = plt.subplots(figsize=(12, 6))

    # Raw histogram
    ax.bar(bin_centers, density, width=result["histogram"]["bin_width"],
           alpha=0.4, color="steelblue", label="HAG density")

    # Smoothed curve
    ax.plot(bin_centers, smoothed, color="navy", linewidth=1.5, label="Smoothed")

    # Current threshold band
    ax.axvspan(hag_min, hag_max, alpha=0.2, color="orange",
               label=f"Current threshold [{hag_min}–{hag_max}] m")

    # Peaks
    if peaks_idx is not None and len(peaks_idx) > 0:
        ax.plot(bin_centers[peaks_idx], smoothed[peaks_idx],
                "rv", markersize=10, label="Detected peaks")
        for idx in peaks_idx:
            ax.annotate(
                f"{bin_centers[idx]:.3f} m",
                xy=(bin_centers[idx], smoothed[idx]),
                xytext=(5, 10), textcoords="offset points",
                fontsize=8, color="red",
            )

    ax.set_xlabel("Height Above Ground (m)")
    ax.set_ylabel("Density (normalized)")
    ax.set_title(f"HAG Distribution — {Path(result['tile']).name}")
    ax.set_xlim(0, 1.5)
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="HAG histogram analysis")
    parser.add_argument("--tile", required=True, help="Path to LAS/LAZ tile")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--plot", default=None, help="Output PNG path")
    parser.add_argument("--crs-epsg", type=int, default=32720)
    parser.add_argument("--cell-res", type=float, default=0.25)
    parser.add_argument("--ground-method", default="min", choices=["min", "p05"])
    parser.add_argument("--hag-min", type=float, default=0.28, help="Current threshold min (for overlay)")
    parser.add_argument("--hag-max", type=float, default=0.48, help="Current threshold max (for overlay)")
    parser.add_argument("--bin-width", type=float, default=0.01)
    parser.add_argument("--max-hag", type=float, default=2.0)
    parser.add_argument("--smooth-sigma", type=float, default=3.0)
    parser.add_argument("--chunk-size", type=int, default=1_000_000)
    args = parser.parse_args()

    tile_path = Path(args.tile).resolve()
    if not tile_path.exists():
        raise SystemExit(f"Tile not found: {tile_path}")

    print(f"Analyzing HAG distribution for {tile_path.name} ...", flush=True)
    result = _compute_hag_histogram(
        tile_path,
        cell_res=args.cell_res,
        chunk_size=args.chunk_size,
        ground_method=args.ground_method,
        bin_width=args.bin_width,
        max_hag=args.max_hag,
        smooth_sigma=args.smooth_sigma,
    )

    print(f"  {result['total_above_ground_cells']} above-ground cells "
          f"({result['pct_above_ground']:.1f}% of grid)")
    print(f"  {len(result['peaks'])} peaks detected:")
    for p in result["peaks"][:5]:
        print(f"    {p['hag_m']:.3f} m (prominence: {p['prominence']:.4f})")

    if result["suggested_threshold_range"]:
        sr = result["suggested_threshold_range"]
        print(f"  Suggested range: [{sr['hag_min']}–{sr['hag_max']}] m "
              f"(centered on {sr['center_peak']:.3f} m)")

    # Save plot
    plot_path = Path(args.plot) if args.plot else Path(args.out).with_suffix(".png")
    _save_plot(result, plot_path, hag_min=args.hag_min, hag_max=args.hag_max)
    print(f"Plot saved: {plot_path}")

    # Serialize (strip numpy arrays)
    serializable = {k: v for k, v in result.items() if not k.startswith("_")}
    serializable["crs_epsg"] = args.crs_epsg

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(serializable, indent=2))
    print(f"Results saved: {out_path}")


if __name__ == "__main__":
    main()
