#!/usr/bin/env python3
"""
LiDAR penguin detection via DEM + Height-Above-Ground (HAG) analysis.

Pipeline per file:
- Stream LAS/LAZ to build a ground DEM (min Z) on a regular XY grid (cell size in meters)
- Stream again to compute HAG per cell (max Z - ground DEM)
- Detect penguin-like blobs: HAG within [hag_min, hag_max], small, compact regions
- Count connected components / peaks; write per-file counts + summary JSON; optional PNGs

Designed to avoid loading all points in memory; baseline Python is 3.12.x (tests may run on newer versions).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Add project src to path for consistency
import sys
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[1]
for p in [str(_ROOT / "src"), str(_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Optional plotting
try:
    import matplotlib

    matplotlib.use("Agg")  # Headless-safe backend
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

# Image processing
from skimage import morphology, measure
from skimage.segmentation import watershed
from scipy import ndimage as ndi
from scipy.ndimage import percentile_filter
from scipy.spatial import cKDTree
from pipelines.utils.provenance import write_provenance, append_timings
from pipelines.contracts import LIDAR_CANDIDATES_CONTRACT, LIDAR_CANDIDATES_PURPOSE
from pipelines.lidar_profiles import (
    OFFICIAL_DETERMINISTIC,
    SENSOR_PROFILES,
    as_policy_dict,
)
from pipelines.blob_features import extract_blob_features, BlobFeatures
from pipelines.official_reporting import (
    check_aoi_integrity,
    collect_git_context,
    collect_ground_quantile_fallbacks,
    load_aoi_registry,
    lookup_aoi_registry_entry,
)
import hashlib

# LAS streaming
try:
    import laspy  # type: ignore
    LASPY_AVAILABLE = True
except Exception:
    LASPY_AVAILABLE = False

# Optional CSF ground model
try:
    import CSF as _csf_module  # type: ignore
    HAS_CSF = True
except ImportError:
    HAS_CSF = False


def _is_sample_path(path: Path) -> bool:
    """Return True if any path component equals 'sample' (case-insensitive)."""
    return any(part.lower() == "sample" for part in path.parts)


def find_lidar_files(root: Path) -> List[Path]:
    """Recursively discover LAS/LAZ files under *root*, deduplicating sample/ copies.

    When both a ``sample/`` version and a non-sample version of the same
    filename exist, only the non-sample path is kept.  Results are sorted by
    string path for deterministic ordering.
    """
    files: List[Path] = []
    for dp, _dns, fns in os.walk(root):
        for fn in fns:
            if Path(fn).suffix.lower() in {".las", ".laz"}:
                files.append(Path(dp) / fn)
    # Avoid accidentally dropping real tiles that share a filename across directories.
    # Only de-duplicate the special case where both a `sample/` version and a non-sample
    # version exist for the same filename; prefer the non-sample path in that case.
    files = sorted(files, key=str)
    by_name: Dict[str, List[Path]] = {}
    for path in files:
        by_name.setdefault(path.name.lower(), []).append(path)

    filtered: List[Path] = []
    for group in by_name.values():
        if len(group) == 1:
            filtered.append(group[0])
            continue
        non_sample = [p for p in group if not _is_sample_path(p)]
        sample = [p for p in group if _is_sample_path(p)]
        if non_sample and sample:
            filtered.extend(non_sample)
        else:
            # Either all are non-sample, or all are sample → keep them all.
            filtered.extend(group)
    return sorted(filtered, key=str)


def _compute_bounds_stream(las_path: Path, chunk_size: int) -> Tuple[np.ndarray, np.ndarray, int]:
    """Compute bounds by streaming points (robust when header mins/maxs are absent)."""
    min_xyz = np.array([np.inf, np.inf, np.inf], dtype=float)
    max_xyz = np.array([-np.inf, -np.inf, -np.inf], dtype=float)
    total = 0
    for x, y, z in _stream_points(las_path, chunk_size):
        if x.size:
            total += x.size
            min_xyz[0] = min(min_xyz[0], float(np.min(x)))
            min_xyz[1] = min(min_xyz[1], float(np.min(y)))
            min_xyz[2] = min(min_xyz[2], float(np.min(z)))
            max_xyz[0] = max(max_xyz[0], float(np.max(x)))
            max_xyz[1] = max(max_xyz[1], float(np.max(y)))
            max_xyz[2] = max(max_xyz[2], float(np.max(z)))
    if not np.isfinite(min_xyz).all() or not np.isfinite(max_xyz).all():
        # No points encountered
        min_xyz = np.zeros(3, dtype=float)
        max_xyz = np.zeros(3, dtype=float)
    return min_xyz, max_xyz, total


def read_bounds_and_counts(las_path: Path, chunk_size: int) -> Tuple[np.ndarray, np.ndarray, int]:
    """Return min/max XYZ and point count, using header if available else streaming."""
    if not LASPY_AVAILABLE:
        raise RuntimeError("laspy not available")
    try:
        with laspy.open(str(las_path)) as fh:  # type: ignore[attr-defined]
            h = fh.header
            # Prefer laspy 2.x arrays if available
            mins_arr = getattr(h, "mins", None)
            maxs_arr = getattr(h, "maxs", None)
            if mins_arr is not None and maxs_arr is not None:
                mins = np.array(mins_arr, dtype=float)
                maxs = np.array(maxs_arr, dtype=float)
            else:
                mins = np.array([
                    getattr(h, "min_x", 0.0), getattr(h, "min_y", 0.0), getattr(h, "min_z", 0.0)
                ], dtype=float)
                maxs = np.array([
                    getattr(h, "max_x", 0.0), getattr(h, "max_y", 0.0), getattr(h, "max_z", 0.0)
                ], dtype=float)
            npts = int(getattr(h, "point_count", 0))
    except Exception:
        # Fallback entirely to streaming
        return _compute_bounds_stream(las_path, chunk_size)

    # If header bounds look degenerate, compute via streaming
    if np.any((maxs - mins) <= 0) or not np.isfinite(mins).all() or not np.isfinite(maxs).all():
        return _compute_bounds_stream(las_path, chunk_size)
    # If header point count is zero, compute via streaming to confirm
    if npts <= 0:
        mins_s, maxs_s, npts_s = _compute_bounds_stream(las_path, chunk_size)
        return mins_s, maxs_s, npts_s
    return mins, maxs, npts


def _stream_points(las_path: Path, chunk_size: int, include_intensity: bool = False):
    """Stream LAS points as (x, y, z) or (x, y, z, intensity) tuples."""
    with laspy.open(str(las_path)) as fh:  # type: ignore[attr-defined]
        if hasattr(fh, "chunk_iterator"):
            for pts in fh.chunk_iterator(chunk_size):  # type: ignore[attr-defined]
                x = np.asarray(pts.x, dtype=np.float64)
                y = np.asarray(pts.y, dtype=np.float64)
                z = np.asarray(pts.z, dtype=np.float64)
                if x.size:
                    if include_intensity:
                        try:
                            intensity = np.asarray(pts.intensity, dtype=np.float32)
                        except AttributeError:
                            intensity = np.zeros_like(x, dtype=np.float32)
                        yield x, y, z, intensity
                    else:
                        yield x, y, z
        else:
            total = int(getattr(fh.header, "point_count", 0))  # type: ignore[attr-defined]
            start = 0
            while start < total:
                count = min(chunk_size, total - start)
                pts = fh.read_points(start=start, count=count)  # type: ignore[attr-defined]
                x = np.asarray(pts.x, dtype=np.float64)
                y = np.asarray(pts.y, dtype=np.float64)
                z = np.asarray(pts.z, dtype=np.float64)
                if x.size:
                    if include_intensity:
                        try:
                            intensity = np.asarray(pts.intensity, dtype=np.float32)
                        except AttributeError:
                            intensity = np.zeros_like(x, dtype=np.float32)
                        yield x, y, z, intensity
                    else:
                        yield x, y, z
                start += count


def _read_extra_fields(pts, field_name: str) -> Optional[np.ndarray]:
    """Safely read an optional LAS field, returning None if absent."""
    try:
        arr = np.asarray(getattr(pts, field_name))
        return arr
    except (AttributeError, Exception):
        return None


def _build_enrichment_grids(
    las_path: Path,
    chunk_size: int,
    mins: np.ndarray,
    cell_res: float,
    ny: int,
    nx: int,
    include_intensity: bool = True,
    include_rgb: bool = True,
    include_returns: bool = True,
    include_z_std: bool = False,
    verbose: bool = False,
) -> Dict[str, Optional[np.ndarray]]:
    """Build per-cell grids for intensity, RGB, and return count in one streaming pass.

    Returns a dict of grids, each (ny, nx) float32 or None if the field was
    unavailable in the LAS file.  Grid keys:

    - ``intensity``: mean intensity per cell
    - ``rgb_r``, ``rgb_g``, ``rgb_b``: mean red/green/blue per cell (uint16 scale)
    - ``single_return_fraction``: fraction of points per cell where
      number_of_returns == 1 (solid surface indicator)
    """
    n_cells = ny * nx
    # Accumulator arrays — only allocate what we need
    cnt = np.zeros(n_cells, dtype=np.int32)

    if include_intensity:
        intensity_sum = np.zeros(n_cells, dtype=np.float64)
    if include_rgb:
        r_sum = np.zeros(n_cells, dtype=np.float64)
        g_sum = np.zeros(n_cells, dtype=np.float64)
        b_sum = np.zeros(n_cells, dtype=np.float64)
        rgb_available = None  # determined on first chunk
    if include_returns:
        single_cnt = np.zeros(n_cells, dtype=np.int32)
        returns_available = None
    if include_z_std:
        z_sum = np.zeros(n_cells, dtype=np.float64)
        z_sq_sum = np.zeros(n_cells, dtype=np.float64)

    with laspy.open(str(las_path)) as fh:
        for pts in fh.chunk_iterator(chunk_size):
            x = np.asarray(pts.x, dtype=np.float64)
            y = np.asarray(pts.y, dtype=np.float64)
            if not x.size:
                continue
            ix = np.floor((x - mins[0]) / cell_res).astype(np.int64)
            iy = np.floor((y - mins[1]) / cell_res).astype(np.int64)
            valid = (ix >= 0) & (iy >= 0) & (ix < nx) & (iy < ny)
            if not np.any(valid):
                continue
            flat = (iy[valid] * nx + ix[valid])
            np.add.at(cnt, flat, 1)

            if include_z_std:
                z = np.asarray(pts.z, dtype=np.float64)
                z_valid = z[valid]
                np.add.at(z_sum, flat, z_valid)
                np.add.at(z_sq_sum, flat, z_valid * z_valid)

            if include_intensity:
                i_arr = _read_extra_fields(pts, "intensity")
                if i_arr is not None:
                    np.add.at(intensity_sum, flat, i_arr[valid].astype(np.float64))

            if include_rgb and rgb_available is not False:
                r_arr = _read_extra_fields(pts, "red")
                g_arr = _read_extra_fields(pts, "green")
                b_arr = _read_extra_fields(pts, "blue")
                if r_arr is not None and g_arr is not None and b_arr is not None:
                    rgb_available = True
                    np.add.at(r_sum, flat, r_arr[valid].astype(np.float64))
                    np.add.at(g_sum, flat, g_arr[valid].astype(np.float64))
                    np.add.at(b_sum, flat, b_arr[valid].astype(np.float64))
                else:
                    rgb_available = False
                    if verbose:
                        print(f"    {las_path.name}: RGB fields not found in LAS; skipping.", file=sys.stderr)

            if include_returns and returns_available is not False:
                nr = _read_extra_fields(pts, "number_of_returns")
                if nr is not None:
                    returns_available = True
                    is_single = (nr[valid] == 1)
                    np.add.at(single_cnt, flat, is_single.astype(np.int32))
                else:
                    returns_available = False
                    if verbose:
                        print(f"    {las_path.name}: number_of_returns not found; skipping.", file=sys.stderr)

    # Convert accumulators to mean grids
    result: Dict[str, Optional[np.ndarray]] = {}
    cnt_2d = cnt.reshape(ny, nx)
    has_data = cnt_2d > 0

    if include_intensity:
        with np.errstate(divide="ignore", invalid="ignore"):
            igrid = np.where(has_data, (intensity_sum.reshape(ny, nx) / np.maximum(cnt_2d, 1)).astype(np.float32), np.float32(0))
        result["intensity"] = igrid
        if not np.any(has_data) or float(np.max(intensity_sum)) == 0.0:
            print(f"WARNING: {las_path.name}: intensity data is all zeros; "
                  f"LAS file may lack intensity values.", file=sys.stderr)
    else:
        result["intensity"] = None

    if include_rgb and rgb_available:
        with np.errstate(divide="ignore", invalid="ignore"):
            denom = np.maximum(cnt_2d, 1).astype(np.float64)
            result["rgb_r"] = np.where(has_data, (r_sum.reshape(ny, nx) / denom).astype(np.float32), np.float32(0))
            result["rgb_g"] = np.where(has_data, (g_sum.reshape(ny, nx) / denom).astype(np.float32), np.float32(0))
            result["rgb_b"] = np.where(has_data, (b_sum.reshape(ny, nx) / denom).astype(np.float32), np.float32(0))
    else:
        result["rgb_r"] = result["rgb_g"] = result["rgb_b"] = None

    if include_returns and returns_available:
        with np.errstate(divide="ignore", invalid="ignore"):
            result["single_return_fraction"] = np.where(
                has_data,
                (single_cnt.reshape(ny, nx) / np.maximum(cnt_2d, 1)).astype(np.float32),
                np.float32(0),
            )
    else:
        result["single_return_fraction"] = None

    if include_z_std:
        with np.errstate(divide="ignore", invalid="ignore"):
            cnt_safe = np.maximum(cnt_2d, 1).astype(np.float64)
            mean_z = z_sum.reshape(ny, nx) / cnt_safe
            mean_z_sq = z_sq_sum.reshape(ny, nx) / cnt_safe
            variance = np.maximum(mean_z_sq - mean_z * mean_z, 0.0)
            result["z_std"] = np.where(has_data, np.sqrt(variance).astype(np.float32), np.float32(0))
    else:
        result["z_std"] = None

    if verbose:
        for key, grid in result.items():
            if grid is not None and np.any(has_data):
                vals = grid[has_data]
                print(f"    {key} grid: mean={float(np.mean(vals)):.1f}, "
                      f"range=[{float(np.min(vals)):.1f}, {float(np.max(vals)):.1f}]", flush=True)

    return result


def _grid_shape(mins: np.ndarray, maxs: np.ndarray, cell_res: float) -> Tuple[int, int]:
    nx = int(np.ceil((maxs[0] - mins[0]) / cell_res)) + 1
    ny = int(np.ceil((maxs[1] - mins[1]) / cell_res)) + 1
    return ny, nx  # rows (y), cols (x)


def _bin_indices(x: np.ndarray, y: np.ndarray, mins: np.ndarray, cell_res: float, ny: int, nx: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    ix = np.floor((x - mins[0]) / cell_res).astype(np.int64)
    iy = np.floor((y - mins[1]) / cell_res).astype(np.int64)
    valid = (ix >= 0) & (iy >= 0) & (ix < nx) & (iy < ny)
    return ix[valid], iy[valid], valid


def _online_quantile_update_indexed(
    q_flat: np.ndarray,
    idx: np.ndarray,
    x: np.ndarray,
    p: float,
    lr: float,
) -> None:
    """Update per-cell quantiles for a stream chunk, handling duplicate cell indices.

    ``idx`` is a flattened cell index per sample in ``x`` and typically contains
    duplicates (many points per cell). This function aggregates updates per
    unique cell index so all points contribute deterministically within a chunk.
    """
    if idx.size == 0:
        return

    idx = np.asarray(idx, dtype=np.int64)
    x = np.asarray(x, dtype=np.float32)

    uniq, inv = np.unique(idx, return_inverse=True)
    q_u = np.asarray(q_flat[uniq], dtype=np.float32).copy()

    nan_mask = np.isnan(q_u)
    if nan_mask.any():
        if p <= 0.5:
            init = np.full(uniq.shape[0], np.inf, dtype=np.float32)
            np.minimum.at(init, inv, x)
        else:
            init = np.full(uniq.shape[0], -np.inf, dtype=np.float32)
            np.maximum.at(init, inv, x)
        q_u[nan_mask] = init[nan_mask]

    q0 = q_u[inv]
    below = x <= q0
    counts = np.bincount(inv, minlength=uniq.shape[0]).astype(np.float32)
    below_counts = np.bincount(inv, weights=below.astype(np.float32), minlength=uniq.shape[0]).astype(
        np.float32
    )
    frac_below = below_counts / np.maximum(counts, 1.0)
    q_u = q_u + float(lr) * (float(p) - frac_below)
    q_flat[uniq] = q_u


def _build_ground_quantile_exact(
    las_path: Path,
    *,
    mins: np.ndarray,
    cell_res: float,
    ny: int,
    nx: int,
    chunk_size: int,
    counts_flat: np.ndarray,
    percentile: float = 5.0,
    max_memory_gb: float = 2.0,
) -> Tuple[Optional[np.ndarray], Dict[str, object]]:
    """Compute an exact per-cell ground percentile with a two-pass fill.

    The returned array has shape ``(ny, nx)`` with NaN in empty cells. If the
    memory estimate exceeds *max_memory_gb*, returns ``(None, meta)`` so caller
    can apply a deterministic fallback.
    """
    n_cells = int(ny) * int(nx)
    counts_flat = np.asarray(counts_flat, dtype=np.int64).reshape(-1)
    if counts_flat.size != n_cells:
        raise ValueError(
            f"counts_flat shape mismatch: expected {n_cells} cells, got {counts_flat.size}"
        )

    total_points = int(np.sum(counts_flat))
    mem_bytes = total_points * 4  # float32 payload only
    mem_gb = float(mem_bytes / (1024**3))
    meta: Dict[str, object] = {
        "percentile": float(percentile),
        "total_points": total_points,
        "estimated_memory_gb": round(mem_gb, 3),
        "max_memory_gb": float(max_memory_gb),
    }
    if total_points <= 0:
        return np.full((ny, nx), np.nan, dtype=np.float32), meta
    if mem_gb > float(max_memory_gb):
        meta["fallback_reason"] = "memory_limit_exceeded"
        return None, meta

    offsets = np.zeros(n_cells + 1, dtype=np.int64)
    np.cumsum(counts_flat, out=offsets[1:])
    values = np.empty(total_points, dtype=np.float32)
    cursors = offsets[:-1].copy()

    # Pass 2: insert z values into each cell's contiguous slice.
    for x, y, z in _stream_points(las_path, chunk_size):
        ix, iy, mask = _bin_indices(x, y, mins, cell_res, ny, nx)
        if not np.any(mask):
            continue
        flat = (iy * nx + ix).astype(np.int64, copy=False)
        z_valid = z[mask].astype(np.float32, copy=False)

        # Group by cell id to assign contiguous chunk slices.
        order = np.argsort(flat, kind="stable")
        flat_sorted = flat[order]
        z_sorted = z_valid[order]
        uniq, starts, run_counts = np.unique(
            flat_sorted, return_index=True, return_counts=True
        )
        for cell, start, run_count in zip(uniq, starts, run_counts):
            pos = int(cursors[int(cell)])
            end = pos + int(run_count)
            values[pos:end] = z_sorted[start : start + run_count]
            cursors[int(cell)] = end

    q = np.full(n_cells, np.nan, dtype=np.float32)
    occupied = np.nonzero(counts_flat > 0)[0]
    for cell in occupied:
        start = int(offsets[int(cell)])
        end = int(offsets[int(cell) + 1])
        if end <= start:
            continue
        q[int(cell)] = np.percentile(values[start:end], float(percentile))

    return q.reshape(ny, nx), meta


def _autodetect_crs_from_las(las_path: Path) -> Optional[Dict[str, object]]:
    """Attempt to auto-detect CRS from LAS file header using laspy's parse_crs()."""
    if not LASPY_AVAILABLE:
        return None
    try:
        with laspy.open(str(las_path)) as fh:
            h = fh.header
            if not hasattr(h, "parse_crs"):
                return None
            crs_obj = h.parse_crs()
            if crs_obj is None:
                return None
            crs_str = str(crs_obj).strip()
            if not crs_str or crs_str.lower() in ("none", ""):
                return None
            # Try pyproj to extract EPSG if available
            try:
                import pyproj
                crs_parsed = pyproj.CRS.from_wkt(crs_str) if ("GEOGCS" in crs_str or "PROJCS" in crs_str or "COMPD_CS" in crs_str) else pyproj.CRS.from_user_input(crs_str)
                epsg = crs_parsed.to_epsg()
                if epsg is not None:
                    return {"epsg": int(epsg), "wkt": crs_str}
                return {"wkt": crs_str}
            except (ImportError, ValueError, RuntimeError):
                # pyproj not available or parse failed; return raw WKT
                return {"wkt": crs_str}
    except (OSError, ValueError, KeyError, AttributeError) as exc:
        print(f"WARNING: CRS auto-detection failed for {las_path.name}: {exc}", file=sys.stderr)
        return None


