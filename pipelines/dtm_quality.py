"""
DTM quality metrics for LiDAR-based penguin detection.

Core library functions extracted from scripts/analyze_dtm_quality.py.
Provides compute_local_roughness() and compute_dtm_quality_metrics()
for integration into the main pipeline via --emit-dtm-quality.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np


def compute_local_roughness(dem: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    """Compute local roughness as std dev of DEM in a neighborhood.

    Roughness indicates terrain noise / irregularity that may affect HAG quality.
    """
    from scipy.ndimage import generic_filter

    def local_std(values):
        return np.std(values)

    roughness = generic_filter(
        dem.astype(np.float64),
        local_std,
        size=kernel_size,
        mode='reflect',
    )
    return roughness.astype(np.float32)


def compute_dtm_quality_metrics(
    dem: np.ndarray,
    count_grid: np.ndarray,
    cell_res: float,
    roughness_kernel: int = 3,
) -> Dict:
    """Compute DTM quality metrics from a DEM and point count grid.

    Args:
        dem: Ground DEM array (ny, nx)
        count_grid: Per-cell point count array (ny, nx), int32
        cell_res: Cell resolution in meters
        roughness_kernel: Kernel size for local roughness computation

    Returns:
        Dict with keys: point_stats, roughness_stats, dem_stats, quality_flags
    """
    ny, nx = dem.shape
    n_cells = int(ny * nx)
    empty_cells = int(np.sum(count_grid == 0))
    occupied_cells = count_grid[count_grid > 0]

    # Point count statistics
    point_stats = {
        "n_cells": n_cells,
        "cells_with_data": int(n_cells - empty_cells),
        "empty_cells": empty_cells,
        "pct_empty": round(100.0 * empty_cells / max(n_cells, 1), 2),
        "total_points": int(np.sum(count_grid)),
        "min_pts_per_cell": int(np.min(count_grid)),
        "max_pts_per_cell": int(np.max(count_grid)),
        "mean_pts_per_cell": round(float(np.mean(count_grid)), 2),
        "median_pts_per_cell": round(float(np.median(count_grid)), 2),
    }
    if occupied_cells.size > 0:
        point_stats["mean_pts_per_occupied_cell"] = round(float(np.mean(occupied_cells)), 2)
        point_stats["median_pts_per_occupied_cell"] = round(float(np.median(occupied_cells)), 2)

    # Roughness statistics
    roughness = compute_local_roughness(dem, kernel_size=roughness_kernel)
    finite_roughness = roughness[np.isfinite(roughness)]
    roughness_stats: Dict = {
        "kernel_size": roughness_kernel,
    }
    if finite_roughness.size > 0:
        roughness_stats.update({
            "min": round(float(np.min(finite_roughness)), 4),
            "max": round(float(np.max(finite_roughness)), 4),
            "mean": round(float(np.mean(finite_roughness)), 4),
            "median": round(float(np.median(finite_roughness)), 4),
            "p95": round(float(np.percentile(finite_roughness, 95)), 4),
        })
    else:
        roughness_stats.update({"min": None, "max": None, "mean": None, "median": None, "p95": None})

    # DEM elevation statistics
    finite_dem = dem[np.isfinite(dem)]
    if finite_dem.size > 0:
        dem_stats = {
            "min_z": round(float(np.min(finite_dem)), 3),
            "max_z": round(float(np.max(finite_dem)), 3),
            "mean_z": round(float(np.mean(finite_dem)), 3),
            "range_z": round(float(np.ptp(finite_dem)), 3),
        }
    else:
        dem_stats = {"min_z": None, "max_z": None, "mean_z": None, "range_z": None}

    # Quality flags
    quality_flags: List[str] = []
    if point_stats["pct_empty"] > 20:
        quality_flags.append(f"HIGH_EMPTY_CELLS: {point_stats['pct_empty']:.1f}% cells have no points")
    if occupied_cells.size > 0 and np.median(occupied_cells) < 3:
        quality_flags.append(f"LOW_SUPPORT: median {np.median(occupied_cells):.0f} points/cell")
    if roughness_stats.get("p95") is not None and roughness_stats["p95"] > 0.1:
        quality_flags.append(f"HIGH_ROUGHNESS: p95 roughness = {roughness_stats['p95']:.3f}m")

    return {
        "cell_res": cell_res,
        "point_stats": point_stats,
        "roughness_stats": roughness_stats,
        "dem_stats": dem_stats,
        "quality_flags": quality_flags,
    }
