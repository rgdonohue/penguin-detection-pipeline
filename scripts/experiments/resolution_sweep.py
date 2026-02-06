#!/usr/bin/env python3
"""Resolution sweep experiment — test detection at varying cell sizes.

For each test tile, runs detection at cell sizes [0.10, 0.15, 0.20, 0.25, 0.30] m.
Collects per-resolution: detection count, mean points per cell, % empty cells,
% single-cell blobs, mean blob area, grid dimensions, memory usage, runtime.

Self-contained density computation (does not depend on --density-stats flag).

Usage:
    python scripts/experiments/resolution_sweep.py \
        --tile "data/2025/Caleta Tiny Island/cloud0.las" \
        --out data/interim/resolution_sweep.json \
        --crs-epsg 32720
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT / "scripts"), str(ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import run_lidar_hag as lidar

DEFAULT_RESOLUTIONS = [0.10, 0.15, 0.20, 0.25, 0.30]


def _run_at_resolution(
    las_path: Path,
    cell_res: float,
    hag_min: float,
    hag_max: float,
    min_area_cells: int,
    max_area_cells: int,
    chunk_size: int,
    ground_method: str = "min",
) -> dict:
    """Run detection at a specific cell resolution and return stats."""
    t0 = time.time()

    mins, maxs, npts = lidar.read_bounds_and_counts(las_path, chunk_size)
    ny, nx = lidar._grid_shape(mins, maxs, cell_res)
    n_cells = ny * nx

    # Memory estimate
    est_bytes = lidar._estimate_grid_bytes(ny, nx, ground_method, "max", None, density_stats=True)
    est_mb = est_bytes / (1024 ** 2)

    # Build DEM with count grid for density stats
    count_grid = np.zeros((ny, nx), dtype=np.int32)
    dem, meta = lidar.build_ground_dem(
        las_path, cell_res, chunk_size, verbose=False,
        ground_method=ground_method, bounds=(mins, maxs),
        count_grid=count_grid,
    )

    # Density stats
    total_points = int(np.sum(count_grid))
    empty_cells = int(np.sum(count_grid == 0))
    occupied = count_grid[count_grid > 0]
    mean_pts_per_cell = float(np.mean(count_grid)) if n_cells > 0 else 0.0
    pct_empty = 100.0 * empty_cells / max(n_cells, 1)

    # HAG and detection
    hag = lidar.build_hag_grid(las_path, dem, meta, chunk_size, top_method="max")
    count, labeled, dets, _ = lidar.detect_penguins_from_hag(
        hag, hag_min, hag_max, min_area_cells, max_area_cells,
        connectivity=2, cell_res=cell_res, mins=np.array(meta["mins"]),
    )

    dt = time.time() - t0

    # Blob stats
    areas = [d["area_cells"] for d in dets]
    single_cell_blobs = sum(1 for a in areas if a == 1)
    pct_single_cell = 100.0 * single_cell_blobs / max(len(areas), 1) if areas else 0.0
    mean_area_cells = float(np.mean(areas)) if areas else 0.0
    mean_area_m2 = mean_area_cells * (cell_res ** 2)

    return {
        "cell_res": cell_res,
        "grid_shape": [ny, nx],
        "n_cells": n_cells,
        "detection_count": count,
        "runtime_s": round(dt, 2),
        "memory_est_mb": round(est_mb, 1),
        "density": {
            "total_points": total_points,
            "mean_pts_per_cell": round(mean_pts_per_cell, 2),
            "pct_empty_cells": round(pct_empty, 2),
            "mean_pts_per_occupied_cell": round(float(np.mean(occupied)), 2) if occupied.size > 0 else 0.0,
        },
        "blob_stats": {
            "n_single_cell": single_cell_blobs,
            "pct_single_cell": round(pct_single_cell, 1),
            "mean_area_cells": round(mean_area_cells, 2),
            "mean_area_m2": round(mean_area_m2, 4),
        },
    }


def _save_plots(results: list[dict], out_png: Path) -> None:
    """Save line plots: count vs resolution, pts/cell vs resolution, empty% vs resolution."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("WARNING: matplotlib not available; skipping plot", file=sys.stderr)
        return

    resolutions = [r["cell_res"] for r in results]
    counts = [r["detection_count"] for r in results]
    pts_per_cell = [r["density"]["mean_pts_per_cell"] for r in results]
    pct_empty = [r["density"]["pct_empty_cells"] for r in results]
    pct_single = [r["blob_stats"]["pct_single_cell"] for r in results]

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    axes[0, 0].plot(resolutions, counts, "bo-")
    axes[0, 0].set_xlabel("Cell resolution (m)")
    axes[0, 0].set_ylabel("Detection count")
    axes[0, 0].set_title("Detection Count vs Resolution")
    axes[0, 0].grid(True, alpha=0.3)

    axes[0, 1].plot(resolutions, pts_per_cell, "go-")
    axes[0, 1].set_xlabel("Cell resolution (m)")
    axes[0, 1].set_ylabel("Mean points per cell")
    axes[0, 1].set_title("Point Density vs Resolution")
    axes[0, 1].grid(True, alpha=0.3)

    axes[1, 0].plot(resolutions, pct_empty, "ro-")
    axes[1, 0].set_xlabel("Cell resolution (m)")
    axes[1, 0].set_ylabel("% empty cells")
    axes[1, 0].set_title("Empty Cells vs Resolution")
    axes[1, 0].grid(True, alpha=0.3)

    axes[1, 1].plot(resolutions, pct_single, "mo-")
    axes[1, 1].set_xlabel("Cell resolution (m)")
    axes[1, 1].set_ylabel("% single-cell blobs")
    axes[1, 1].set_title("Single-Cell Blobs (Nyquist proxy)")
    axes[1, 1].grid(True, alpha=0.3)

    fig.suptitle("Resolution Sweep", fontsize=14, fontweight="bold")
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Resolution sweep experiment")
    parser.add_argument("--tile", required=True, help="Path to LAS/LAZ tile")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--plot", default=None, help="Output PNG path")
    parser.add_argument("--crs-epsg", type=int, default=32720)
    parser.add_argument("--resolutions", type=float, nargs="+", default=DEFAULT_RESOLUTIONS,
                        help="Cell resolutions to test (meters)")
    parser.add_argument("--hag-min", type=float, default=0.28)
    parser.add_argument("--hag-max", type=float, default=0.48)
    parser.add_argument("--min-area-cells", type=int, default=3)
    parser.add_argument("--max-area-cells", type=int, default=60)
    parser.add_argument("--chunk-size", type=int, default=1_000_000)
    parser.add_argument("--ground-method", default="min", choices=["min", "p05"])
    args = parser.parse_args()

    tile_path = Path(args.tile).resolve()
    if not tile_path.exists():
        raise SystemExit(f"Tile not found: {tile_path}")

    results = []
    for res in sorted(args.resolutions):
        print(f"Resolution {res:.2f} m ...", end=" ", flush=True)
        r = _run_at_resolution(
            tile_path, cell_res=res,
            hag_min=args.hag_min, hag_max=args.hag_max,
            min_area_cells=args.min_area_cells,
            max_area_cells=args.max_area_cells,
            chunk_size=args.chunk_size,
            ground_method=args.ground_method,
        )
        print(f"{r['detection_count']} detections, "
              f"{r['density']['mean_pts_per_cell']:.1f} pts/cell, "
              f"{r['density']['pct_empty_cells']:.0f}% empty, "
              f"{r['runtime_s']}s", flush=True)
        results.append(r)

    # Save plot
    plot_path = Path(args.plot) if args.plot else Path(args.out).with_suffix(".png")
    _save_plots(results, plot_path)
    print(f"Plot saved: {plot_path}")

    output = {
        "tile": str(tile_path),
        "crs_epsg": args.crs_epsg,
        "hag_range": [args.hag_min, args.hag_max],
        "area_range": [args.min_area_cells, args.max_area_cells],
        "ground_method": args.ground_method,
        "resolutions": results,
    }

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Results saved: {out_path}")


if __name__ == "__main__":
    main()