def _autodetect_crs_from_files(files: List[Path]) -> Optional[Dict[str, object]]:
    """Auto-detect CRS from the first LAS file that has embedded CRS info."""
    for f in files:
        crs = _autodetect_crs_from_las(f)
        if crs is not None:
            return crs
    return None


def _crs_meta_from_args(crs_epsg: Optional[int], crs_wkt: Optional[str]) -> Optional[Dict[str, object]]:
    if crs_epsg is None and not crs_wkt:
        return None
    meta: Dict[str, object] = {}
    if crs_epsg is not None:
        meta["epsg"] = int(crs_epsg)
    if crs_wkt:
        meta["wkt"] = str(crs_wkt)
    return meta


def compute_confidence_scores(
    dets: List[Dict],
    cell_res: float = 0.25,
    hag_center: float = 0.35,
    hag_sigma: float = 0.08,
    area_center_m2: float = 0.10,
    area_sigma_m2: float = 0.06,
    circularity_weight: float = 0.5,
    solidity_weight: float = 0.5,
) -> None:
    """Compute a [0, 1] confidence score per detection, modifying dets in-place.

    Score components (geometric mean):
    - HAG score: Gaussian membership centered on hag_center
    - Area score: Gaussian membership centered on expected penguin area
    - Shape score: weighted combination of circularity and solidity
    - Intensity score (optional): if intensity_mean present
    """
    for d in dets:
        scores = []

        # HAG score
        hag_mean = d.get("hag_mean")
        if hag_mean is not None:
            hag_score = float(np.exp(-0.5 * ((float(hag_mean) - hag_center) / max(hag_sigma, 1e-6)) ** 2))
            d["confidence_hag"] = round(hag_score, 4)
            scores.append(hag_score)

        # Area score
        area_m2 = d.get("area_m2")
        if area_m2 is not None:
            area_score = float(np.exp(-0.5 * ((float(area_m2) - area_center_m2) / max(area_sigma_m2, 1e-6)) ** 2))
            d["confidence_area"] = round(area_score, 4)
            scores.append(area_score)

        # Shape score
        circ = d.get("circularity")
        sol = d.get("solidity")
        if circ is not None and sol is not None:
            shape_score = float(circularity_weight * min(float(circ), 1.0) + solidity_weight * min(float(sol), 1.0))
            d["confidence_shape"] = round(shape_score, 4)
            scores.append(shape_score)

        # Combined: geometric mean
        if scores:
            combined = float(np.prod(scores) ** (1.0 / len(scores)))
            d["confidence"] = round(max(0.0, min(1.0, combined)), 4)
        else:
            d["confidence"] = 0.0


def _estimate_grid_bytes(
    ny: int,
    nx: int,
    ground_method: str,
    top_method: str,
    slope_max_deg: Optional[float],
    density_stats: bool = False,
) -> int:
    n_cells = int(ny) * int(nx)
    if n_cells <= 0:
        return 0
    bytes_per_cell = 0
    bytes_per_cell += 4  # DEM
    if ground_method.lower() != "min":
        bytes_per_cell += 4  # q05
    bytes_per_cell += 4  # HAG
    if str(top_method).lower() == "p95":
        bytes_per_cell += 4  # q95
    bytes_per_cell += 4  # HAG copy for detection
    if slope_max_deg is not None:
        bytes_per_cell += 4  # slope
    bytes_per_cell += 8  # labeled (int64 conservative)
    bytes_per_cell += 1  # mask
    bytes_per_cell += 4  # scratch buffers
    if density_stats:
        bytes_per_cell += 4  # count grid (int32)
    return int(n_cells * bytes_per_cell)


def _dedupe_detections(
    detections: list[dict],
    *,
    radius_m: float,
) -> tuple[list[dict], dict[str, dict]]:
    """Return (deduped_detections, dedupe_index).

    - `deduped_detections` contains one representative detection per cluster.
    - `dedupe_index` maps original detection id -> {keep_id, cluster_id, dropped}.
    """
    if radius_m <= 0 or not detections:
        return detections, {}

    pts = np.array([(float(d["x"]), float(d["y"])) for d in detections], dtype=np.float64)
    tree = cKDTree(pts)
    neighbors = tree.query_ball_point(pts, r=float(radius_m))
    parent = np.arange(pts.shape[0])

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, nbrs in enumerate(neighbors):
        for j in nbrs:
            if j <= i:
                continue
            union(i, j)

    # Bucket members by root (cluster).
    clusters: dict[int, list[int]] = {}
    for i in range(pts.shape[0]):
        clusters.setdefault(int(find(i)), []).append(i)

    # Choose a deterministic representative for each cluster.
    rep_by_root: dict[int, int] = {}
    for root, members in clusters.items():
        rep = min(
            members,
            key=lambda idx: (
                str(detections[idx].get("file") or ""),
                str(detections[idx].get("id") or ""),
                float(detections[idx].get("x")),
                float(detections[idx].get("y")),
            ),
        )
        rep_by_root[root] = rep

    dedupe_index: dict[str, dict] = {}
    deduped: list[dict] = []
    for root, rep_idx in rep_by_root.items():
        rep_det = dict(detections[rep_idx])
        rep_det["dedupe_cluster_id"] = int(root)
        rep_det["dedupe_cluster_size"] = int(len(clusters[root]))
        deduped.append(rep_det)

    # Stable output order.
    deduped.sort(key=lambda d: (str(d.get("file") or ""), str(d.get("id") or "")))

    for root, members in clusters.items():
        keep_idx = rep_by_root[root]
        keep_id = str(detections[keep_idx].get("id") or "")
        for idx in members:
            det_id = str(detections[idx].get("id") or "")
            if not det_id:
                continue
            dedupe_index[det_id] = {
                "keep_id": keep_id,
                "cluster_id": int(root),
                "dropped": bool(idx != keep_idx),
            }

    return deduped, dedupe_index


def _write_geojson(
    dets: List[Dict],
    out_path: Path,
    crs_meta: Optional[Dict[str, object]],
    coord_units: str,
    transformer: Optional[object] = None,
    source_crs: Optional[Dict[str, object]] = None,
) -> Optional[str]:
    try:
        feats = []
        for d in dets:
            if "x" not in d or "y" not in d:
                continue
            x = float(d["x"])
            y = float(d["y"])
            if transformer is not None:
                try:
                    x, y = transformer.transform(x, y)
                except Exception as e:
                    return f"GeoJSON coordinate transform failed: {e}"
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [x, y]},
                "properties": {k: v for k, v in d.items() if k not in ("x", "y")},
            })
        fc = {
            "type": "FeatureCollection",
            "features": feats,
            "metadata": {"crs": crs_meta, "coord_units": coord_units},
        }
        if source_crs is not None and source_crs != crs_meta:
            fc["metadata"]["source_crs"] = source_crs
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(fc, f)
        return None
    except Exception as e:
        return str(e)


def _write_geotiff(
    raster: np.ndarray,
    out_path: Path,
    mins: np.ndarray,
    cell_res: float,
    crs_meta: Optional[Dict[str, object]],
    nodata: Optional[float] = None,
) -> Optional[str]:
    """Write a raster array as a GeoTIFF.

    Args:
        raster: 2D numpy array (ny, nx) to write
        out_path: Output file path
        mins: XY origin (lower-left corner) as [min_x, min_y, ...]
        cell_res: Cell resolution in meters
        crs_meta: CRS metadata dict with 'epsg' or 'wkt' key
        nodata: Optional nodata value

    Returns:
        None on success, error message string on failure.
        Returns a message (not error) if rasterio is unavailable.
    """
    try:
        import rasterio
        from rasterio.transform import from_origin
    except ImportError:
        return "rasterio not available; skipping GeoTIFF output"

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Rasterio expects transform from upper-left, but our grid origin is lower-left
        # Need to flip vertically and compute upper-left origin
        ny, nx = raster.shape
        # Upper-left Y = lower-left Y + height
        upper_left_y = float(mins[1]) + (ny * cell_res)
        transform = from_origin(float(mins[0]), upper_left_y, cell_res, cell_res)

        # Determine CRS string for rasterio
        crs = None
        if crs_meta is not None:
            if "epsg" in crs_meta and crs_meta["epsg"] is not None:
                crs = f"EPSG:{int(crs_meta['epsg'])}"
            elif "wkt" in crs_meta and crs_meta["wkt"]:
                crs = str(crs_meta["wkt"])

        # Flip raster vertically (origin lower-left -> upper-left for GeoTIFF)
        raster_flipped = np.flipud(raster)

        with rasterio.open(
            out_path,
            "w",
            driver="GTiff",
            height=ny,
            width=nx,
            count=1,
            dtype=raster.dtype,
            crs=crs,
            transform=transform,
            nodata=nodata,
            compress="deflate",
            predictor=3,
            tiled=True,
            blockxsize=256,
            blockysize=256,
        ) as dst:
            dst.write(raster_flipped, 1)

        return None
    except Exception as e:
        return str(e)


def _build_ground_csf(
    las_path: Path,
    cell_res: float,
    ny: int,
    nx: int,
    mins: np.ndarray,
    csf_cloth_resolution: float = 0.5,
    csf_class_threshold: float = 0.3,
    csf_max_points: int = 20_000_000,
    verbose: bool = False,
) -> Tuple[np.ndarray, Dict]:
    """Build ground DEM using Cloth Simulation Filter (CSF).

    CSF requires all points loaded at once. If point count exceeds
    *csf_max_points*, returns ``None`` to signal the caller should fall back.

    Returns ``(dem_array, csf_metadata)`` on success.
    """
    if not HAS_CSF:
        raise RuntimeError("CSF not installed. Run: pip install cloth-simulation-filter")

    # Read all points
    with laspy.open(str(las_path)) as fh:
        las_data = fh.read()
    x = np.asarray(las_data.x, dtype=np.float64)
    y = np.asarray(las_data.y, dtype=np.float64)
    z = np.asarray(las_data.z, dtype=np.float64)
    npts = x.size

    csf_meta: Dict = {"ground_method": "csf", "csf_total_points": int(npts)}

    if npts > csf_max_points:
        csf_meta["csf_fallback"] = True
        csf_meta["csf_fallback_reason"] = (
            f"Point count {npts} exceeds csf_max_points {csf_max_points}"
        )
        if verbose:
            print(
                f"    CSF: {npts} points exceeds limit {csf_max_points}; "
                f"falling back to p05",
                file=sys.stderr,
                flush=True,
            )
        return np.array([]), csf_meta  # empty array signals fallback

    if verbose:
        print(f"    CSF: classifying {npts} points ...", flush=True)

    csf = _csf_module.CSF()
    csf.params.bSloopSmooth = True
    csf.params.cloth_resolution = float(csf_cloth_resolution)
    csf.params.class_threshold = float(csf_class_threshold)

    # CSF expects Nx3 array
    xyz = np.column_stack([x, y, z])
    csf.setPointCloud(xyz)
    ground_indices = _csf_module.VecInt()
    non_ground_indices = _csf_module.VecInt()
    csf.do_filtering(ground_indices, non_ground_indices)

    ground_idx = np.asarray(ground_indices)
    csf_meta["csf_ground_points"] = int(ground_idx.size)
    csf_meta["csf_nonground_points"] = int(npts - ground_idx.size)
    csf_meta["csf_fallback"] = False

    if verbose:
        print(
            f"    CSF: {ground_idx.size} ground / {npts - ground_idx.size} non-ground",
            flush=True,
        )

    # Build DEM from ground points only (cell-wise minimum)
    dem = np.full((ny, nx), np.inf, dtype=np.float32)
    gx = x[ground_idx]
    gy = y[ground_idx]
    gz = z[ground_idx].astype(np.float32)

    ix = np.floor((gx - mins[0]) / cell_res).astype(np.int64)
    iy = np.floor((gy - mins[1]) / cell_res).astype(np.int64)
    valid = (ix >= 0) & (iy >= 0) & (ix < nx) & (iy < ny)
    flat = iy[valid] * nx + ix[valid]
    if flat.size:
        np.minimum.at(dem.ravel(), flat, gz[valid])

    # Fill no-data via nearest-neighbor interpolation
    if np.isinf(dem).any():
        finite = np.isfinite(dem)
        if finite.any() and (~finite).any():
            idx = ndi.distance_transform_edt(~finite, return_distances=False, return_indices=True)
            dem = dem[tuple(idx)]
        else:
            dem = np.full_like(dem, 0.0)

    return dem.astype(np.float32), csf_meta


