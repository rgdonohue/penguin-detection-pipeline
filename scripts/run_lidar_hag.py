#!/usr/bin/env python3
"""
LiDAR penguin detection via DEM + Height-Above-Ground (HAG) analysis.

Pipeline per file:
- Stream LAS/LAZ to build a ground DEM (min Z) on a regular XY grid (cell size in meters)
- Stream again to compute HAG per cell (max Z - ground DEM)
- Detect penguin-like blobs: HAG within [hag_min, hag_max], small, compact regions
- Count connected components / peaks; write per-file counts + summary JSON; optional PNGs

Designed to avoid loading all points in memory; works on Python 3.13 without Open3D.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import time

# Add project src to path for consistency
import sys
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[1]
for p in [str(_ROOT / "src"), str(_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Optional plotting
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

# Image processing
from skimage import morphology, measure, filters
from skimage.segmentation import watershed
from scipy import ndimage as ndi
from scipy.ndimage import maximum_filter, percentile_filter
from scipy.spatial import cKDTree
from pipelines.utils.provenance import write_provenance, append_timings

# LAS streaming
try:
    import laspy  # type: ignore
    LASPY_AVAILABLE = True
except Exception:
    LASPY_AVAILABLE = False


def _is_sample_path(path: Path) -> bool:
    """Return True if any path component equals 'sample' (case-insensitive)."""
    return any(part.lower() == "sample" for part in path.parts)


def find_lidar_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for dp, _dns, fns in os.walk(root):
        for fn in fns:
            if Path(fn).suffix.lower() in {".las", ".laz"}:
                files.append(Path(dp) / fn)
    # Prefer non-sample duplicates by filename; keep first seen otherwise.
    sorted_files = sorted(files, key=lambda p: (_is_sample_path(p), str(p)))
    filtered: List[Path] = []
    seen_names: Dict[str, Path] = {}
    for path in sorted_files:
        key = path.name.lower()
        prior = seen_names.get(key)
        if prior is None:
            filtered.append(path)
            seen_names[key] = path
            continue
        # Only replace the prior path if it came from a 'sample' subdir and the new one does not.
        if _is_sample_path(prior) and not _is_sample_path(path):
            idx = filtered.index(prior)
            filtered[idx] = path
            seen_names[key] = path
    return filtered


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


def _stream_points(las_path: Path, chunk_size: int):
    with laspy.open(str(las_path)) as fh:  # type: ignore[attr-defined]
        if hasattr(fh, "chunk_iterator"):
            for pts in fh.chunk_iterator(chunk_size):  # type: ignore[attr-defined]
                x = np.asarray(pts.x, dtype=np.float64)
                y = np.asarray(pts.y, dtype=np.float64)
                z = np.asarray(pts.z, dtype=np.float64)
                if x.size:
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
                    yield x, y, z
                start += count


def _grid_shape(mins: np.ndarray, maxs: np.ndarray, cell_res: float) -> Tuple[int, int]:
    nx = int(np.ceil((maxs[0] - mins[0]) / cell_res)) + 1
    ny = int(np.ceil((maxs[1] - mins[1]) / cell_res)) + 1
    return ny, nx  # rows (y), cols (x)


def _bin_indices(x: np.ndarray, y: np.ndarray, mins: np.ndarray, cell_res: float, ny: int, nx: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    ix = np.floor((x - mins[0]) / cell_res).astype(np.int64)
    iy = np.floor((y - mins[1]) / cell_res).astype(np.int64)
    valid = (ix >= 0) & (iy >= 0) & (ix < nx) & (iy < ny)
    return ix[valid], iy[valid], valid


def _online_quantile_update(q: np.ndarray, x: np.ndarray, p: float, lr: float) -> None:
    """Online quantile tracker per cell. q and x are aligned arrays for cells seen in this chunk.
    q <- q + lr * sign * (x - q), where sign depends on whether x above/below q.
    """
    above = x > q
    # Move q toward x: small step weighted by desired quantile probability
    q[above] += lr * p * (x[above] - q[above])
    q[~above] -= lr * (1.0 - p) * (q[~above] - x[~above])


def build_ground_dem(las_path: Path, cell_res: float, chunk_size: int, verbose: bool,
                     ground_method: str = "min",
                     quantile_lr: float = 0.05) -> Tuple[np.ndarray, Dict]:
    mins, maxs, _ = read_bounds_and_counts(las_path, chunk_size)
    ny, nx = _grid_shape(mins, maxs, cell_res)
    dem = np.full((ny, nx), np.inf, dtype=np.float32)
    # For percentile ground: maintain online q05 per cell
    if ground_method.lower() != "min":
        q05 = np.full((ny, nx), np.nan, dtype=np.float32)
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
            np.minimum.at(dem_flat, flat, z_valid.astype(np.float32))
            # Online q05 update if enabled (bootstrap then track)
            if ground_method.lower() != "min":
                q05_flat = q05.ravel()
                idx = flat
                # initialize missing
                init_sel = np.isnan(q05_flat[idx])
                if np.any(init_sel):
                    q05_flat[idx[init_sel]] = z_valid.astype(np.float32)[init_sel]
                q_vals = q05_flat[idx]
                x_vals = z_valid.astype(np.float32)
                _online_quantile_update(q_vals, x_vals, p=0.05, lr=quantile_lr)
                q05_flat[idx] = q_vals

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

    # Choose ground surface
    if ground_method.lower() == "min":
        ground = dem
    else:
        # Fallback to dem where q05 is NaN
        ground = np.where(np.isnan(q05), dem, q05)
    meta = {"mins": mins.tolist(), "maxs": maxs.tolist(), "cell_res": cell_res, "shape": [int(ny), int(nx)]}
    return ground.astype(np.float32), meta


def build_hag_grid(las_path: Path, dem: np.ndarray, meta: Dict, chunk_size: int,
                   top_method: str = "max",
                   top_zscore_cap: Optional[float] = None) -> np.ndarray:
    mins = np.array(meta["mins"], dtype=float)
    cell_res = float(meta["cell_res"])
    ny, nx = dem.shape
    use_p95 = (str(top_method).lower() == "p95")
    hag = np.zeros_like(dem, dtype=np.float32)
    # Approximate per-cell p95 using online quantile tracking
    q95 = np.full_like(dem, np.nan, dtype=np.float32) if use_p95 else None
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
            if use_p95:
                q95_flat = q95.ravel()  # type: ignore[arg-type]
                # initialize missing
                init_sel = np.isnan(q95_flat[flat])
                if np.any(init_sel):
                    q95_flat[flat[init_sel]] = hag_chunk[init_sel]
                q_vals = q95_flat[flat]
                _online_quantile_update(q_vals, hag_chunk, p=0.95, lr=0.05)
                q95_flat[flat] = q_vals
            else:
                hag_flat = hag.ravel()
                np.maximum.at(hag_flat, flat, hag_chunk)
    # Finalize HAG surface
    if use_p95 and q95 is not None:
        hag = np.where(np.isnan(q95), hag, q95)
    if top_zscore_cap is not None and not use_p95:
        finite = np.isfinite(hag)
        if finite.any():
            mean = float(np.nanmean(hag[finite]))
            std = float(np.nanstd(hag[finite]))
            if std > 0:
                cap = mean + float(top_zscore_cap) * std
                hag = np.clip(hag, 0, cap, out=hag)
    # Ensure non-negative
    return np.clip(hag, 0, None)


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
                             emit_geojson_path: Optional[Path] = None,
                             refine_grid_pct: Optional[float] = None,
                             refine_size: int = 3,
                             se_radius_m: float = 0.15,
                             circularity_min: float = 0.2,
                             solidity_min: float = 0.7,
                             apply_watershed: bool = False,
                             h_maxima_h: float = 0.05,
                             min_split_area_cells: int = 12,
                             border_trim_px: int = 0) -> Tuple[int, np.ndarray, List[Dict]]:
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

    # Optional watershed split on large blobs only
    if apply_watershed and min_split_area_cells > 0 and h_maxima_h > 0:
        current_max = int(labeled.max())
        if current_max > 0:
            new_labeled = labeled.copy()
            # Iterate over regions to split selectively
            for region in measure.regionprops(labeled):
                if region.area < min_split_area_cells:
                    continue
                minr, minc, maxr, maxc = region.bbox
                submask = labeled[minr:maxr, minc:maxc] == region.label
                # Markers via h-maxima on HAG within region
                sub_hag = hag[minr:maxr, minc:maxc]
                maxima = morphology.h_maxima(sub_hag, h=h_maxima_h)
                maxima = maxima & submask
                markers, _ = ndi.label(maxima)
                # Need at least 2 markers to split
                if markers.max() < 2:
                    continue
                ws = watershed(-sub_hag, markers=markers, mask=submask, connectivity=connectivity)
                # Relabel watershed result with global indices
                ws_mask = ws > 0
                if not np.any(ws_mask):
                    continue
                # Map local labels to global unique labels
                unique_ws = np.unique(ws[ws_mask])
                label_map = {int(l): int(i + labeled.max() + 1) for i, l in enumerate(unique_ws)}
                # Clear the original region
                new_labeled[minr:maxr, minc:maxc][submask] = 0
                # Write new labels
                mapped = np.zeros_like(ws, dtype=int)
                for l, gid in label_map.items():
                    mapped[ws == l] = gid
                new_labeled[minr:maxr, minc:maxc] |= mapped
            labeled = new_labeled
    count = 0
    dets: List[Dict] = []
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
        det: Dict = {"row": float(region.centroid[0]), "col": float(region.centroid[1]),
                     "area_cells": int(area), "circularity": circularity, "solidity": solidity,
                     "hag_mean": float(region.mean_intensity), "hag_max": float(region.max_intensity)}
        # Map coordinates if available
        if cell_res is not None and mins is not None:
            x = float(mins[0] + (det["col"] + 0.5) * cell_res)
            y = float(mins[1] + (det["row"] + 0.5) * cell_res)
            det.update({"x": x, "y": y, "area_m2": float(area) * (cell_res ** 2)})
        dets.append(det)
    # Optional GeoJSON write
    if emit_geojson_path is not None and dets:
        try:
            feats = [{"type": "Feature",
                      "geometry": {"type": "Point", "coordinates": [d.get("x"), d.get("y")]},
                      "properties": {k: v for k, v in d.items() if k not in ("x", "y")}}
                     for d in dets if "x" in d and "y" in d]
            fc = {"type": "FeatureCollection", "features": feats}
            emit_geojson_path.parent.mkdir(parents=True, exist_ok=True)
            with open(emit_geojson_path, "w") as f:
                json.dump(fc, f)
        except Exception:
            pass
    return count, labeled, dets


def save_plot(hag: np.ndarray, labeled: np.ndarray, out_png: Path, title: str,
              cell_res: float, hag_min: float, hag_max: float,
              min_area_cells: int, max_area_cells: int, det_count: int,
              fixed_vmin: Optional[float] = None,
              fixed_vmax: Optional[float] = None) -> None:
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
                 top_method: str = "p95",
                 top_zscore_cap: Optional[float] = None,
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
                 connectivity: int = 2,
                 emit_geojson_path: Optional[Path] = None) -> Dict:
    if verbose:
        print(f"Processing {las_path.name} ...", flush=True)
    import time as _t
    t0 = _t.time()
    dem, meta = build_ground_dem(las_path, cell_res, chunk_size, verbose, ground_method=ground_method)
    hag = build_hag_grid(
        las_path,
        dem,
        meta,
        chunk_size,
        top_method=top_method,
        top_zscore_cap=top_zscore_cap,
    )
    # Optional slope (degrees) from ground surface for terrain gating
    slope_arr: Optional[np.ndarray] = None
    if slope_max_deg is not None:
        gy, gx = np.gradient(dem, cell_res, cell_res)
        slope_rad = np.arctan(np.hypot(gx, gy))
        slope_arr = np.degrees(slope_rad).astype(np.float32)
    count, labeled, dets = detect_penguins_from_hag(
        hag, hag_min, hag_max, min_area_cells, max_area_cells,
        smooth_sigma=0.0, connectivity=connectivity,
        slope=slope_arr, slope_max_deg=slope_max_deg,
        cell_res=cell_res, mins=np.array(meta["mins"]),
        emit_geojson_path=emit_geojson_path,
        refine_grid_pct=refine_grid_pct,
        refine_size=refine_size,
        se_radius_m=se_radius_m,
        circularity_min=circularity_min,
        solidity_min=solidity_min,
        apply_watershed=apply_watershed,
        h_maxima_h=h_maxima_h,
        min_split_area_cells=min_split_area_cells,
        border_trim_px=border_trim_px,
    )
    dt = _t.time() - t0
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


def main() -> None:
    parser = argparse.ArgumentParser(description="LiDAR penguin detection via DEM+HAG")
    parser.add_argument("--data-root", required=True, help="Folder with LAS/LAZ files")
    parser.add_argument("--out", default="results/lidar_hag_counts.json", help="Output JSON path")
    parser.add_argument("--cell-res", type=float, default=0.25, help="DEM/HAG cell size in meters")
    parser.add_argument("--hag-min", type=float, default=0.2, help="Min HAG (m)")
    parser.add_argument("--hag-max", type=float, default=0.6, help="Max HAG (m)")
    parser.add_argument("--ground-method", default="min", choices=["min","p05"], help="Ground DEM estimator per cell")
    parser.add_argument("--top-method", default="p95", choices=["max","p95"], help="Top surface estimator per cell (currently informational)")
    parser.add_argument("--top-zscore-cap", type=float, default=3.0, help="Z-score cap for top outliers")
    parser.add_argument("--connectivity", type=int, default=2, choices=[1,2], help="Connectivity for labeling (2 = 8-connected)")
    parser.add_argument("--emit-geojson", action="store_true", help="Write detections GeoJSON per tile")
    parser.add_argument("--min-area-cells", type=int, default=2, help="Min region size in cells")
    parser.add_argument("--max-area-cells", type=int, default=80, help="Max region size in cells")
    parser.add_argument("--chunk-size", type=int, default=1000000, help="LAS chunk size for streaming")
    parser.add_argument("--plots", action="store_true", help="Save HAG map + detections PNG")
    parser.add_argument("--emit-csv", action="store_true", help="Also write aggregated detections CSV alongside JSON summary")
    parser.add_argument("--csv-path", default=None, help="Optional CSV output path (default: results/lidar_hag_detections.csv)")
    parser.add_argument("--verbose", action="store_true", help="Verbose progress")
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
    parser.add_argument("--border-trim-px", type=int, default=0, help="Ignore detections closer than N pixels to any image edge")
    parser.add_argument("--slope-max-deg", type=float, default=None, help="Drop candidates where ground slope exceeds this many degrees")
    parser.add_argument("--dedupe-radius-m", type=float, default=None, help="If set, de-duplicate detections across tiles within this radius (meters)")

    args = parser.parse_args()

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

    summary = {
        "data_root": str(data_root),
        "params": {
            "cell_res": args.cell_res,
            "hag_min": args.hag_min,
            "hag_max": args.hag_max,
            "min_area_cells": args.min_area_cells,
            "max_area_cells": args.max_area_cells,
            "chunk_size": args.chunk_size,
        },
        "files": [],
        "total_count": 0,
    }

    # Optional: compute global color bounds for consistent plotting across tiles
    global_vmin: Optional[float] = 0.0
    global_vmax: Optional[float] = None
    if plots_dir is not None:
        vmax_samples: List[float] = []
        for f_tmp in files:
            try:
                dem_tmp, meta_tmp = build_ground_dem(f_tmp, args.cell_res, args.chunk_size, verbose=False)
                hag_tmp = build_hag_grid(f_tmp, dem_tmp, meta_tmp, args.chunk_size)
                if np.isfinite(hag_tmp).any():
                    vmax_samples.append(float(np.nanpercentile(hag_tmp, 99)))
            except Exception:
                continue
        if vmax_samples:
            global_vmax = max(float(np.median(vmax_samples)), float(args.hag_max))
        else:
            global_vmax = float(args.hag_max)

    all_xy: list[tuple[float, float]] = []
    for f in files:
        geojson_path = None
        if det_geojson_dir is not None:
            geojson_path = det_geojson_dir / f"{f.stem}_detections.geojson"
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
            refine_grid_pct=args.refine_grid_pct,
            refine_size=args.refine_size,
            se_radius_m=args.se_radius_m,
            circularity_min=args.circularity_min,
            solidity_min=args.solidity_min,
            apply_watershed=args.watershed,
            h_maxima_h=args.h_maxima,
            min_split_area_cells=args.min_split_area_cells,
            border_trim_px=args.border_trim_px,
            slope_max_deg=args.slope_max_deg,
            connectivity=args.connectivity,
            emit_geojson_path=geojson_path,
        )
        summary["files"].append(info)
        summary["total_count"] += int(info.get("count", 0))
        # Collect centroids if present
        for d in info.get("detections", []) or []:
            if "x" in d and "y" in d:
                all_xy.append((float(d["x"]), float(d["y"])) )

    # Cross-tile de-duplication
    if args.dedupe_radius_m and all_xy:
        pts = np.array(all_xy, dtype=np.float64)
        tree = cKDTree(pts)
        neighbors = tree.query_ball_point(pts, r=float(args.dedupe_radius_m))
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
        clusters = {int(find(i)) for i in range(pts.shape[0])}
        summary["dedupe_radius_m"] = float(args.dedupe_radius_m)
        summary["total_count_deduped"] = int(len(clusters))

    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)

    # Optional aggregated detections CSV for client-friendly consumption
    if args.emit_csv:
        try:
            import csv as _csv
            rows: List[Dict] = []
            for fi in summary["files"]:
                # Use the per-tile LAS path for provenance (key is 'path' in process_file output)
                src = fi.get("path")
                for d in fi.get("detections", []) or []:
                    row = {"file": src}
                    row.update({k: d.get(k) for k in ("x","y","area_m2","hag_mean","hag_max","circularity","solidity")})
                    rows.append(row)
            if rows:
                csv_path = Path(args.csv_path) if args.csv_path else (out_path.parent / "lidar_hag_detections.csv")
                with open(csv_path, "w", newline="") as cf:
                    writer = _csv.DictWriter(cf, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows)
        except Exception:
            pass

    print(json.dumps({"files": len(summary["files"]), "total_count": summary["total_count"]}, indent=2))
    # Write provenance with timing and params
    total_time_s = float(sum((fi.get("time_s", 0.0) for fi in summary["files"])) )
    write_provenance(out_path.parent, filename="provenance_lidar.json", extra={
        "script": "lidar_detect_penguins.py",
        "data_root": str(data_root),
        "params": summary["params"],
        "timings": {
            "total_seconds": round(total_time_s, 3),
            "avg_seconds_per_file": round(total_time_s / max(1, len(summary["files"])), 3)
        },
    })
    append_timings(out_path.parent, component='lidar', timings={
        "total_seconds": round(total_time_s, 3),
        "avg_seconds_per_file": round(total_time_s / max(1, len(summary["files"])), 3)
    }, extra={"data_root": str(data_root), "n_files": len(summary["files"])})


if __name__ == "__main__":
    main()
