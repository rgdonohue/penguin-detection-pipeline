#!/usr/bin/env python3
"""
DTM Quality Diagnostics — Penguin Detection Pipeline

Analyzes Digital Terrain Model (DTM) quality to identify problematic areas
that may affect HAG-based penguin detection. Outputs:
- Point count per cell (support analysis)
- Local roughness (terrain noise indicator)
- Empty cell percentage (coverage gaps)
- DTM statistics and histograms

Usage:
    python scripts/analyze_dtm_quality.py \
        --las-file data/2025/Caleta\ Tiny\ Island/tile_001.las \
        --out data/interim/dtm_quality.json \
        --cell-res 0.25 \
        --plots
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Add project root to path
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[1]
for p in [str(_ROOT / "src"), str(_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Import LiDAR utilities from the main pipeline
try:
    from scripts.run_lidar_hag import (
        read_bounds_and_counts,
        _grid_shape,
        _stream_points,
        _bin_indices,
        build_ground_dem,
        LASPY_AVAILABLE,
    )
except ImportError as e:
    print(f"ERROR: Could not import from run_lidar_hag.py: {e}", file=sys.stderr)
    sys.exit(1)

# Optional plotting
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def compute_point_count_grid(
    las_path: Path,
    cell_res: float,
    chunk_size: int,
    bounds: Optional[Tuple[np.ndarray, np.ndarray]] = None,
) -> Tuple[np.ndarray, Dict]:
    """Build a grid of point counts per cell.

    Returns (count_grid, metadata) where count_grid[y, x] is the number of
    LiDAR points falling in that cell.
    """
    if bounds is None:
        mins, maxs, _ = read_bounds_and_counts(las_path, chunk_size)
    else:
        mins, maxs = bounds
        mins = np.array(mins, dtype=float)
        maxs = np.array(maxs, dtype=float)

    ny, nx = _grid_shape(mins, maxs, cell_res)
    count_grid = np.zeros((ny, nx), dtype=np.int32)

    for x, y, z in _stream_points(las_path, chunk_size):
        ix, iy, mask = _bin_indices(x, y, mins, cell_res, ny, nx)
        flat = (iy * nx + ix)
        if flat.size:
            np.add.at(count_grid.ravel(), flat, 1)

    meta = {
        "mins": mins.tolist(),
        "maxs": maxs.tolist(),
        "cell_res": cell_res,
        "shape": [int(ny), int(nx)],
    }
    return count_grid, meta


from pipelines.dtm_quality import compute_local_roughness  # noqa: E402


def _compute_local_roughness(dem: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    """Wrapper for backwards compatibility — delegates to pipelines.dtm_quality."""
    return compute_local_roughness(dem, kernel_size=kernel_size)


def analyze_dtm_quality(
    las_path: Path,
    cell_res: float,
    chunk_size: int,
    ground_method: str = "p05",
    roughness_kernel: int = 3,
    verbose: bool = False,
) -> Dict:
    """Run full DTM quality analysis on a LAS file.

    Returns a dict with:
    - point_stats: min/max/mean/median point counts per cell
    - empty_cell_stats: count and percentage of empty cells
    - roughness_stats: min/max/mean/percentiles of local roughness
    - dem_stats: elevation statistics
    - grids: numpy arrays (optional, not serialized to JSON)
    """
    if verbose:
        print(f"Analyzing DTM quality for {las_path.name}...", flush=True)

    # Get bounds first
    mins, maxs, total_points = read_bounds_and_counts(las_path, chunk_size)
    bounds = (mins, maxs)
    ny, nx = _grid_shape(mins, maxs, cell_res)

    if verbose:
        print(f"  Grid: {ny}x{nx} cells at {cell_res}m resolution", flush=True)
        print(f"  Total points: {total_points:,}", flush=True)

    # Build point count grid
    count_grid, _ = compute_point_count_grid(las_path, cell_res, chunk_size, bounds)

    # Build DEM
    dem, dem_meta = build_ground_dem(
        las_path, cell_res, chunk_size, verbose=False,
        ground_method=ground_method,
        bounds=bounds,
    )

    # Compute local roughness
    roughness = compute_local_roughness(dem, kernel_size=roughness_kernel)

    # Compute statistics
    n_cells = int(ny * nx)
    empty_cells = int(np.sum(count_grid == 0))
    occupied_cells = count_grid[count_grid > 0]

    # Point count statistics
    point_stats = {
        "total_points": int(total_points),
        "n_cells": n_cells,
        "cells_with_data": int(n_cells - empty_cells),
        "empty_cells": empty_cells,
        "pct_empty": round(100.0 * empty_cells / max(n_cells, 1), 2),
        "min_pts_per_cell": int(np.min(count_grid)),
        "max_pts_per_cell": int(np.max(count_grid)),
        "mean_pts_per_cell": round(float(np.mean(count_grid)), 2),
        "median_pts_per_cell": round(float(np.median(count_grid)), 2),
    }
    if occupied_cells.size > 0:
        point_stats["mean_pts_per_occupied_cell"] = round(float(np.mean(occupied_cells)), 2)
        point_stats["median_pts_per_occupied_cell"] = round(float(np.median(occupied_cells)), 2)
        point_stats["p05_pts_per_occupied_cell"] = round(float(np.percentile(occupied_cells, 5)), 2)
        point_stats["p95_pts_per_occupied_cell"] = round(float(np.percentile(occupied_cells, 95)), 2)

    # Roughness statistics
    finite_roughness = roughness[np.isfinite(roughness)]
    roughness_stats = {
        "kernel_size": roughness_kernel,
        "min": round(float(np.min(finite_roughness)), 4) if finite_roughness.size > 0 else None,
        "max": round(float(np.max(finite_roughness)), 4) if finite_roughness.size > 0 else None,
        "mean": round(float(np.mean(finite_roughness)), 4) if finite_roughness.size > 0 else None,
        "median": round(float(np.median(finite_roughness)), 4) if finite_roughness.size > 0 else None,
        "p90": round(float(np.percentile(finite_roughness, 90)), 4) if finite_roughness.size > 0 else None,
        "p95": round(float(np.percentile(finite_roughness, 95)), 4) if finite_roughness.size > 0 else None,
        "p99": round(float(np.percentile(finite_roughness, 99)), 4) if finite_roughness.size > 0 else None,
    }

    # DEM elevation statistics
    finite_dem = dem[np.isfinite(dem)]
    dem_stats = {
        "min_z": round(float(np.min(finite_dem)), 3) if finite_dem.size > 0 else None,
        "max_z": round(float(np.max(finite_dem)), 3) if finite_dem.size > 0 else None,
        "mean_z": round(float(np.mean(finite_dem)), 3) if finite_dem.size > 0 else None,
        "range_z": round(float(np.ptp(finite_dem)), 3) if finite_dem.size > 0 else None,
    }

    # Quality indicators
    quality_flags = []
    if point_stats["pct_empty"] > 20:
        quality_flags.append(f"HIGH_EMPTY_CELLS: {point_stats['pct_empty']:.1f}% cells have no points")
    if occupied_cells.size > 0 and np.median(occupied_cells) < 3:
        quality_flags.append(f"LOW_SUPPORT: median {np.median(occupied_cells):.0f} points/cell")
    if roughness_stats["p95"] is not None and roughness_stats["p95"] > 0.1:
        quality_flags.append(f"HIGH_ROUGHNESS: p95 roughness = {roughness_stats['p95']:.3f}m")

    return {
        "file": str(las_path),
        "cell_res": cell_res,
        "ground_method": ground_method,
        "grid_shape": [int(ny), int(nx)],
        "point_stats": point_stats,
        "roughness_stats": roughness_stats,
        "dem_stats": dem_stats,
        "quality_flags": quality_flags,
        "grids": {  # Not serialized to JSON, used for plotting
            "count": count_grid,
            "dem": dem,
            "roughness": roughness,
        },
    }


def save_plots(
    analysis: Dict,
    out_dir: Path,
    prefix: str = "dtm_quality",
) -> List[str]:
    """Generate and save DTM quality diagnostic plots."""
    if not MATPLOTLIB_AVAILABLE:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []

    grids = analysis.get("grids", {})
    count_grid = grids.get("count")
    dem = grids.get("dem")
    roughness = grids.get("roughness")

    # Figure 1: Point count heatmap
    if count_grid is not None:
        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(count_grid, origin='lower', cmap='viridis',
                       norm=plt.matplotlib.colors.LogNorm(vmin=max(1, count_grid.min()), vmax=max(1, count_grid.max())))
        ax.set_title(f"Point Count per Cell\n{analysis['file']}")
        ax.set_xlabel("X cell index")
        ax.set_ylabel("Y cell index")
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("Points per cell (log scale)")

        # Add statistics panel
        ps = analysis["point_stats"]
        panel = (
            f"Total: {ps['total_points']:,} points\n"
            f"Empty: {ps['pct_empty']:.1f}% cells\n"
            f"Mean: {ps['mean_pts_per_cell']:.1f} pts/cell"
        )
        ax.text(0.02, 0.98, panel, transform=ax.transAxes, fontsize=9,
                va='top', ha='left', color='white',
                bbox=dict(facecolor='black', alpha=0.7, boxstyle='round,pad=0.3'))

        path = out_dir / f"{prefix}_point_count.png"
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(str(path))

    # Figure 2: DEM with roughness overlay
    if dem is not None and roughness is not None:
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # DEM
        ax = axes[0]
        finite_dem = dem[np.isfinite(dem)]
        vmin = float(np.percentile(finite_dem, 1)) if finite_dem.size > 0 else 0
        vmax = float(np.percentile(finite_dem, 99)) if finite_dem.size > 0 else 1
        im = ax.imshow(dem, origin='lower', cmap='terrain', vmin=vmin, vmax=vmax)
        ax.set_title(f"Ground DEM ({analysis['ground_method']})")
        fig.colorbar(im, ax=ax, label="Elevation (m)")

        # Roughness
        ax = axes[1]
        finite_rough = roughness[np.isfinite(roughness)]
        vmax_r = float(np.percentile(finite_rough, 99)) if finite_rough.size > 0 else 1
        im = ax.imshow(roughness, origin='lower', cmap='hot', vmin=0, vmax=vmax_r)
        ax.set_title(f"Local Roughness (kernel={analysis['roughness_stats']['kernel_size']})")
        fig.colorbar(im, ax=ax, label="Roughness (m)")

        path = out_dir / f"{prefix}_dem_roughness.png"
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(str(path))

    # Figure 3: Histograms
    if count_grid is not None and roughness is not None:
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Point count histogram
        ax = axes[0]
        occupied = count_grid[count_grid > 0].flatten()
        if occupied.size > 0:
            ax.hist(occupied, bins=50, color='steelblue', edgecolor='white', alpha=0.7)
            ax.axvline(np.median(occupied), color='red', linestyle='--', label=f'Median: {np.median(occupied):.0f}')
            ax.legend()
        ax.set_xlabel("Points per cell")
        ax.set_ylabel("Frequency")
        ax.set_title("Point Count Distribution (occupied cells)")

        # Roughness histogram
        ax = axes[1]
        finite_rough = roughness[np.isfinite(roughness)].flatten()
        if finite_rough.size > 0:
            ax.hist(finite_rough, bins=50, color='coral', edgecolor='white', alpha=0.7)
            ax.axvline(np.percentile(finite_rough, 95), color='red', linestyle='--',
                      label=f'P95: {np.percentile(finite_rough, 95):.3f}m')
            ax.legend()
        ax.set_xlabel("Roughness (m)")
        ax.set_ylabel("Frequency")
        ax.set_title("Local Roughness Distribution")

        path = out_dir / f"{prefix}_histograms.png"
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(str(path))

    return saved


def main():
    parser = argparse.ArgumentParser(
        description="Analyze DTM quality for LiDAR-based penguin detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--las-file", required=True, help="Input LAS/LAZ file")
    parser.add_argument("--out", default="dtm_quality.json", help="Output JSON path")
    parser.add_argument("--cell-res", type=float, default=0.25, help="Cell resolution in meters")
    parser.add_argument("--ground-method", default="p05", choices=["min", "p05"],
                       help="Ground DEM estimator method")
    parser.add_argument("--roughness-kernel", type=int, default=3,
                       help="Kernel size for local roughness computation")
    parser.add_argument("--chunk-size", type=int, default=1000000, help="LAS chunk size")
    parser.add_argument("--plots", action="store_true", help="Generate diagnostic plots")
    parser.add_argument("--plots-dir", default=None, help="Directory for plots (default: <out>_plots)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if not LASPY_AVAILABLE:
        print("ERROR: laspy not available. Install with: pip install laspy", file=sys.stderr)
        sys.exit(1)

    las_path = Path(args.las_file)
    if not las_path.exists():
        print(f"ERROR: File not found: {las_path}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Run analysis
    analysis = analyze_dtm_quality(
        las_path,
        cell_res=args.cell_res,
        chunk_size=args.chunk_size,
        ground_method=args.ground_method,
        roughness_kernel=args.roughness_kernel,
        verbose=args.verbose,
    )

    # Generate plots if requested
    if args.plots:
        plots_dir = Path(args.plots_dir) if args.plots_dir else out_path.parent / f"{out_path.stem}_plots"
        saved_plots = save_plots(analysis, plots_dir, prefix=las_path.stem)
        analysis["plots"] = saved_plots
        if args.verbose:
            print(f"  Saved {len(saved_plots)} plots to {plots_dir}", flush=True)

    # Remove non-serializable grids before JSON output
    analysis_json = {k: v for k, v in analysis.items() if k != "grids"}

    # Write JSON output
    with open(out_path, "w") as f:
        json.dump(analysis_json, f, indent=2)

    # Print summary
    print(json.dumps({
        "file": analysis["file"],
        "cell_res": analysis["cell_res"],
        "pct_empty": analysis["point_stats"]["pct_empty"],
        "mean_pts_per_cell": analysis["point_stats"]["mean_pts_per_cell"],
        "p95_roughness": analysis["roughness_stats"]["p95"],
        "quality_flags": analysis["quality_flags"],
    }, indent=2))


if __name__ == "__main__":
    main()