def build_ground_dem(
    las_path: Path,
    cell_res: float,
    chunk_size: int,
    verbose: bool,
    ground_method: str = "min",
    quantile_lr: float = 0.05,
    bounds: Optional[Tuple[np.ndarray, np.ndarray]] = None,
    count_grid: Optional[np.ndarray] = None,
    include_dsm: bool = False,
    quantile_max_memory_gb: float = 2.0,
) -> Tuple[np.ndarray, Dict]:
    """Build a ground-surface DEM by streaming LAS points into a regular grid.

    Uses either per-cell minimum Z (``ground_method='min'``) or an exact 5th
    percentile estimate with memory guard (``ground_method='p05'``).  No-data cells are filled via
    nearest-neighbor interpolation.  Returns the DEM array and a metadata dict
    containing grid origin, extent, cell resolution, and shape.

    If *count_grid* is provided (pre-allocated int32 array of shape (ny, nx)),
    it is incremented per point during the streaming pass for density reporting.

    If *include_dsm* is True, also tracks per-cell maximum Z (DSM) in the same
    streaming pass and stores the result in ``meta["dsm"]``.
    """
    if bounds is None:
        mins, maxs, _ = read_bounds_and_counts(las_path, chunk_size)
    else:
        mins, maxs = bounds
        mins = np.array(mins, dtype=float)
        maxs = np.array(maxs, dtype=float)
    ny, nx = _grid_shape(mins, maxs, cell_res)
    dem = np.full((ny, nx), np.inf, dtype=np.float32)
    if include_dsm:
        dsm = np.full((ny, nx), -np.inf, dtype=np.float32)
    use_quantile_ground = ground_method.lower() != "min"
    quantile_counts_flat: Optional[np.ndarray] = None
    if use_quantile_ground:
        quantile_counts_flat = np.zeros(ny * nx, dtype=np.int64)
    global_min_z: Optional[float] = None

    if verbose:
        print(f"    DEM grid {ny}x{nx} at {cell_res} m", flush=True)

    for x, y, z in _stream_points(las_path, chunk_size):
        ix, iy, mask = _bin_indices(x, y, mins, cell_res, ny, nx)
        z_valid = z[mask]
        if z_valid.size:
            z_min_chunk = float(np.min(z_valid))
            global_min_z = z_min_chunk if global_min_z is None else min(global_min_z, z_min_chunk)
        # O(n) in-place reduction using indexed ufuncs
        flat = (iy * nx + ix)
        if flat.size:
            dem_flat = dem.ravel()
            z_f32 = z_valid.astype(np.float32)
            np.minimum.at(dem_flat, flat, z_f32)
            if include_dsm:
                np.maximum.at(dsm.ravel(), flat, z_f32)
            if count_grid is not None:
                np.add.at(count_grid.ravel(), flat, 1)
            if quantile_counts_flat is not None:
                np.add.at(quantile_counts_flat, flat, 1)

    # Replace inf (no data) with fallback values
    if np.isinf(dem).all():
        # No cells received data; fall back to a flat DEM at global min z (or 0 if unknown)
        fallback = 0.0 if global_min_z is None else global_min_z
        dem = np.full_like(dem, float(fallback))
    elif np.isinf(dem).any():
        # Nearest-neighbor fill via distance transform to avoid edge smearing
        finite = np.isfinite(dem)
        if finite.any() and (~finite).any():
            idx = ndi.distance_transform_edt(~finite, return_distances=False, return_indices=True)
            dem = dem[tuple(idx)]
        else:
            fallback = 0.0 if global_min_z is None else global_min_z
            dem = np.full_like(dem, float(fallback))

    meta = {"mins": mins.tolist(), "maxs": maxs.tolist(), "cell_res": cell_res, "shape": [int(ny), int(nx)]}
    if use_quantile_ground:
        # Retain for reproducibility traces while p05 transitioned away from online updates.
        meta["ground_quantile_lr_legacy"] = float(quantile_lr)

    # Choose ground surface
    ground_method_actual = "min"
    if not use_quantile_ground:
        ground = dem
    else:
        assert quantile_counts_flat is not None
        q05, q05_meta = _build_ground_quantile_exact(
            las_path,
            mins=mins,
            cell_res=cell_res,
            ny=ny,
            nx=nx,
            chunk_size=chunk_size,
            counts_flat=quantile_counts_flat,
            percentile=5.0,
            max_memory_gb=float(quantile_max_memory_gb),
        )
        if q05 is None:
            ground = dem
            q05_meta["fallback_method"] = "min"
            if verbose:
                print(
                    "    WARNING: p05 ground fallback to min (memory estimate exceeds "
                    f"{float(quantile_max_memory_gb):.2f} GB)",
                    flush=True,
                )
        else:
            # Fallback to DEM where q05 is NaN.
            ground = np.where(np.isnan(q05), dem, q05)
            ground_method_actual = "p05-exact"
        meta["ground_quantile"] = q05_meta
    meta["ground_method_actual"] = ground_method_actual

    if include_dsm:
        # Fill DSM gaps with NN interpolation (same approach as DTM)
        neg_inf_mask = np.isinf(dsm) & (dsm < 0)
        if neg_inf_mask.all():
            dsm = np.full_like(dsm, float(global_min_z or 0.0))
        elif neg_inf_mask.any():
            finite_dsm = ~neg_inf_mask
            if finite_dsm.any():
                idx_dsm = ndi.distance_transform_edt(neg_inf_mask, return_distances=False, return_indices=True)
                dsm = dsm[tuple(idx_dsm)]
        meta["dsm"] = dsm.astype(np.float32)

    return ground.astype(np.float32), meta


def build_hag_grid(las_path: Path, dem: np.ndarray, meta: Dict, chunk_size: int,
                   top_method: str = "max",
                   top_zscore_cap: Optional[float] = None,
                   top_quantile_lr: float = 0.05) -> np.ndarray:
    """Compute per-cell Height Above Ground by streaming LAS points against *dem*.

    For each point the HAG is ``z - DEM[cell]``; the per-cell aggregate is either
    the maximum (``top_method='max'``) or an online 95th percentile estimate
    (``top_method='p95-online'``).  An optional Z-score cap suppresses outlier spikes.
    The returned array is clipped to non-negative values.

    Note: For exact p95 percentile, use ``build_hag_grid_exact_percentile()`` instead.
    The online p95 estimator has convergence issues with chunked streaming.
    """
    mins = np.array(meta["mins"], dtype=float)
    cell_res = float(meta["cell_res"])
    ny, nx = dem.shape
    use_p95_online = (str(top_method).lower() == "p95-online")
    hag = np.zeros_like(dem, dtype=np.float32)
    # Approximate per-cell p95 using online quantile tracking
    q95 = np.full_like(dem, np.nan, dtype=np.float32) if use_p95_online else None
    for x, y, z in _stream_points(las_path, chunk_size):
        ix, iy, mask = _bin_indices(x, y, mins, cell_res, ny, nx)
        if not np.any(mask):
            continue
        z_valid = z[mask]
        # height above ground per point -> per cell max
        ground = dem[iy, ix]
        hag_chunk = (z_valid - ground).astype(np.float32)
        flat = (iy * nx + ix)
        if flat.size:
            if use_p95_online:
                q95_flat = q95.ravel()  # type: ignore[arg-type]
                _online_quantile_update_indexed(q95_flat, flat, hag_chunk, p=0.95, lr=top_quantile_lr)
            else:
                hag_flat = hag.ravel()
                np.maximum.at(hag_flat, flat, hag_chunk)
    # Finalize HAG surface
    if use_p95_online and q95 is not None:
        hag = np.where(np.isnan(q95), hag, q95)
    if top_zscore_cap is not None and not use_p95_online:
        finite = np.isfinite(hag)
        if finite.any():
            mean = float(np.nanmean(hag[finite]))
            std = float(np.nanstd(hag[finite]))
            if std > 0:
                cap = mean + float(top_zscore_cap) * std
                hag = np.clip(hag, 0, cap, out=hag)
    # Ensure non-negative
    return np.clip(hag, 0, None)


def build_hag_grid_histogram_percentile(
    las_path: Path,
    dem: np.ndarray,
    meta: Dict,
    chunk_size: int,
    percentile: float = 95.0,
    hag_bin_min: float = -0.5,
    hag_bin_max: float = 3.0,
    n_bins: int = 350,
) -> np.ndarray:
    """Compute per-cell HAG percentile using histogram-based estimation.

    Memory-efficient O(n_cells * n_bins) approach suitable for production use.
    Builds a histogram of HAG values per cell, then computes approximate
    percentile from the histogram.

    Args:
        las_path: Path to LAS/LAZ file
        dem: Ground DEM array (ny, nx)
        meta: Grid metadata with mins, cell_res, shape
        chunk_size: LAS streaming chunk size
        percentile: Target percentile (default 95)
        hag_bin_min: Minimum HAG value for histogram bins
        hag_bin_max: Maximum HAG value for histogram bins
        n_bins: Number of histogram bins

    Returns:
        HAG percentile array (ny, nx)
    """
    mins = np.array(meta["mins"], dtype=float)
    cell_res = float(meta["cell_res"])
    ny, nx = dem.shape
    n_cells = ny * nx

    # Histogram bins
    bin_edges = np.linspace(hag_bin_min, hag_bin_max, n_bins + 1)
    bin_width = bin_edges[1] - bin_edges[0]

    # Per-cell histogram counts: shape (n_cells, n_bins)
    # Use uint16 to save memory (max 65535 points per bin per cell)
    histograms = np.zeros((n_cells, n_bins), dtype=np.uint16)

    # Stream points and build histograms
    for x, y, z in _stream_points(las_path, chunk_size):
        ix, iy, mask = _bin_indices(x, y, mins, cell_res, ny, nx)
        if not np.any(mask):
            continue
        z_valid = z[mask]
        ground = dem[iy, ix]
        hag_vals = (z_valid - ground).astype(np.float32)
        flat = (iy * nx + ix)

        # Bin the HAG values
        bin_indices = np.clip(
            ((hag_vals - hag_bin_min) / bin_width).astype(np.int32),
            0, n_bins - 1
        )

        # Increment histogram counts
        np.add.at(histograms, (flat, bin_indices), 1)

    # Compute percentile from histograms
    hag = np.zeros((ny, nx), dtype=np.float32)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    for i in range(n_cells):
        hist = histograms[i]
        total = hist.sum()
        if total == 0:
            continue

        row = i // nx
        col = i % nx

        # Find percentile from cumulative histogram
        target_count = total * (percentile / 100.0)
        cumsum = np.cumsum(hist)
        bin_idx = np.searchsorted(cumsum, target_count)
        bin_idx = min(bin_idx, n_bins - 1)

        # Linear interpolation within bin for better accuracy
        if bin_idx > 0:
            prev_cum = cumsum[bin_idx - 1]
            curr_cum = cumsum[bin_idx]
            if curr_cum > prev_cum:
                frac = (target_count - prev_cum) / (curr_cum - prev_cum)
                hag[row, col] = bin_edges[bin_idx] + frac * bin_width
            else:
                hag[row, col] = bin_centers[bin_idx]
        else:
            hag[row, col] = bin_centers[bin_idx]

    return np.clip(hag, 0, None)


def build_hag_grid_exact_percentile(
    las_path: Path,
    dem: np.ndarray,
    meta: Dict,
    chunk_size: int,
    percentile: float = 95.0,
    max_memory_gb: float = 4.0,
) -> np.ndarray:
    """Compute per-cell HAG percentile using a two-pass exact approach.

    Pass 1: Stream all points, compute HAG, count per cell.
    Allocate a flat float32 array large enough to hold all HAG values.
    Pass 2: Stream again, insert HAG values into the flat array at per-cell offsets.
    Post-pass: For each occupied cell, compute np.percentile on its slice.

    Falls back to histogram-based p95 if memory exceeds *max_memory_gb*.

    Args:
        las_path: Path to LAS/LAZ file
        dem: Ground DEM array (ny, nx)
        meta: Grid metadata with mins, cell_res, shape
        chunk_size: LAS streaming chunk size
        percentile: Target percentile (default 95)
        max_memory_gb: Maximum memory for the value array (default 4 GB)

    Returns:
        HAG percentile array (ny, nx)
    """
    mins = np.array(meta["mins"], dtype=float)
    cell_res = float(meta["cell_res"])
    ny, nx = dem.shape
    n_cells = ny * nx

    # Pass 1: count points per cell
    counts = np.zeros(n_cells, dtype=np.int64)
    for x, y, z in _stream_points(las_path, chunk_size):
        ix, iy, mask = _bin_indices(x, y, mins, cell_res, ny, nx)
        if not np.any(mask):
            continue
        flat = (iy * nx + ix)
        if flat.size:
            np.add.at(counts, flat, 1)

    total_points = int(counts.sum())
    mem_bytes = total_points * 4  # float32
    mem_gb = mem_bytes / (1024 ** 3)
    if mem_gb > max_memory_gb:
        print(
            f"WARNING: p95-exact would need {mem_gb:.1f} GB (>{max_memory_gb:.1f} GB limit); "
            f"falling back to histogram p95.",
            file=sys.stderr,
        )
        return build_hag_grid_histogram_percentile(
            las_path, dem, meta, chunk_size, percentile=percentile,
        )

    # Build cumulative offset array
    offsets = np.zeros(n_cells + 1, dtype=np.int64)
    np.cumsum(counts, out=offsets[1:])

    # Allocate flat storage
    values = np.empty(total_points, dtype=np.float32)
    cursors = offsets[:-1].copy()  # per-cell fill position

    # Pass 2: insert HAG values
    for x, y, z in _stream_points(las_path, chunk_size):
        ix, iy, mask = _bin_indices(x, y, mins, cell_res, ny, nx)
        if not np.any(mask):
            continue
        z_valid = z[mask]
        ground = dem[iy, ix]
        hag_chunk = (z_valid - ground).astype(np.float32)
        flat = (iy * nx + ix)
        # Insert values at cursor positions (sequential within chunk to avoid races)
        for i in range(flat.size):
            cell = flat[i]
            pos = cursors[cell]
            values[pos] = hag_chunk[i]
            cursors[cell] = pos + 1

    # Compute percentile per cell
    hag = np.zeros((ny, nx), dtype=np.float32)
    for cell_idx in range(n_cells):
        start = offsets[cell_idx]
        end = offsets[cell_idx + 1]
        if end <= start:
            continue
        row = cell_idx // nx
        col = cell_idx % nx
        cell_values = values[start:end]
        hag[row, col] = np.percentile(cell_values, percentile)

    return np.clip(hag, 0, None)


def build_hag_multi_surface(
    las_path: Path,
    dem: np.ndarray,
    meta: Dict,
    chunk_size: int,
) -> Dict[str, np.ndarray]:
    """Compute multiple HAG surface statistics in a single streaming pass.

    Memory-efficient approach using running statistics (Welford's algorithm)
    for mean/std, plus tracking max and histogram for percentiles.

    Args:
        las_path: Path to LAS/LAZ file
        dem: Ground DEM array (ny, nx)
        meta: Grid metadata with mins, cell_res, shape
        chunk_size: LAS streaming chunk size

    Returns:
        Dict with keys: 'max', 'mean', 'std', 'p50', 'p90', 'p95'
    """
    mins = np.array(meta["mins"], dtype=float)
    cell_res = float(meta["cell_res"])
    ny, nx = dem.shape
    n_cells = ny * nx

    # Running statistics arrays
    hag_max = np.full((ny, nx), -np.inf, dtype=np.float32)
    count = np.zeros((ny, nx), dtype=np.int32)
    mean = np.zeros((ny, nx), dtype=np.float64)
    m2 = np.zeros((ny, nx), dtype=np.float64)  # For Welford's algorithm

    # Histogram for percentiles
    hag_bin_min, hag_bin_max, n_bins = -0.5, 3.0, 350
    bin_edges = np.linspace(hag_bin_min, hag_bin_max, n_bins + 1)
    bin_width = bin_edges[1] - bin_edges[0]
    histograms = np.zeros((n_cells, n_bins), dtype=np.uint16)

    # Stream points
    for x, y, z in _stream_points(las_path, chunk_size):
        ix, iy, mask = _bin_indices(x, y, mins, cell_res, ny, nx)
        if not np.any(mask):
            continue
        z_valid = z[mask]
        ground = dem[iy, ix]
        hag_vals = (z_valid - ground).astype(np.float32)
        flat = (iy * nx + ix)

        # Update max
        np.maximum.at(hag_max.ravel(), flat, hag_vals)

        # Update running mean/variance (Welford's algorithm, vectorized)
        for cell_idx, hag_val in zip(flat, hag_vals):
            row, col = cell_idx // nx, cell_idx % nx
            count[row, col] += 1
            delta = hag_val - mean[row, col]
            mean[row, col] += delta / count[row, col]
            delta2 = hag_val - mean[row, col]
            m2[row, col] += delta * delta2

        # Update histogram
        bin_indices = np.clip(
            ((hag_vals - hag_bin_min) / bin_width).astype(np.int32),
            0, n_bins - 1
        )
        np.add.at(histograms, (flat, bin_indices), 1)

    # Finalize std
    with np.errstate(divide='ignore', invalid='ignore'):
        variance = np.where(count > 1, m2 / (count - 1), 0.0)
    hag_std = np.sqrt(variance).astype(np.float32)

    # Replace -inf with NaN for cells with no data
    hag_max = np.where(np.isinf(hag_max), np.nan, hag_max)

    # Compute percentiles from histograms
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    def percentile_from_hist(pct):
        result = np.full((ny, nx), np.nan, dtype=np.float32)
        for i in range(n_cells):
            hist = histograms[i]
            total = hist.sum()
            if total == 0:
                continue
            row, col = i // nx, i % nx
            target = total * (pct / 100.0)
            cumsum = np.cumsum(hist)
            bin_idx = min(np.searchsorted(cumsum, target), n_bins - 1)
            if bin_idx > 0 and cumsum[bin_idx] > cumsum[bin_idx - 1]:
                frac = (target - cumsum[bin_idx - 1]) / (cumsum[bin_idx] - cumsum[bin_idx - 1])
                result[row, col] = bin_edges[bin_idx] + frac * bin_width
            else:
                result[row, col] = bin_centers[bin_idx]
        return np.fmax(result, 0)  # Clip negative values to 0, preserving NaN

    # Set empty cells to NaN for mean (where count==0)
    mean_final = np.where(count > 0, mean, np.nan).astype(np.float32)
    std_final = np.where(count > 0, hag_std, np.nan).astype(np.float32)

    return {
        'max': np.fmax(hag_max, 0).astype(np.float32),  # Clip negatives, preserve NaN
        'mean': np.fmax(mean_final, 0).astype(np.float32),
        'std': std_final,
        'p50': percentile_from_hist(50),
        'p90': percentile_from_hist(90),
        'p95': percentile_from_hist(95),
    }


def detect_penguins_from_hag(hag: np.ndarray,
                             hag_min: float,
                             hag_max: float,
                             min_area_cells: int,
                             max_area_cells: int,
                             smooth_sigma: float = 0.0,
                             connectivity: int = 2,
                             slope: Optional[np.ndarray] = None,
                             slope_max_deg: Optional[float] = None,
                             cell_res: Optional[float] = None,
                             mins: Optional[np.ndarray] = None,
                             refine_grid_pct: Optional[float] = None,
                             refine_size: int = 3,
                             se_radius_m: float = 0.15,
                             circularity_min: float = 0.2,
                             solidity_min: float = 0.7,
                             apply_watershed: bool = False,
                             h_maxima_h: float = 0.05,
                             min_split_area_cells: int = 12,
                             border_trim_px: int = 0,
                             expected_penguin_area_cells: Optional[int] = None,
                             watershed_merge_threshold: float = 1.5,
                             emit_diagnostics: bool = False) -> Tuple[int, np.ndarray, List[Dict], Dict]:
    """Detect penguin-sized blobs from a HAG grid via threshold, morphology, and labeling.

    Returns ``(count, labeled_image, detections_list, watershed_stats)``.  Each detection dict
    contains centroid coordinates (row/col and optionally projected x/y), area,
    shape metrics (circularity, solidity), and HAG statistics.  Optional
    watershed splitting subdivides large blobs that likely contain multiple
    individuals.

    The selective watershed trigger only attempts to split blobs that are
    "likely merged" (area > expected_penguin_area_cells * watershed_merge_threshold).
    If expected_penguin_area_cells is not provided, it defaults to min_split_area_cells.
    """
    # Optional smoothing
    img = hag.copy()
    if smooth_sigma > 0:
        try:
            from scipy.ndimage import gaussian_filter
            img = gaussian_filter(img, sigma=smooth_sigma)
        except Exception:
            pass
    # Optional cheap refinement on grid to suppress spikes
    if refine_grid_pct is not None and 0 < refine_grid_pct < 100:
        hag = percentile_filter(hag, percentile=float(refine_grid_pct), size=int(refine_size))
        img = hag
    # Threshold HAG window
    mask = (img >= hag_min) & (img <= hag_max)
    # Morphological cleanup
    se_px = 1
    if cell_res is not None and se_radius_m is not None:
        se_px = max(1, int(round(se_radius_m / max(cell_res, 1e-6))))
    se = morphology.disk(se_px)
    mask = morphology.binary_opening(mask, se)
    mask = morphology.binary_closing(mask, se)
    mask &= (hag >= hag_min) & (hag <= hag_max)
    # Label connected components
    labeled = measure.label(mask, connectivity=connectivity)

    # Optional watershed split on large blobs only (selective trigger)
    # Track split statistics for diagnostics
    _watershed_stats = {
        "n_candidates": 0,  # Blobs considered for splitting
        "n_splits": 0,      # Blobs actually split
        "n_new_regions": 0, # Total new regions created
        "split_labels": set(),  # Labels that came from watershed splitting
    }
    if emit_diagnostics:
        _watershed_stats["diagnostics"] = []

    if apply_watershed and min_split_area_cells > 0 and h_maxima_h > 0:
        current_max = int(labeled.max())
        if current_max > 0:
            new_labeled = labeled.copy()

            # Determine expected penguin area for "likely merged" threshold
            _expected_area = expected_penguin_area_cells if expected_penguin_area_cells else min_split_area_cells
            _merge_threshold = _expected_area * watershed_merge_threshold

            # Iterate over regions to split selectively
            for region in measure.regionprops(labeled):
                # Only consider blobs meeting minimum area requirement
                if region.area < min_split_area_cells:
                    continue

                # Selective trigger: only attempt split on "likely merged" blobs
                # A blob is "likely merged" if its area exceeds the expected single-penguin area
                # by a threshold factor (default 1.5x)
                likely_merged_score = region.area / max(_expected_area, 1)
                if region.area < _merge_threshold:
                    continue

                _watershed_stats["n_candidates"] += 1

                minr, minc, maxr, maxc = region.bbox
                submask = labeled[minr:maxr, minc:maxc] == region.label
                # Markers via h-maxima on HAG within region
                sub_hag = hag[minr:maxr, minc:maxc]
                maxima = morphology.h_maxima(sub_hag, h=h_maxima_h)
                maxima = maxima & submask
                markers, _ = ndi.label(maxima)
                # Need at least 2 markers to split
                if markers.max() < 2:
                    if emit_diagnostics:
                        _watershed_stats["diagnostics"].append({
                            "original_label": int(region.label),
                            "area_cells": int(region.area),
                            "n_markers": int(markers.max()),
                            "n_new_regions": 0,
                            "action": "kept",
                        })
                    continue
                ws = watershed(-sub_hag, markers=markers, mask=submask, connectivity=connectivity)
                # Relabel watershed result with global indices
                ws_mask = ws > 0
                if not np.any(ws_mask):
                    continue
                # Map local labels to globally unique labels.
                # Note: label ids must be unique across *all* regions, even if they are disjoint;
                # otherwise scikit-image treats same-id pixels as one region (even when disconnected).
                unique_ws = np.unique(ws[ws_mask])
                n_new = len(unique_ws)
                label_map = {int(l): int(i + current_max + 1) for i, l in enumerate(unique_ws)}
                current_max += n_new
                patch = new_labeled[minr:maxr, minc:maxc]
                # Clear the original region
                patch[submask] = 0
                # Write new labels
                mapped = np.zeros_like(ws, dtype=int)
                for l, gid in label_map.items():
                    mapped[ws == l] = gid
                patch[ws_mask] = mapped[ws_mask]

                # Track statistics
                _watershed_stats["n_splits"] += 1
                _watershed_stats["n_new_regions"] += n_new
                # Track which labels came from splitting
                _watershed_stats["split_labels"].update(label_map.values())

                if emit_diagnostics:
                    _watershed_stats["diagnostics"].append({
                        "original_label": int(region.label),
                        "area_cells": int(region.area),
                        "n_markers": int(markers.max()),
                        "n_new_regions": n_new,
                        "action": "split",
                    })

            labeled = new_labeled
    count = 0
    dets: List[Dict] = []
    accepted_labels: set[int] = set()
    props = measure.regionprops(labeled, intensity_image=hag)
    for region in props:
        area = region.area
        if area < min_area_cells or area > max_area_cells:
            continue
        # Basic compactness: area vs bbox
        minr, minc, maxr, maxc = region.bbox
        # Border trim to avoid edge artifacts
        if border_trim_px and (
            minr <= border_trim_px or minc <= border_trim_px or
            (labeled.shape[0] - maxr) <= border_trim_px or (labeled.shape[1] - maxc) <= border_trim_px
        ):
            continue
        bbox_area = (maxr - minr) * (maxc - minc)
        if bbox_area == 0:
            continue
        fill_ratio = area / bbox_area
        if fill_ratio < 0.1:  # discard very elongated/noisy
            continue
        # Shape features
        perim = max(region.perimeter, 1e-6)
        circularity = float(4.0 * np.pi * area / (perim * perim))
        solidity = float(region.solidity)
        if circularity < circularity_min or solidity < solidity_min:
            continue
        # Terrain gating by slope at centroid
        if slope is not None and slope_max_deg is not None:
            cy, cx = region.centroid
            sy = min(max(int(round(cy)), 0), slope.shape[0]-1)
            sx = min(max(int(round(cx)), 0), slope.shape[1]-1)
            if slope[sy, sx] > slope_max_deg:
                continue
        count += 1
        accepted_labels.add(int(region.label))
        det: Dict = {"label": int(region.label), "row": float(region.centroid[0]), "col": float(region.centroid[1]),
                     "area_cells": int(area), "circularity": circularity, "solidity": solidity,
                     "hag_mean": float(region.mean_intensity), "hag_max": float(region.max_intensity)}
        # Map coordinates if available
        if cell_res is not None and mins is not None:
            x = float(mins[0] + (det["col"] + 0.5) * cell_res)
            y = float(mins[1] + (det["row"] + 0.5) * cell_res)
            det.update({"x": x, "y": y, "area_m2": float(area) * (cell_res ** 2)})
        dets.append(det)
    # Keep only accepted regions in the label image so QC plots match the returned detections/count.
    if accepted_labels:
        keep = np.zeros(int(labeled.max()) + 1, dtype=bool)
        keep[list(accepted_labels)] = True
        labeled = np.where(keep[labeled], labeled, 0)
    else:
        labeled = np.zeros_like(labeled)
    return count, labeled, dets, _watershed_stats


def save_plot(hag: np.ndarray, labeled: np.ndarray, out_png: Path, title: str,
              cell_res: float, hag_min: float, hag_max: float,
              min_area_cells: int, max_area_cells: int, det_count: int,
              fixed_vmin: Optional[float] = None,
              fixed_vmax: Optional[float] = None) -> None:
    """Save a QC visualization PNG showing the HAG heatmap with detection overlays.

    Detections are rendered as semi-transparent fill regions with cyan outlines
    and numbered centroid markers.  A text panel shows grid parameters and
    detection count.  Color scale can be fixed across tiles via *fixed_vmin*
    and *fixed_vmax* for visual consistency.
    """
    if not MATPLOTLIB_AVAILABLE:
        return
    out_png.parent.mkdir(parents=True, exist_ok=True)
    import numpy.ma as ma
    import matplotlib as mpl
    from skimage.measure import regionprops
    fig, ax = plt.subplots(figsize=(10, 7))

    # Base HAG heatmap with intuitive ramp (low=blue → high=red)
    # Consistent color scale across tiles if fixed bounds provided
    if fixed_vmin is None:
        fixed_vmin = 0.0
    if fixed_vmax is None:
        vmax_est = float(np.nanpercentile(hag, 99)) if np.isfinite(hag).any() else 1.0
        fixed_vmax = max(vmax_est, hag_max)
    norm = mpl.colors.Normalize(vmin=fixed_vmin, vmax=fixed_vmax)
    # Muted base layer for clarity
    im = ax.imshow(hag, cmap="Greys", norm=norm, origin="lower", interpolation="none")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Height above ground (m)")
    ax.set_title(title)

    # Detection overlay: semi‑transparent fill + thin outline + id dots
    det_mask = (labeled > 0)
    if det_mask.any():
        overlay = ma.masked_where(~det_mask, det_mask)
        ax.imshow(overlay, cmap="autumn", alpha=0.25, interpolation="none", origin="lower")
        # High-contrast cyan outlines
        try:
            ax.contour(det_mask, levels=[0.5], colors="#00FFFF", linewidths=0.8)
        except Exception:
            pass
        # Labels at centroids
        props = regionprops(labeled)
        for i, rp in enumerate(props, start=1):
            cy, cx = rp.centroid  # row, col
            ax.plot(cx, cy, marker="o", markersize=2.2, color="#00FFFF")
            if i <= 400:  # avoid over‑cluttering in very dense scenes
                ax.text(cx+1, cy+1, str(i), fontsize=4, color="black",
                        bbox=dict(boxstyle='round,pad=0.1', fc='white', ec='none', alpha=0.6))

    # QA panel (ties back to JSON)
    panel = (
        f"Grid: {cell_res:.2f} m\n"
        f"HAG range: {hag_min:.2f}–{hag_max:.2f} m\n"
        f"Region area: {min_area_cells}–{max_area_cells} cells\n"
        f"Detections: {det_count}"
    )
    ax.text(0.01, 0.01, panel, transform=ax.transAxes, fontsize=8,
            va='bottom', ha='left', color='white',
            bbox=dict(facecolor='black', alpha=0.5, boxstyle='round,pad=0.3'))

    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(out_png, dpi=220)
    plt.close(fig)


def save_hag_only(hag: np.ndarray, out_png: Path, title: str,
                  fixed_vmin: Optional[float] = None,
                  fixed_vmax: Optional[float] = None) -> None:
    """Save HAG heatmap only with legend (no detections)."""
    if not MATPLOTLIB_AVAILABLE:
        return
    out_png.parent.mkdir(parents=True, exist_ok=True)
    import matplotlib as mpl
    fig, ax = plt.subplots(figsize=(10, 7))
    if fixed_vmin is None:
        fixed_vmin = 0.0
    if fixed_vmax is None:
        vmax_est = float(np.nanpercentile(hag, 99)) if np.isfinite(hag).any() else 1.0
        fixed_vmax = max(0.5, vmax_est)
    norm = mpl.colors.Normalize(vmin=fixed_vmin, vmax=fixed_vmax)
    im = ax.imshow(hag, cmap="Greys", norm=norm, origin="lower", interpolation="none")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Height above ground (m)")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_png, dpi=220)
    plt.close(fig)


def _apply_classifier(
    classifier: Dict,
    blob_features: List[BlobFeatures],
    detections: List[Dict],
    top_n: int = 3,
) -> None:
    """Apply trained classifier to blob features, updating detections in-place.

    Args:
        classifier: Loaded classifier dict (from train_blob_classifier.py)
        blob_features: List of BlobFeatures for this tile
        detections: List of detection dicts to update with probability/top_features
        top_n: Number of top contributing features to report
    """
    if not blob_features or not detections:
        return

    model = classifier.get("model")
    scaler = classifier.get("scaler")
    feature_names = classifier.get("feature_names", [])

    if model is None or scaler is None or not feature_names:
        return

    # Build feature matrix from blob features
    # Map detection_id to detection dict for fast lookup
    det_by_id = {d["id"]: d for d in detections if "id" in d}

    for feat in blob_features:
        if feat.detection_id not in det_by_id:
            continue

        # Extract feature values in the expected order
        feature_values = []
        for fname in feature_names:
            val = getattr(feat, fname, None)
            if val is None:
                val = 0.0
            feature_values.append(float(val))

        X = np.array([feature_values])
        try:
            X_scaled = scaler.transform(X)
            prob = float(model.predict_proba(X_scaled)[0, 1])

            # Compute feature contributions for explanation
            contributions = X_scaled[0] * model.coef_[0]
            top_indices = np.argsort(np.abs(contributions))[::-1][:top_n]
            top_feature_names = [feature_names[j] for j in top_indices]
            top_feature_values = [round(contributions[j], 3) for j in top_indices]

            explanation = "; ".join([
                f"{name}={val:+.2f}"
                for name, val in zip(top_feature_names, top_feature_values)
            ])

            # Update detection
            det = det_by_id[feat.detection_id]
            det["probability"] = round(prob, 4)
            det["top_features"] = explanation

        except Exception:
            # Skip this detection if inference fails
            continue


def process_file(las_path: Path,
                 cell_res: float,
                 hag_min: float,
                 hag_max: float,
                 min_area_cells: int,
                 max_area_cells: int,
                 chunk_size: int,
                 verbose: bool,
                 plots_dir: Optional[Path],
                 fixed_vmin: Optional[float] = None,
                 fixed_vmax: Optional[float] = None,
                 ground_method: str = "min",
                 top_method: str = "max",
                 top_zscore_cap: Optional[float] = None,
                 top_quantile_lr: float = 0.05,
                 refine_grid_pct: Optional[float] = None,
                 refine_size: int = 3,
                 se_radius_m: float = 0.15,
                 circularity_min: float = 0.2,
                 solidity_min: float = 0.7,
                 slope_max_deg: Optional[float] = None,
                 border_trim_px: int = 0,
                 apply_watershed: bool = False,
                 h_maxima_h: float = 0.05,
                 min_split_area_cells: int = 12,
                 watershed_merge_threshold: float = 1.5,
                 emit_watershed_diagnostics: bool = False,
                 connectivity: int = 2,
                 emit_geojson_path: Optional[Path] = None,
                 geojson_crs: Optional[Dict[str, object]] = None,
                 geojson_coord_units: str = "meters",
                 geojson_wgs84: bool = False,
                 strict_outputs: bool = False,
                 max_grid_mb: Optional[float] = None,
                 skip_oversized_tiles: bool = False,
                 extract_intensity: bool = False,
                 extract_features: bool = False,
                 compute_confidence: bool = False,
                 density_stats: bool = False,
                 ground_quantile_max_memory_gb: float = 2.0,
                 csf_cloth_resolution: float = 0.5,
                 csf_class_threshold: float = 0.3,
                 csf_max_points: int = 20_000_000,
                 emit_dtm_dir: Optional[Path] = None,
                 dtm_crs: Optional[Dict[str, object]] = None,
                 emit_hag_surfaces_dir: Optional[Path] = None,
                 emit_blob_features: bool = False,
                 classifier_model: Optional[Dict] = None,
                 emit_dtm_quality: bool = False) -> Dict:
    """Process a single LAS/LAZ tile: build DEM, compute HAG, detect candidates.

    Orchestrates the full per-tile pipeline (ground DEM → HAG grid → detection →
    optional intensity/confidence enrichment → optional GeoJSON/plot output) and
    returns a summary dict with detection count, timing, grid metadata, and the
    list of detection records.
    """
    if verbose:
        print(f"Processing {las_path.name} ...", flush=True)
    import time as _t
    t0 = _t.time()
    try:
        mins, maxs, _ = read_bounds_and_counts(las_path, chunk_size)
    except Exception as e:
        msg = f"Failed to read bounds for {las_path.name}: {e}"
        print(f"WARNING: {msg}", file=sys.stderr)
        return {"path": str(las_path), "count": 0, "error": msg}
    ny, nx = _grid_shape(mins, maxs, cell_res)
    if max_grid_mb is not None:
        est_bytes = _estimate_grid_bytes(ny, nx, ground_method, top_method, slope_max_deg, density_stats=density_stats)
        est_mb = est_bytes / (1024 ** 2)
        if est_mb > float(max_grid_mb):
            msg = (
                f"Tile grid too large: estimated {est_mb:.1f} MB exceeds max-grid-mb {float(max_grid_mb):.1f} MB."
            )
            if skip_oversized_tiles:
                print(f"WARNING: Skipping {las_path.name}: {msg}", file=sys.stderr)
                return {
                    "path": str(las_path),
                    "count": 0,
                    "skipped": True,
                    "error": msg,
                    "grid_shape": [int(ny), int(nx)],
                    "cell_res": cell_res,
                    "hag_min": hag_min,
                    "hag_max": hag_max,
                }
            raise RuntimeError(f"{las_path.name}: {msg}")
    _count_grid: Optional[np.ndarray] = None
    if density_stats or emit_dtm_quality:
        _count_grid = np.zeros((ny, nx), dtype=np.int32)
    _csf_meta: Optional[Dict] = None
    _actual_ground_method = ground_method
    if ground_method == "csf":
        csf_dem, csf_info = _build_ground_csf(
            las_path, cell_res, ny, nx, mins,
            csf_cloth_resolution=csf_cloth_resolution,
            csf_class_threshold=csf_class_threshold,
            csf_max_points=csf_max_points,
            verbose=verbose,
        )
        _csf_meta = csf_info
        if csf_dem.size == 0:
            # CSF fallback: use p05 instead
            _actual_ground_method = "p05"
        else:
            # CSF succeeded; build meta and optionally populate count grid
            dem = csf_dem
            meta = {"mins": mins.tolist(), "maxs": maxs.tolist(), "cell_res": cell_res, "shape": [int(ny), int(nx)]}
            # Count grid still needs a streaming pass if requested
            if density_stats and _count_grid is not None:
                for x, y, z in _stream_points(las_path, chunk_size):
                    ix, iy, mask = _bin_indices(x, y, mins, cell_res, ny, nx)
                    flat = (iy * nx + ix)
                    if flat.size:
                        np.add.at(_count_grid.ravel(), flat, 1)
    if ground_method != "csf" or _actual_ground_method != ground_method:
        dem, meta = build_ground_dem(
            las_path,
            cell_res,
            chunk_size,
            verbose,
            ground_method=_actual_ground_method if _actual_ground_method != ground_method else ground_method,
            bounds=(mins, maxs),
            count_grid=_count_grid,
            quantile_max_memory_gb=float(ground_quantile_max_memory_gb),
        )
        if isinstance(meta, dict):
            _actual_ground_method = str(meta.get("ground_method_actual", _actual_ground_method))
    # Build HAG surface for detection
    # IMPORTANT: Output flags (emit_hag_surfaces) must NOT affect detection results
    if top_method.lower() == "p95":
        # Use histogram-based percentile (memory-efficient)
        hag = build_hag_grid_histogram_percentile(
            las_path,
            dem,
            meta,
            chunk_size,
            percentile=95.0,
        )
    elif top_method.lower() == "p95-exact":
        # Use two-pass exact percentile
        hag = build_hag_grid_exact_percentile(
            las_path,
            dem,
            meta,
            chunk_size,
            percentile=95.0,
        )
    else:
        # Use streaming method (max or p95-online)
        hag = build_hag_grid(
            las_path,
            dem,
            meta,
            chunk_size,
            top_method=top_method,
            top_zscore_cap=top_zscore_cap,
            top_quantile_lr=top_quantile_lr,
        )

    # Optional multi-surface HAG output (computed separately, doesn't affect detection)
    _hag_surfaces: Optional[Dict[str, np.ndarray]] = None
    if emit_hag_surfaces_dir is not None:
        # Build all surfaces in a single streaming pass
        _hag_surfaces = build_hag_multi_surface(
            las_path,
            dem,
            meta,
            chunk_size,
        )

    # Optional DTM raster output
    if emit_dtm_dir is not None:
        dtm_path = emit_dtm_dir / f"{las_path.stem}_dtm.tif"
        dtm_err = _write_geotiff(
            dem,
            dtm_path,
            np.array(meta["mins"]),
            cell_res,
            dtm_crs,
            nodata=np.nan,
        )
        if dtm_err:
            if "rasterio not available" in dtm_err:
                if verbose:
                    print(f"    DTM output skipped: {dtm_err}", file=sys.stderr)
            else:
                print(f"WARNING: DTM write failed for {las_path.name}: {dtm_err}", file=sys.stderr)

    # Optional multi-surface HAG raster output
    if emit_hag_surfaces_dir is not None and _hag_surfaces is not None:
        surface_names = ["max", "p95", "p90", "p50", "mean", "std"]
        for surface_name in surface_names:
            surface_arr = _hag_surfaces.get(surface_name)
            if surface_arr is None:
                continue
            surface_path = emit_hag_surfaces_dir / f"{las_path.stem}_hag_{surface_name}.tif"
            surface_err = _write_geotiff(
                surface_arr,
                surface_path,
                np.array(meta["mins"]),
                cell_res,
                dtm_crs,
                nodata=np.nan,
            )
            if surface_err:
                if "rasterio not available" in surface_err:
                    if verbose:
                        print(f"    HAG surface output skipped: {surface_err}", file=sys.stderr)
                    break  # Don't repeat warning for each surface
                else:
                    print(f"WARNING: HAG {surface_name} write failed for {las_path.name}: {surface_err}", file=sys.stderr)

    # Optional slope (degrees) from ground surface for terrain gating
    slope_arr: Optional[np.ndarray] = None
    if slope_max_deg is not None:
        gy, gx = np.gradient(dem, cell_res, cell_res)
        slope_rad = np.arctan(np.hypot(gx, gy))
        slope_arr = np.degrees(slope_rad).astype(np.float32)

    # Feature enrichment pass — build per-cell grids for intensity, RGB, return count, z_std
    do_enrichment = extract_features or extract_intensity
    _want_z_std = emit_blob_features or extract_features
    enrichment_grids: Dict[str, Optional[np.ndarray]] = {}
    if do_enrichment or _want_z_std:
        enrichment_grids = _build_enrichment_grids(
            las_path, chunk_size,
            mins=np.array(meta["mins"]),
            cell_res=cell_res, ny=ny, nx=nx,
            include_intensity=do_enrichment,
            include_rgb=extract_features,
            include_returns=extract_features,
            include_z_std=_want_z_std,
            verbose=verbose,
        )

    count, labeled, dets, _watershed_stats = detect_penguins_from_hag(
        hag, hag_min, hag_max, min_area_cells, max_area_cells,
        smooth_sigma=0.0, connectivity=connectivity,
        slope=slope_arr, slope_max_deg=slope_max_deg,
        cell_res=cell_res, mins=np.array(meta["mins"]),
        refine_grid_pct=refine_grid_pct,
        refine_size=refine_size,
        se_radius_m=se_radius_m,
        circularity_min=circularity_min,
        solidity_min=solidity_min,
        apply_watershed=apply_watershed,
        h_maxima_h=h_maxima_h,
        min_split_area_cells=min_split_area_cells,
        border_trim_px=border_trim_px,
        watershed_merge_threshold=watershed_merge_threshold,
        emit_diagnostics=emit_watershed_diagnostics,
    )

    # Enrich detections with features from enrichment grids
    if dets and do_enrichment:
        # Intensity (mean/min/max per blob — existing behavior)
        igrid = enrichment_grids.get("intensity")
        if igrid is not None:
            intensity_props = measure.regionprops(labeled, intensity_image=igrid)
            label_to_intensity = {}
            for rp in intensity_props:
                label_to_intensity[rp.label] = {
                    "intensity_mean": float(rp.mean_intensity),
                    "intensity_min": float(rp.min_intensity),
                    "intensity_max": float(rp.max_intensity),
                }
            for d in dets:
                lbl = d.get("label")
                if lbl in label_to_intensity:
                    d.update(label_to_intensity[lbl])

        # RGB mean per blob (one regionprops call per channel)
        for grid_key, det_key in [("rgb_r", "rgb_r_mean"), ("rgb_g", "rgb_g_mean"), ("rgb_b", "rgb_b_mean")]:
            grid = enrichment_grids.get(grid_key)
            if grid is not None:
                rgb_props = measure.regionprops(labeled, intensity_image=grid)
                label_to_val = {rp.label: float(rp.mean_intensity) for rp in rgb_props}
                for d in dets:
                    lbl = d.get("label")
                    if lbl in label_to_val:
                        d[det_key] = label_to_val[lbl]

        # Single-return fraction per blob (mean of per-cell fractions)
        srf_grid = enrichment_grids.get("single_return_fraction")
        if srf_grid is not None:
            srf_props = measure.regionprops(labeled, intensity_image=srf_grid)
            label_to_srf = {rp.label: float(rp.mean_intensity) for rp in srf_props}
            for d in dets:
                lbl = d.get("label")
                if lbl in label_to_srf:
                    d["single_return_fraction"] = label_to_srf[lbl]

    # HAG height profile per blob (std dev of HAG within each detection)
    if dets and extract_features:
        from scipy.ndimage import labeled_comprehension
        det_labels = [d["label"] for d in dets]
        hag_stds = labeled_comprehension(hag, labeled, det_labels, np.std, float, 0.0)
        for d, std_val in zip(dets, hag_stds):
            d["hag_std"] = float(std_val)

    # Optional confidence scoring
    if compute_confidence and dets:
        compute_confidence_scores(dets, cell_res=cell_res)

    dt = _t.time() - t0

    # Stable ordering + stable IDs (per-tile) for downstream joins and reproducibility.
    dets.sort(key=lambda d: (float(d.get("x", 0.0)), float(d.get("y", 0.0)), int(d.get("area_cells", 0))))
    for i, d in enumerate(dets, start=1):
        d.setdefault("tile", las_path.stem)
        d.setdefault("id", f"{las_path.stem}:{i:05d}")
        d.setdefault("file", str(las_path))

    # Optional comprehensive blob feature extraction
    # IMPORTANT: Extract AFTER detection sorting so IDs align with output JSON
    _blob_features: Optional[List[BlobFeatures]] = None
    if emit_blob_features and count > 0:
        # Create mapping from region label to detection ID
        label_to_det_id = {d["label"]: d["id"] for d in dets if "label" in d}

        _blob_features = extract_blob_features(
            labeled,
            hag,
            cell_res,
            np.array(meta["mins"]),
            tile_name=las_path.stem,
            intensity_grid=enrichment_grids.get("intensity") if do_enrichment else None,
            rgb_r_grid=enrichment_grids.get("rgb_r") if do_enrichment else None,
            rgb_g_grid=enrichment_grids.get("rgb_g") if do_enrichment else None,
            rgb_b_grid=enrichment_grids.get("rgb_b") if do_enrichment else None,
            point_count_grid=_count_grid,
            single_return_grid=enrichment_grids.get("single_return_fraction") if do_enrichment else None,
            normalize_spectral=True,
            split_labels=_watershed_stats.get("split_labels"),
            z_std_grid=enrichment_grids.get("z_std"),
        )

        # Update blob feature IDs to match detection IDs
        for feat in _blob_features:
            if feat.label in label_to_det_id:
                feat.detection_id = label_to_det_id[feat.label]

        # Apply classifier if model provided
        if classifier_model is not None:
            _apply_classifier(classifier_model, _blob_features, dets)

    # Also apply classifier if no blob features but classifier_model provided
    # (need to extract features on demand for classifier inference)
    elif classifier_model is not None and count > 0:
        # Extract minimal blob features for classification only
        label_to_det_id = {d["label"]: d["id"] for d in dets if "label" in d}
        _temp_features = extract_blob_features(
            labeled,
            hag,
            cell_res,
            np.array(meta["mins"]),
            tile_name=las_path.stem,
            intensity_grid=enrichment_grids.get("intensity") if do_enrichment else None,
            rgb_r_grid=enrichment_grids.get("rgb_r") if do_enrichment else None,
            rgb_g_grid=enrichment_grids.get("rgb_g") if do_enrichment else None,
            rgb_b_grid=enrichment_grids.get("rgb_b") if do_enrichment else None,
            point_count_grid=_count_grid,
            single_return_grid=enrichment_grids.get("single_return_fraction") if do_enrichment else None,
            normalize_spectral=True,
            split_labels=_watershed_stats.get("split_labels"),
            z_std_grid=enrichment_grids.get("z_std"),
        )
        for feat in _temp_features:
            if feat.label in label_to_det_id:
                feat.detection_id = label_to_det_id[feat.label]
        _apply_classifier(classifier_model, _temp_features, dets)

    info = {
        "path": str(las_path),
        "count": int(count),
        "time_s": float(dt),
        "grid_shape": list(hag.shape),
        "cell_res": cell_res,
        "hag_min": hag_min,
        "hag_max": hag_max,
        "detections": dets,
    }

    # Store blob features for aggregation if extracted
    if _blob_features is not None:
        info["_blob_features"] = _blob_features  # Internal, not serialized to JSON
    # Record actual ground method used (may differ from requested if CSF fell back)
    if _actual_ground_method != ground_method:
        info["ground_method_requested"] = ground_method
        info["ground_method_actual"] = _actual_ground_method
    if isinstance(meta, dict) and "ground_quantile" in meta:
        info["ground_quantile"] = meta["ground_quantile"]
    # Optional CSF metadata (separate sub-object, outside _stable_signature scope)
    if _csf_meta is not None:
        info["csf"] = _csf_meta
    # Optional density stats (separate sub-object, outside _stable_signature scope)
    if density_stats and _count_grid is not None:
        total_points = int(np.sum(_count_grid))
        n_cells_total = int(ny) * int(nx)
        tile_area_m2 = n_cells_total * (cell_res ** 2)
        empty_cells = int(np.sum(_count_grid == 0))
        occupied = _count_grid[_count_grid > 0]
        info["density"] = {
            "total_points": total_points,
            "density_pts_per_m2": round(total_points / max(tile_area_m2, 1e-6), 2),
            "mean_pts_per_cell": round(float(np.mean(_count_grid)), 2),
            "pct_empty_cells": round(100.0 * empty_cells / max(n_cells_total, 1), 2),
            "min_pts_per_cell": int(np.min(_count_grid)),
            "max_pts_per_cell": int(np.max(_count_grid)),
        }
        if occupied.size > 0:
            info["density"]["mean_pts_per_occupied_cell"] = round(float(np.mean(occupied)), 2)

    # Optional DTM quality metrics
    if emit_dtm_quality and _count_grid is not None:
        from pipelines.dtm_quality import compute_dtm_quality_metrics
        info["dtm_quality"] = compute_dtm_quality_metrics(dem, _count_grid, cell_res)

    # Watershed statistics (if any splitting was attempted)
    if apply_watershed and _watershed_stats.get("n_candidates", 0) > 0:
        info["watershed"] = {
            "enabled": True,
            "h_maxima_h": h_maxima_h,
            "min_split_area_cells": min_split_area_cells,
            "n_candidates": _watershed_stats["n_candidates"],
            "n_splits": _watershed_stats["n_splits"],
            "n_new_regions": _watershed_stats["n_new_regions"],
            "split_rate": round(_watershed_stats["n_splits"] / max(_watershed_stats["n_candidates"], 1), 3),
        }
    elif apply_watershed:
        info["watershed"] = {
            "enabled": True,
            "h_maxima_h": h_maxima_h,
            "min_split_area_cells": min_split_area_cells,
            "n_candidates": 0,
            "n_splits": 0,
            "n_new_regions": 0,
        }
    # Append watershed diagnostics if collected
    if emit_watershed_diagnostics and "diagnostics" in _watershed_stats:
        if "watershed" not in info:
            info["watershed"] = {"enabled": apply_watershed}
        info["watershed"]["diagnostics"] = _watershed_stats["diagnostics"]

    if emit_geojson_path is not None and dets:
        out_crs = geojson_crs
        coord_units = geojson_coord_units
        transformer = None
        source_crs = None
        if geojson_wgs84:
            if geojson_crs is None:
                msg = "GeoJSON WGS84 output requested but CRS not provided; writing projected coordinates."
                print(f"WARNING: {msg}", file=sys.stderr)
                info["geojson_transform_error"] = msg
            else:
                try:
                    import pyproj
                    if "wkt" in geojson_crs:
                        crs_in = pyproj.CRS.from_wkt(str(geojson_crs["wkt"]))
                    elif "epsg" in geojson_crs:
                        crs_in = pyproj.CRS.from_epsg(int(geojson_crs["epsg"]))
                    else:
                        crs_in = pyproj.CRS.from_user_input(geojson_crs)
                    transformer = pyproj.Transformer.from_crs(
                        crs_in, pyproj.CRS.from_epsg(4326), always_xy=True
                    )
                    out_crs = {"epsg": 4326}
                    coord_units = "degrees"
                    source_crs = geojson_crs
                except Exception as e:
                    msg = f"GeoJSON WGS84 transform unavailable: {e}. Writing projected coordinates."
                    print(f"WARNING: {msg}", file=sys.stderr)
                    info["geojson_transform_error"] = msg
        geojson_error = _write_geojson(
            dets,
            emit_geojson_path,
            out_crs,
            coord_units,
            transformer=transformer,
            source_crs=source_crs,
        )
        if geojson_error:
            print(f"WARNING: GeoJSON write failed for {emit_geojson_path}: {geojson_error}", file=sys.stderr)
            info["geojson_error"] = geojson_error
            if strict_outputs:
                raise RuntimeError(f"GeoJSON write failed for {emit_geojson_path}: {geojson_error}")
        else:
            info["geojson"] = str(emit_geojson_path)
    if plots_dir is not None:
        # Save HAG-only first (use global fixed color bounds if available via closure)
        png_before = plots_dir / f"{las_path.stem}_hag.png"
        try:
            save_hag_only(hag, png_before, f"{las_path.name} – HAG (m)", fixed_vmin=fixed_vmin, fixed_vmax=fixed_vmax)
            info["plot_hag"] = str(png_before)
        except Exception as e:
            info["plot_hag_error"] = str(e)
        # Save HAG + detections
        png = plots_dir / f"{las_path.stem}_hag_detect.png"
        try:
            save_plot(hag, labeled, png, f"{las_path.name}: {count} candidates",
                      cell_res, hag_min, hag_max, min_area_cells, max_area_cells, count,
                      fixed_vmin=fixed_vmin, fixed_vmax=fixed_vmax)
            info["plot"] = str(png)
        except Exception as e:
            info["plot_error"] = str(e)
    if verbose:
        print(f"    -> count={count} time={dt:.1f}s", flush=True)
    return info


def _validate_params(args: argparse.Namespace) -> None:
    """Validate all CLI parameters beyond the hag_min/hag_max and area checks.

    Collects all violations and reports them together via SystemExit so the
    user can fix everything in one pass.
    """
    errors: list[str] = []

    if args.cell_res <= 0:
        errors.append(f"cell_res must be > 0, got {args.cell_res}")
    if args.chunk_size <= 0:
        errors.append(f"chunk_size must be > 0, got {args.chunk_size}")
    if args.hag_min < 0:
        errors.append(f"hag_min must be >= 0, got {args.hag_min}")
    if args.se_radius_m < 0:
        errors.append(f"se_radius_m must be >= 0, got {args.se_radius_m}")
    if args.border_trim_px < 0:
        errors.append(f"border_trim_px must be >= 0, got {args.border_trim_px}")
    if not (0 <= args.circularity_min <= 1):
        errors.append(f"circularity_min must be in [0, 1], got {args.circularity_min}")
    if not (0 <= args.solidity_min <= 1):
        errors.append(f"solidity_min must be in [0, 1], got {args.solidity_min}")
    if args.refine_grid_pct is not None and not (0 < args.refine_grid_pct <= 100):
        errors.append(f"refine_grid_pct must be in (0, 100], got {args.refine_grid_pct}")
    if args.slope_max_deg is not None and not (0 < args.slope_max_deg < 90):
        errors.append(f"slope_max_deg must be in (0, 90), got {args.slope_max_deg}")
    if args.dedupe_radius_m is not None and args.dedupe_radius_m <= 0:
        errors.append(f"dedupe_radius_m must be > 0, got {args.dedupe_radius_m}")
    if args.max_grid_mb <= 0:
        errors.append(f"max_grid_mb must be > 0, got {args.max_grid_mb}")
    if args.ground_quantile_max_memory_gb <= 0:
        errors.append(
            "ground_quantile_max_memory_gb must be > 0, "
            f"got {args.ground_quantile_max_memory_gb}"
        )
    if args.h_maxima <= 0:
        errors.append(f"h_maxima must be > 0, got {args.h_maxima}")
    aoi_area_tolerance_pct = float(getattr(args, "aoi_area_tolerance_pct", 5.0))
    if aoi_area_tolerance_pct <= 0:
        errors.append(
            f"aoi_area_tolerance_pct must be > 0, got {aoi_area_tolerance_pct}"
        )

    if errors:
        raise SystemExit("Parameter validation failed:\n  " + "\n  ".join(errors))


def _write_effective_config(
    out_dir: Path,
    args: argparse.Namespace,
    crs_meta: Optional[Dict[str, object]],
    crs_source: str,
    input_files: List[Path],
) -> Path:
    """Write effective configuration artifact for reproducibility.

    Emits ``config.effective.json`` containing all resolved parameters
    (including defaults), CRS source information, and input file hashes.
    This enables any run to be replayed from the config + input data.

    Returns the path to the written config file.
    """
    import datetime

    # Compute input file hashes for provenance
    input_hashes = []
    for f in input_files:
        try:
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            input_hashes.append({
                "path": str(f),
                "sha256": h.hexdigest(),
                "size_bytes": f.stat().st_size,
            })
        except Exception as e:
            input_hashes.append({
                "path": str(f),
                "sha256": None,
                "error": str(e),
            })

    # Extract all parameters with their resolved values
    params = vars(args).copy()

    # Build effective config document
    config = {
        "schema_version": "1",
        "purpose": "effective_config",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "parameters": {
            # Core geometry
            "cell_res": params.get("cell_res"),
            "chunk_size": params.get("chunk_size"),
            # HAG window
            "hag_min": params.get("hag_min"),
            "hag_max": params.get("hag_max"),
            # Ground/top modeling
            "ground_method": params.get("ground_method"),
            "ground_quantile_max_memory_gb": params.get("ground_quantile_max_memory_gb"),
            "top_method": params.get("top_method"),
            "top_zscore_cap": params.get("top_zscore_cap"),
            "top_quantile_lr": params.get("top_quantile_lr"),
            # Candidate extraction
            "connectivity": params.get("connectivity"),
            "min_area_cells": params.get("min_area_cells"),
            "max_area_cells": params.get("max_area_cells"),
            # Morphology
            "refine_grid_pct": params.get("refine_grid_pct"),
            "refine_size": params.get("refine_size"),
            "se_radius_m": params.get("se_radius_m"),
            "circularity_min": params.get("circularity_min"),
            "solidity_min": params.get("solidity_min"),
            # Watershed
            "watershed": params.get("watershed"),
            "h_maxima": params.get("h_maxima"),
            "min_split_area_cells": params.get("min_split_area_cells"),
            # Terrain
            "border_trim_px": params.get("border_trim_px"),
            "slope_max_deg": params.get("slope_max_deg"),
            # Deduplication
            "dedupe_radius_m": params.get("dedupe_radius_m"),
            # CSF
            "csf_cloth_resolution": params.get("csf_cloth_resolution"),
            "csf_class_threshold": params.get("csf_class_threshold"),
            "csf_max_points": params.get("csf_max_points"),
            # File selection
            "exclude_dir": params.get("exclude_dir"),
            "skip_copc": params.get("skip_copc"),
            "only_las": params.get("only_las"),
            "max_grid_mb": params.get("max_grid_mb"),
        },
        "crs": {
            "resolved": crs_meta,
            "source": crs_source,
            "cli_epsg": params.get("crs_epsg"),
            "cli_wkt": params.get("crs_wkt"),
        },
        "inputs": {
            "data_root": str(params.get("data_root")),
            "n_files": len(input_files),
            "files": input_hashes,
        },
        "outputs": {
            "out": str(params.get("out")),
            "emit_geojson": params.get("emit_geojson"),
            "emit_csv": params.get("emit_csv"),
            "emit_gpkg": params.get("emit_gpkg"),
            "emit_dtm": params.get("emit_dtm"),
            "emit_hag_surfaces": params.get("emit_hag_surfaces"),
            "emit_blob_features": params.get("emit_blob_features"),
            "plots": params.get("plots"),
        },
        "feature_flags": {
            "extract_intensity": params.get("extract_intensity"),
            "extract_features": params.get("extract_features"),
            "compute_confidence": params.get("compute_confidence"),
            "density_stats": params.get("density_stats"),
        },
        "classifier": {
            "model_path": params.get("classifier_model"),
        },
    }

    config_path = out_dir / "config.effective.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return config_path


def _normalize_crs_code_for_compare(crs_meta: Optional[Dict[str, object]]) -> Optional[str]:
    """Normalize CRS metadata into a comparable code string."""
    if not isinstance(crs_meta, dict):
        return None
    epsg = crs_meta.get("epsg")
    if epsg is not None:
        try:
            return f"EPSG:{int(epsg)}"
        except (TypeError, ValueError):
            pass
    wkt = crs_meta.get("wkt")
    if isinstance(wkt, str) and wkt.strip():
        return wkt.strip()
    return None


def _write_run_manifest(path: Path, manifest: Dict[str, Any]) -> None:
    """Write run manifest JSON to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="LiDAR penguin detection via DEM+HAG")
    parser.add_argument("--data-root", required=True, help="Folder with LAS/LAZ files")
    parser.add_argument("--out", default="results/lidar_hag_counts.json", help="Output JSON path")
    parser.add_argument("--cell-res", type=float, default=0.25, help="DEM/HAG cell size in meters")
    parser.add_argument("--hag-min", type=float, default=0.2, help="Min HAG (m)")
    parser.add_argument("--hag-max", type=float, default=0.6, help="Max HAG (m)")
    parser.add_argument(
        "--ground-method",
        default="p05",
        choices=["min", "p05", "csf"],
        help=(
            "Ground DEM estimator per cell: p05 (default, exact percentile with memory guard), "
            "min (cell minimum), or csf (requires cloth-simulation-filter)"
        ),
    )
    parser.add_argument(
        "--ground-quantile-max-memory-gb",
        type=float,
        default=2.0,
        help=(
            "When --ground-method p05 is used, maximum memory budget (GB) for exact "
            "per-cell p05 computation. Falls back to min if exceeded."
        ),
    )
    parser.add_argument("--top-method", default="max", choices=["max","p95","p95-online","p95-exact"],
                        help="Top surface estimator per cell: max (default), p95 (histogram-based), p95-online (experimental online), p95-exact (two-pass exact percentile)")
    parser.add_argument("--top-zscore-cap", type=float, default=3.0, help="Z-score cap for top outliers")
    parser.add_argument("--top-quantile-lr", type=float, default=0.05, help="Learning rate for online p95 quantile")
    parser.add_argument("--connectivity", type=int, default=2, choices=[1,2], help="Connectivity for labeling (2 = 8-connected)")
    parser.add_argument("--emit-geojson", action="store_true", help="Write detections GeoJSON per tile")
    parser.add_argument("--crs-epsg", type=int, default=None, help="EPSG code for input XY CRS (projected)")
    parser.add_argument("--crs-wkt", default=None, help="WKT string for input XY CRS")
    parser.add_argument("--geojson-wgs84", action="store_true", help="Transform GeoJSON output to EPSG:4326 (requires CRS)")
    parser.add_argument(
        "--emit-gpkg",
        action="store_true",
        help="Write a GeoPackage with all detections in the input CRS (requires CRS + geopandas stack).",
    )
    parser.add_argument(
        "--gpkg-path",
        default=None,
        help="Optional GeoPackage output path (default: <out_dir>/lidar_hag_detections.gpkg)",
    )
    parser.add_argument(
        "--allow-unknown-crs",
        action="store_true",
        help="Allow GeoJSON output without CRS metadata (not recommended).",
    )
    parser.add_argument("--min-area-cells", type=int, default=2, help="Min region size in cells")
    parser.add_argument("--max-area-cells", type=int, default=80, help="Max region size in cells")
    parser.add_argument("--chunk-size", type=int, default=1000000, help="LAS chunk size for streaming")
    parser.add_argument("--plots", action="store_true", help="Save HAG map + detections PNG")
    parser.add_argument("--plots-global-scale", action="store_true", help="Use a global color scale across tiles")
    parser.add_argument("--plot-sample-n", type=int, default=20, help="Sample N tiles for global scale")
    parser.add_argument("--plot-vmax", type=float, default=None, help="Fixed vmax for global plot scaling")
    parser.add_argument("--emit-csv", action="store_true", help="Also write aggregated detections CSV alongside JSON summary")
    parser.add_argument("--csv-path", default=None, help="Optional CSV output path (default: results/lidar_hag_detections.csv)")
    parser.add_argument(
        "--emit-dtm",
        action="store_true",
        help="Write ground DTM as GeoTIFF per tile (requires rasterio; graceful skip if unavailable).",
    )
    parser.add_argument(
        "--emit-hag-surfaces",
        action="store_true",
        help="Write multiple HAG surface GeoTIFFs per tile: hag_max, hag_p95, hag_mean, hag_std (requires rasterio).",
    )
    parser.add_argument(
        "--emit-blob-features",
        action="store_true",
        help="Write comprehensive blob features to Parquet file (requires pandas/pyarrow).",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose progress")
    parser.add_argument(
        "--max-grid-mb",
        type=float,
        default=512.0,
        help="Fail (or skip with --skip-oversized-tiles) when a tile exceeds this grid memory estimate (MiB)",
    )
    parser.add_argument(
        "--skip-oversized-tiles",
        action="store_true",
        help="Skip tiles exceeding --max-grid-mb instead of failing the run (not recommended for final counts).",
    )
    parser.add_argument("--strict-outputs", action="store_true", help="Fail fast on GeoJSON/CSV output errors")
    parser.add_argument(
        "--official-reporting",
        action="store_true",
        help=(
            "Enable official reporting mode: enforce deterministic defaults, require dedupe "
            "for multi-tile runs, and fail on degraded conditions unless --allow-degraded."
        ),
    )
    parser.add_argument(
        "--allow-degraded",
        action="store_true",
        help="Allow official mode to complete even when run_status=DEGRADED.",
    )
    parser.add_argument(
        "--override-blocked-aoi",
        action="store_true",
        help="Override AOI registry BLOCKED status (recorded in manifest).",
    )
    parser.add_argument("--aoi-id", default=None, help="AOI identifier for registry/gating checks.")
    parser.add_argument(
        "--aoi-registry",
        default="manifests/aoi_registry.json",
        help="AOI registry JSON with status entries (default: manifests/aoi_registry.json).",
    )
    parser.add_argument(
        "--aoi-geojson",
        default=None,
        help="Optional AOI GeoJSON to validate CRS/area integrity (no geometry edits are performed).",
    )
    parser.add_argument(
        "--aoi-area-tolerance-pct",
        type=float,
        default=5.0,
        help="Tolerance for AOI property area vs computed area mismatch (percent).",
    )
    parser.add_argument(
        "--run-manifest-path",
        default=None,
        help="Optional run manifest output path (default: <out_dir>/lidar_run_manifest.json).",
    )
    # File selection filters
    parser.add_argument("--exclude-dir", action="append", default=[], help="Exclude any files within directories with this name (repeatable)")
    parser.add_argument("--skip-copc", action="store_true", help="Skip *.copc.laz files (COPC) when both COPC and LAS exist")
    parser.add_argument("--only-las", action="store_true", help="Process only .las files (ignore .laz)")
    # Optional refinement and morphology/shape thresholds
    parser.add_argument("--refine-grid-pct", type=float, default=None, help="Percentile for per-cell suppression (e.g., 90). Leave empty to disable.")
    parser.add_argument("--refine-size", type=int, default=3, help="Neighborhood size for refinement filter")
    parser.add_argument("--se-radius-m", type=float, default=0.15, help="Structuring element radius in meters for morphology")
    parser.add_argument("--circularity-min", type=float, default=0.2, help="Minimum circularity for candidates")
    parser.add_argument("--solidity-min", type=float, default=0.7, help="Minimum solidity for candidates")
    parser.add_argument("--watershed", action="store_true", help="Enable h-maxima + watershed splitting inside large blobs")
    parser.add_argument("--h-maxima", type=float, default=0.05, help="h parameter for h-maxima seed extraction (meters)")
    parser.add_argument("--min-split-area-cells", type=int, default=12, help="Only attempt watershed on blobs with at least this many cells")
    parser.add_argument("--watershed-merge-threshold", type=float, default=1.5, help="Area multiplier for 'likely merged' trigger (default 1.5x expected penguin area)")
    parser.add_argument("--emit-watershed-diagnostics", action="store_true", help="Include per-blob watershed split decisions in output JSON")
    parser.add_argument("--profile", default=None, choices=list(SENSOR_PROFILES.keys()),
                        help="Sensor profile for recommended parameters; warns if CLI values differ")
    parser.add_argument("--border-trim-px", type=int, default=0, help="Ignore detections closer than N pixels to any image edge")
    parser.add_argument("--slope-max-deg", type=float, default=None, help="Drop candidates where ground slope exceeds this many degrees")
    parser.add_argument("--dedupe-radius-m", type=float, default=None, help="If set, de-duplicate detections across tiles within this radius (meters)")
    parser.add_argument("--extract-intensity", action="store_true", help="Build per-cell mean intensity grid and add intensity features to detections")
    parser.add_argument("--extract-features", action="store_true",
                        help="Extract all available per-detection features: intensity (905nm), RGB color, "
                             "single-return fraction, and HAG height profile.  Superset of --extract-intensity.")
    parser.add_argument("--compute-confidence", action="store_true", help="Compute a [0,1] confidence score per detection based on HAG, area, and shape features")
    parser.add_argument("--classifier-model", type=str, default=None,
                        help="Path to trained blob classifier model (.pkl) for probability scoring")
    parser.add_argument("--density-stats", action="store_true", help="Compute per-tile point density statistics (total points, pts/m², empty cells, etc.)")
    parser.add_argument("--emit-dtm-quality", action="store_true", help="Compute DTM quality metrics per tile (roughness, support, coverage flags)")
    # CSF ground model options
    parser.add_argument("--csf-cloth-resolution", type=float, default=0.5, help="CSF cloth resolution (meters)")
    parser.add_argument("--csf-class-threshold", type=float, default=0.3, help="CSF classification threshold (meters)")
    parser.add_argument("--csf-max-points", type=int, default=20_000_000, help="Max points for CSF (fallback to p05 above this)")

    args = parser.parse_args()
    if args.hag_min >= args.hag_max:
        raise SystemExit("hag_min must be < hag_max")
    if args.min_area_cells >= args.max_area_cells:
        raise SystemExit("min_area_cells must be < max_area_cells")
    if args.ground_method == "csf" and not HAS_CSF:
        raise SystemExit("CSF not installed. Run: pip install cloth-simulation-filter")
    _validate_params(args)

    requested_ground_method = str(args.ground_method)
    requested_top_method = str(args.top_method)
    official_method_overrides: list[str] = []
    if args.official_reporting:
        if args.ground_method != OFFICIAL_DETERMINISTIC.ground_method:
            official_method_overrides.append(
                f"ground_method {args.ground_method}->{OFFICIAL_DETERMINISTIC.ground_method}"
            )
            args.ground_method = OFFICIAL_DETERMINISTIC.ground_method
        if args.top_method != OFFICIAL_DETERMINISTIC.top_method:
            official_method_overrides.append(
                f"top_method {args.top_method}->{OFFICIAL_DETERMINISTIC.top_method}"
            )
            args.top_method = OFFICIAL_DETERMINISTIC.top_method
        if official_method_overrides:
            print(
                "WARNING: official reporting enforced deterministic methods: "
                + ", ".join(official_method_overrides),
                file=sys.stderr,
            )

    # Profile validation: warn if CLI values differ from profile recommendations
    _active_profile = None
    if args.profile:
        _active_profile = SENSOR_PROFILES[args.profile]
        _profile_warnings = []
        if _active_profile.ground_method != args.ground_method:
            _profile_warnings.append(
                f"ground_method: CLI={args.ground_method}, profile={_active_profile.ground_method}"
            )
        if _active_profile.top_method != args.top_method:
            _profile_warnings.append(
                f"top_method: CLI={args.top_method}, profile={_active_profile.top_method}"
            )
        if _active_profile.h_maxima_h is not None and _active_profile.h_maxima_h != args.h_maxima:
            _profile_warnings.append(
                f"h_maxima: CLI={args.h_maxima}, profile={_active_profile.h_maxima_h}"
            )
        if _active_profile.min_split_area_cells is not None and _active_profile.min_split_area_cells != args.min_split_area_cells:
            _profile_warnings.append(
                f"min_split_area_cells: CLI={args.min_split_area_cells}, profile={_active_profile.min_split_area_cells}"
            )
        if _active_profile.watershed_merge_threshold is not None and _active_profile.watershed_merge_threshold != args.watershed_merge_threshold:
            _profile_warnings.append(
                f"watershed_merge_threshold: CLI={args.watershed_merge_threshold}, profile={_active_profile.watershed_merge_threshold}"
            )
        if _profile_warnings:
            print(f"WARNING: CLI parameters differ from profile '{args.profile}':", file=sys.stderr)
            for w in _profile_warnings:
                print(f"  {w}", file=sys.stderr)

    data_root = Path(args.data_root).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not LASPY_AVAILABLE:
        raise SystemExit("laspy not available; install with `pip install laspy`.")

    files = find_lidar_files(data_root)
    # Apply selection filters
    if args.exclude_dir:
        excl = set(args.exclude_dir)
        files = [f for f in files if not any((part in excl) for part in f.parts)]
    if args.skip_copc:
        files = [f for f in files if not f.name.lower().endswith('.copc.laz')]
    if args.only_las:
        files = [f for f in files if f.suffix.lower() == '.las']
    if args.verbose:
        print(f"Found {len(files)} LAS/LAZ files under {data_root}")

    plots_dir = out_path.parent / "lidar_hag_plots" if args.plots else None
    det_geojson_dir = out_path.parent / "lidar_hag_geojson" if args.emit_geojson else None
    if det_geojson_dir is not None:
        det_geojson_dir.mkdir(parents=True, exist_ok=True)
    dtm_dir = out_path.parent / "lidar_hag_dtm" if args.emit_dtm else None
    if dtm_dir is not None:
        dtm_dir.mkdir(parents=True, exist_ok=True)
    hag_surfaces_dir = out_path.parent / "lidar_hag_surfaces" if args.emit_hag_surfaces else None
    if hag_surfaces_dir is not None:
        hag_surfaces_dir.mkdir(parents=True, exist_ok=True)

    # CRS resolution: explicit CLI arg > auto-detect from LAS headers > None
    crs_meta = _crs_meta_from_args(args.crs_epsg, args.crs_wkt)
    crs_mismatch_detected = False
    autodetected_crs: Optional[Dict[str, object]] = None
    if crs_meta is None and files:
        autodetected_crs = _autodetect_crs_from_files(files)
        if autodetected_crs is not None:
            crs_meta = autodetected_crs
            if args.verbose:
                epsg_str = str(autodetected_crs.get("epsg", "unknown"))
                print(f"CRS auto-detected from LAS headers: EPSG:{epsg_str}", flush=True)
    elif crs_meta is not None and files:
        # Check for mismatch between CLI arg and auto-detected CRS
        autodetected_crs = _autodetect_crs_from_files(files)
        if autodetected_crs is not None:
            cli_epsg = crs_meta.get("epsg")
            auto_epsg = autodetected_crs.get("epsg")
            if cli_epsg is not None and auto_epsg is not None and int(cli_epsg) != int(auto_epsg):
                crs_mismatch_detected = True
                print(
                    f"WARNING: CLI CRS (EPSG:{cli_epsg}) differs from auto-detected CRS "
                    f"(EPSG:{auto_epsg}). Using CLI value.",
                    file=sys.stderr,
                )
    coord_units = "meters"
    if args.emit_geojson or args.emit_gpkg:
        if args.geojson_wgs84 and crs_meta is None:
            raise SystemExit("--geojson-wgs84 requires --crs-epsg or --crs-wkt.")
        if crs_meta is None and not args.allow_unknown_crs:
            raise SystemExit(
                "--emit-geojson requires CRS metadata. Provide --crs-epsg/--crs-wkt or pass --allow-unknown-crs."
            )
        if args.emit_gpkg and crs_meta is None:
            raise SystemExit("--emit-gpkg requires --crs-epsg or --crs-wkt.")
        if crs_meta is None and args.allow_unknown_crs:
            print(
                "WARNING: CRS not provided; GeoJSON coordinates are projected meters with unknown CRS.",
                file=sys.stderr,
            )

    # Determine CRS source for provenance
    crs_source = "cli" if autodetected_crs is None and crs_meta is not None else (
        "autodetect" if autodetected_crs is not None and _crs_meta_from_args(args.crs_epsg, args.crs_wkt) is None else "cli"
    )

    manifest_path = (
        Path(args.run_manifest_path).resolve()
        if args.run_manifest_path
        else (out_path.parent / "lidar_run_manifest.json")
    )
    degraded_reasons: list[str] = []
    run_warnings: list[str] = []
    blocked_reasons: list[str] = []

    aoi_registry_path = Path(args.aoi_registry).resolve()
    aoi_registry: Dict[str, Dict[str, Any]] = {}
    aoi_registry_error: Optional[str] = None
    try:
        aoi_registry = load_aoi_registry(aoi_registry_path)
    except Exception as exc:
        aoi_registry_error = str(exc)
        run_warnings.append(
            f"Failed to load AOI registry {aoi_registry_path}: {aoi_registry_error}"
        )

    aoi_registry_entry: Optional[Dict[str, Any]] = None
    if args.aoi_id:
        aoi_registry_entry = lookup_aoi_registry_entry(aoi_registry, str(args.aoi_id))
        if aoi_registry_entry is None:
            msg = f"AOI id '{args.aoi_id}' not found in AOI registry {aoi_registry_path}"
            run_warnings.append(msg)
            if args.official_reporting:
                degraded_reasons.append(msg)
        else:
            aoi_status = str(aoi_registry_entry.get("status", "UNKNOWN")).upper()
            if aoi_status == "BLOCKED":
                reason = str(aoi_registry_entry.get("reason") or "No reason recorded")
                since = str(aoi_registry_entry.get("blocked_since") or "unknown date")
                block_msg = (
                    f"AOI '{args.aoi_id}' is BLOCKED since {since}: {reason}"
                )
                if args.override_blocked_aoi:
                    run_warnings.append(f"AOI block override used: {block_msg}")
                elif args.official_reporting:
                    blocked_reasons.append(block_msg)
                else:
                    run_warnings.append(block_msg)
    elif args.official_reporting:
        blocked_reasons.append(
            "Official reporting requires --aoi-id to trace AOI authority and block status."
        )

    expected_crs_for_aoi = _normalize_crs_code_for_compare(crs_meta)
    aoi_integrity: Optional[Dict[str, Any]] = None
    if args.aoi_geojson:
        aoi_geojson_path = Path(args.aoi_geojson).resolve()
        if not aoi_geojson_path.exists():
            msg = f"AOI GeoJSON not found: {aoi_geojson_path}"
            degraded_reasons.append(msg)
        else:
            try:
                aoi_integrity = check_aoi_integrity(
                    aoi_geojson=aoi_geojson_path,
                    expected_crs=expected_crs_for_aoi,
                    area_property_tolerance_pct=float(args.aoi_area_tolerance_pct),
                )
                for warn in aoi_integrity.get("warnings", []) or []:
                    run_warnings.append(str(warn))
                for issue in aoi_integrity.get("issues", []) or []:
                    degraded_reasons.append(str(issue))
            except Exception as exc:
                degraded_reasons.append(f"AOI integrity validation failed: {exc}")

    if crs_mismatch_detected:
        degraded_reasons.append(
            "CLI CRS differs from LAS auto-detected CRS; verify CRS authority before reporting."
        )

    dedupe_required_multi_tile = bool(args.official_reporting and len(files) > 1)
    if dedupe_required_multi_tile and args.dedupe_radius_m is None:
        blocked_reasons.append(
            "Official reporting requires --dedupe-radius-m for multi-tile runs."
        )

    run_manifest: Dict[str, Any] = {
        "schema_version": "1",
        "purpose": "lidar_run_manifest",
        "generated_at_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "official_reporting": bool(args.official_reporting),
        "run_status": "PENDING",
        "degraded_reasons": [],
        "warnings": [],
        "blocked_reasons": [],
        "parameters": vars(args).copy(),
        "git": collect_git_context(_ROOT),
        "inputs": {
            "data_root": str(data_root),
            "tile_count": int(len(files)),
            "tile_list": [str(p) for p in files],
        },
        "methods": {
            "ground_method_requested": requested_ground_method,
            "ground_method_effective": str(args.ground_method),
            "top_method_requested": requested_top_method,
            "top_method_effective": str(args.top_method),
            "official_method_overrides": official_method_overrides,
            "dedupe_radius_m": args.dedupe_radius_m,
            "dedupe_required_multi_tile": dedupe_required_multi_tile,
        },
        "crs": {
            "resolved": crs_meta,
            "source": crs_source,
            "autodetected": autodetected_crs,
            "mismatch_detected": bool(crs_mismatch_detected),
        },
        "aoi": {
            "aoi_id": args.aoi_id,
            "registry_path": str(aoi_registry_path),
            "registry_entry": aoi_registry_entry,
            "registry_error": aoi_registry_error,
            "aoi_geojson": str(Path(args.aoi_geojson).resolve()) if args.aoi_geojson else None,
            "integrity": aoi_integrity,
            "override_blocked_aoi": bool(args.override_blocked_aoi),
        },
        "overrides": {
            "allow_degraded": bool(args.allow_degraded),
            "override_blocked_aoi": bool(args.override_blocked_aoi),
        },
    }

    if blocked_reasons:
        run_manifest["run_status"] = "BLOCKED"
        run_manifest["blocked_reasons"] = blocked_reasons
        run_manifest["warnings"] = run_warnings
        _write_run_manifest(manifest_path, run_manifest)
        raise SystemExit("Official reporting blocked:\n  " + "\n  ".join(blocked_reasons))

    if degraded_reasons and args.official_reporting and not args.allow_degraded:
        run_manifest["run_status"] = "DEGRADED"
        run_manifest["degraded_reasons"] = degraded_reasons
        run_manifest["warnings"] = run_warnings
        _write_run_manifest(manifest_path, run_manifest)
        raise SystemExit(
            "Official reporting refused degraded preflight. "
            "Pass --allow-degraded to continue.\n  "
            + "\n  ".join(degraded_reasons)
        )

    summary = {
        "schema_version": "1",
        "purpose": LIDAR_CANDIDATES_PURPOSE,
        "contract": LIDAR_CANDIDATES_CONTRACT,
        "policy": as_policy_dict(),
        "crs": crs_meta,
        "crs_source": crs_source,
        "coord_units": coord_units,
        "data_root": str(data_root),
        "params": vars(args).copy(),
        "official_reporting": bool(args.official_reporting),
        "official_profile": OFFICIAL_DETERMINISTIC.name if args.official_reporting else None,
        "aoi_id": args.aoi_id,
        "run_manifest": str(manifest_path),
        "run_status": "OK",
        "degraded_reasons": [],
        "warnings": [],
        "files": [],
        "total_count": 0,
    }
    if _active_profile is not None:
        summary["profile"] = {
            "name": _active_profile.name,
            "notes": _active_profile.notes,
        }
    if run_warnings:
        summary["warnings"] = list(run_warnings)
    if degraded_reasons:
        summary["run_status"] = "DEGRADED"
        summary["degraded_reasons"] = list(degraded_reasons)
    summary["aoi_registry"] = {
        "path": str(aoi_registry_path),
        "entry": aoi_registry_entry,
        "error": aoi_registry_error,
    }
    if aoi_integrity is not None:
        summary["aoi_integrity"] = aoi_integrity

    # Write effective config artifact for reproducibility
    effective_config_path = _write_effective_config(
        out_path.parent,
        args,
        crs_meta,
        crs_source,
        files,
    )
    summary["effective_config"] = str(effective_config_path)

    # Optional: compute global color bounds for consistent plotting across tiles
    global_vmin: Optional[float] = None
    global_vmax: Optional[float] = None
    use_global_scale = bool(args.plots_global_scale or args.plot_vmax is not None)
    if plots_dir is not None and use_global_scale:
        global_vmin = 0.0
        if args.plot_vmax is not None:
            global_vmax = float(args.plot_vmax)
        else:
            vmax_samples: List[float] = []
            sample_n = int(args.plot_sample_n)
            if sample_n <= 0 or len(files) <= sample_n:
                sample_files = files
            else:
                idxs = np.linspace(0, len(files) - 1, sample_n, dtype=int)
                sample_files = [files[i] for i in idxs]
            for f_tmp in sample_files:
                try:
                    mins_tmp, maxs_tmp, _ = read_bounds_and_counts(f_tmp, args.chunk_size)
                    ny_tmp, nx_tmp = _grid_shape(mins_tmp, maxs_tmp, args.cell_res)
                    if args.max_grid_mb is not None:
                        est_bytes = _estimate_grid_bytes(
                            ny_tmp, nx_tmp, args.ground_method, args.top_method, args.slope_max_deg,
                            density_stats=args.density_stats,
                        )
                        est_mb = est_bytes / (1024 ** 2)
                        if est_mb > float(args.max_grid_mb):
                            print(
                                f"WARNING: Skipping plot scale prepass for {f_tmp.name} "
                                f"(estimated {est_mb:.1f} MB > max-grid-mb {float(args.max_grid_mb):.1f}).",
                                file=sys.stderr,
                            )
                            continue
                    dem_tmp, meta_tmp = build_ground_dem(
                        f_tmp, args.cell_res, args.chunk_size, verbose=False, ground_method=args.ground_method,
                        bounds=(mins_tmp, maxs_tmp),
                    )
                    hag_tmp = build_hag_grid(
                        f_tmp,
                        dem_tmp,
                        meta_tmp,
                        args.chunk_size,
                        top_method=args.top_method,
                        top_zscore_cap=args.top_zscore_cap,
                        top_quantile_lr=args.top_quantile_lr,
                    )
                    if np.isfinite(hag_tmp).any():
                        vmax_samples.append(float(np.nanpercentile(hag_tmp, 99)))
                except Exception:
                    continue
            if vmax_samples:
                global_vmax = max(float(np.median(vmax_samples)), float(args.hag_max))
            else:
                global_vmax = float(args.hag_max)

    # Load classifier model if provided
    _classifier_model: Optional[Dict] = None
    if args.classifier_model:
        classifier_path = Path(args.classifier_model)
        if not classifier_path.exists():
            print(f"WARNING: Classifier model not found: {classifier_path}", file=sys.stderr)
        else:
            try:
                import pickle
                with open(classifier_path, "rb") as clf_f:
                    _classifier_model = pickle.load(clf_f)
                if args.verbose:
                    print(f"Loaded classifier model from {classifier_path}")
                    if "top_features" in _classifier_model:
                        print(f"  Top features: {_classifier_model['top_features']}")
            except Exception as e:
                print(f"WARNING: Failed to load classifier model: {e}", file=sys.stderr)

    all_detections: list[dict] = []
    file_errors: list[dict] = []
    for f in files:
        geojson_path = None
        if det_geojson_dir is not None:
            geojson_path = det_geojson_dir / f"{f.stem}_detections.geojson"
        try:
            info = process_file(
                f,
                cell_res=args.cell_res,
                hag_min=args.hag_min,
                hag_max=args.hag_max,
                min_area_cells=args.min_area_cells,
                max_area_cells=args.max_area_cells,
                chunk_size=args.chunk_size,
                verbose=args.verbose,
                plots_dir=plots_dir,
                fixed_vmin=global_vmin,
                fixed_vmax=global_vmax,
                ground_method=args.ground_method,
                top_method=args.top_method,
                top_zscore_cap=args.top_zscore_cap,
                top_quantile_lr=args.top_quantile_lr,
                refine_grid_pct=args.refine_grid_pct,
                refine_size=args.refine_size,
                se_radius_m=args.se_radius_m,
                circularity_min=args.circularity_min,
                solidity_min=args.solidity_min,
                apply_watershed=args.watershed,
                h_maxima_h=args.h_maxima,
                min_split_area_cells=args.min_split_area_cells,
                watershed_merge_threshold=args.watershed_merge_threshold,
                emit_watershed_diagnostics=args.emit_watershed_diagnostics,
                border_trim_px=args.border_trim_px,
                slope_max_deg=args.slope_max_deg,
                connectivity=args.connectivity,
                emit_geojson_path=geojson_path,
                geojson_crs=crs_meta,
                geojson_coord_units=coord_units,
                geojson_wgs84=args.geojson_wgs84,
                strict_outputs=args.strict_outputs,
                max_grid_mb=args.max_grid_mb,
                skip_oversized_tiles=args.skip_oversized_tiles,
                extract_intensity=args.extract_intensity,
                extract_features=args.extract_features,
                compute_confidence=args.compute_confidence,
                density_stats=args.density_stats,
                ground_quantile_max_memory_gb=args.ground_quantile_max_memory_gb,
                csf_cloth_resolution=args.csf_cloth_resolution,
                csf_class_threshold=args.csf_class_threshold,
                csf_max_points=args.csf_max_points,
                emit_dtm_dir=dtm_dir,
                dtm_crs=crs_meta,
                emit_hag_surfaces_dir=hag_surfaces_dir,
                emit_blob_features=args.emit_blob_features,
                classifier_model=_classifier_model,
                emit_dtm_quality=args.emit_dtm_quality,
            )
        except Exception as exc:
            msg = f"Failed to process {f.name}: {exc}"
            print(f"ERROR: {msg}", file=sys.stderr)
            info = {"path": str(f), "count": 0, "error": msg}
            file_errors.append({"file": str(f), "error": str(exc)})
        summary["files"].append(info)
        summary["total_count"] += int(info.get("count", 0))
        # Collect detection records for optional batch-level de-duplication
        for d in info.get("detections", []) or []:
            if "x" in d and "y" in d and d.get("id"):
                all_detections.append(d)
    if file_errors:
        summary["file_errors"] = file_errors

    fallback_tiles = collect_ground_quantile_fallbacks(summary["files"])
    if fallback_tiles:
        fallback_msg = (
            f"Ground p05 fallback to min occurred in {len(fallback_tiles)} tile(s)."
        )
        degraded_reasons.append(fallback_msg)
        summary["ground_quantile_fallback_tiles"] = fallback_tiles

    # Aggregate blob features from all tiles and write to Parquet
    if args.emit_blob_features:
        all_blob_features: List[BlobFeatures] = []
        for fi in summary["files"]:
            tile_features = fi.pop("_blob_features", None)
            if tile_features:
                all_blob_features.extend(tile_features)

        if all_blob_features:
            try:
                from pipelines.blob_features import features_to_parquet
                features_path = out_path.parent / "blob_features.parquet"
                features_to_parquet(all_blob_features, features_path)
                summary["blob_features"] = {
                    "path": str(features_path),
                    "n_features": len(all_blob_features),
                }
                if args.verbose:
                    print(f"Wrote {len(all_blob_features)} blob features to {features_path}")
            except ImportError as e:
                msg = f"Could not write blob features (missing pandas/pyarrow): {e}"
                print(f"WARNING: {msg}", file=sys.stderr)
                summary["blob_features_error"] = msg
            except Exception as e:
                msg = f"Error writing blob features: {e}"
                print(f"WARNING: {msg}", file=sys.stderr)
                summary["blob_features_error"] = msg

    # Cross-tile de-duplication (batch artifact + count)
    deduped: list[dict] | None = None
    dedupe_index: dict[str, dict] | None = None
    if args.dedupe_radius_m is not None:
        if all_detections:
            deduped, dedupe_index = _dedupe_detections(
                all_detections, radius_m=float(args.dedupe_radius_m)
            )
        else:
            deduped, dedupe_index = [], {}
        summary["dedupe_radius_m"] = float(args.dedupe_radius_m)
        summary["total_count_deduped"] = int(len(deduped))

        dedup_csv_path = out_path.parent / "lidar_hag_detections_deduped.csv"
        dedup_json_path = out_path.parent / "lidar_hag_detections_deduped.json"
        summary["dedupe_outputs"] = {"csv": str(dedup_csv_path), "json": str(dedup_json_path)}

        try:
            import csv as _csv

            fieldnames = [
                "id",
                "tile",
                "file",
                "x",
                "y",
                "area_m2",
                "area_cells",
                "hag_mean",
                "hag_max",
                "circularity",
                "solidity",
                "dedupe_cluster_id",
                "dedupe_cluster_size",
            ]
            with open(dedup_csv_path, "w", newline="") as cf:
                w = _csv.DictWriter(cf, fieldnames=fieldnames)
                w.writeheader()
                for d in deduped:
                    w.writerow({k: d.get(k) for k in fieldnames})
        except Exception as e:
            msg = str(e)
            print(f"WARNING: deduped CSV write failed: {msg}", file=sys.stderr)
            summary["dedupe_csv_error"] = msg
            if args.strict_outputs:
                raise

        try:
            payload = {
                "schema_version": "1",
                "purpose": "lidar_candidates_deduped",
                "contract": {
                    **LIDAR_CANDIDATES_CONTRACT,
                    "purpose": "lidar_candidates_deduped",
                    "semantic_unit": "candidate_deduped",
                    "notes": (
                        "De-duplication is centroid-distance clustering across the batch. "
                        "This reduces obvious cross-tile duplicates but is not an individual-count model."
                    ),
                },
                "crs": crs_meta,
                "coord_units": coord_units,
                "dedupe_radius_m": float(args.dedupe_radius_m),
                "total_count_deduped": int(len(deduped)),
                "detections": deduped,
                "dedupe_index": dedupe_index,
            }
            dedup_json_path.write_text(json.dumps(payload, indent=2))
        except Exception as e:
            msg = str(e)
            print(f"WARNING: deduped JSON write failed: {msg}", file=sys.stderr)
            summary["dedupe_json_error"] = msg
            if args.strict_outputs:
                raise

    # Optional GeoPackage output (projection-preserving GIS delivery)
    if args.emit_gpkg:
        gpkg_path = Path(args.gpkg_path) if args.gpkg_path else (out_path.parent / "lidar_hag_detections.gpkg")
        summary["gpkg"] = {"path": str(gpkg_path)}
        try:
            import geopandas as gpd  # type: ignore[import-not-found]

            if crs_meta is None:
                raise RuntimeError("Missing CRS metadata")

            if "epsg" in crs_meta and crs_meta["epsg"] is not None:
                crs = f"EPSG:{int(crs_meta['epsg'])}"
            elif "wkt" in crs_meta and crs_meta["wkt"]:
                crs = str(crs_meta["wkt"])
            else:
                raise RuntimeError("CRS metadata missing epsg/wkt")

            def to_gdf(rows: list[dict]) -> "gpd.GeoDataFrame":
                df = gpd.GeoDataFrame(rows)
                df["geometry"] = gpd.points_from_xy(df["x"].astype(float), df["y"].astype(float))
                df = df.set_crs(crs)
                return df

            # Write full detections layer.
            if all_detections:
                gdf = to_gdf(all_detections)
                gdf.to_file(gpkg_path, layer="detections", driver="GPKG")
                summary["gpkg"]["layers"] = ["detections"]

            # Write deduped layer if available.
            if deduped:
                gdf_d = to_gdf(deduped)
                gdf_d.to_file(gpkg_path, layer="detections_deduped", driver="GPKG")
                summary["gpkg"].setdefault("layers", []).append("detections_deduped")
        except Exception as e:
            msg = str(e)
            print(f"WARNING: GeoPackage write failed: {msg}", file=sys.stderr)
            summary["gpkg_error"] = msg
            if args.strict_outputs:
                raise

    reporting_counts: Dict[str, Any] = {
        "raw_total_count": int(summary["total_count"]),
        "deduped_total_count": int(len(deduped)) if deduped is not None else None,
        "official_total_count": None,
        "official_count_basis": None,
        "raw_label": "RAW",
        "deduped_label": "OFFICIAL" if args.official_reporting else "DEDUPED",
    }
    if args.official_reporting:
        if deduped is not None:
            reporting_counts["official_total_count"] = int(len(deduped))
            reporting_counts["official_count_basis"] = "deduped"
        else:
            reporting_counts["official_total_count"] = int(summary["total_count"])
            reporting_counts["official_count_basis"] = "raw_single_tile_no_dedupe"
    summary["reporting_counts"] = reporting_counts

    if degraded_reasons:
        summary["run_status"] = "DEGRADED"
        summary["degraded_reasons"] = list(dict.fromkeys(str(x) for x in degraded_reasons))
    else:
        summary["run_status"] = "OK"
        summary["degraded_reasons"] = []
    summary["warnings"] = list(dict.fromkeys(str(x) for x in summary.get("warnings", []) or []))

    # Optional aggregated detections CSV for client-friendly consumption
    if args.emit_csv:
        try:
            import csv as _csv
            rows: List[Dict] = []
            for fi in summary["files"]:
                # Use the per-tile LAS path for provenance (key is 'path' in process_file output)
                src = fi.get("path")
                for d in fi.get("detections", []) or []:
                    row = {"file": src, "tile": d.get("tile"), "id": d.get("id")}
                    row.update({k: d.get(k) for k in ("x","y","area_m2","hag_mean","hag_max","circularity","solidity","area_cells")})
                    rows.append(row)
            if rows:
                csv_path = Path(args.csv_path) if args.csv_path else (out_path.parent / "lidar_hag_detections.csv")
                with open(csv_path, "w", newline="") as cf:
                    writer = _csv.DictWriter(cf, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows)
        except Exception as e:
            msg = str(e)
            print(f"WARNING: CSV write failed: {msg}", file=sys.stderr)
            summary["csv_error"] = msg
            if args.strict_outputs:
                raise

    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)

    run_manifest["run_status"] = str(summary.get("run_status") or "OK")
    run_manifest["degraded_reasons"] = list(summary.get("degraded_reasons") or [])
    run_manifest["warnings"] = list(summary.get("warnings") or [])
    run_manifest["counts"] = reporting_counts
    run_manifest["outputs"] = {
        "summary_json": str(out_path),
        "effective_config": str(effective_config_path),
        "dedupe_outputs": summary.get("dedupe_outputs"),
        "gpkg": summary.get("gpkg"),
    }
    run_manifest["methods"]["dedupe_applied"] = bool(deduped is not None)
    run_manifest["methods"]["deduped_count"] = int(len(deduped)) if deduped is not None else None
    _write_run_manifest(manifest_path, run_manifest)

    print(json.dumps({"files": len(summary["files"]), "total_count": summary["total_count"]}, indent=2))
    # Write provenance with timing and params
    total_time_s = float(sum((fi.get("time_s", 0.0) for fi in summary["files"])) )
    write_provenance(out_path.parent, filename="provenance_lidar.json", extra={
        "script": "scripts/run_lidar_hag.py",
        "data_root": str(data_root),
        "params": summary["params"],
        "cli_args": vars(args),
        "timings": {
            "total_seconds": round(total_time_s, 3),
            "avg_seconds_per_file": round(total_time_s / max(1, len(summary["files"])), 3)
        },
    })
    append_timings(out_path.parent, component='lidar', timings={
        "total_seconds": round(total_time_s, 3),
        "avg_seconds_per_file": round(total_time_s / max(1, len(summary["files"])), 3)
    }, extra={"data_root": str(data_root), "n_files": len(summary["files"])})

    if args.official_reporting and summary.get("run_status") == "DEGRADED" and not args.allow_degraded:
        print(
            "ERROR: Official reporting run ended DEGRADED. "
            "Pass --allow-degraded to override.",
            file=sys.stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    main()
