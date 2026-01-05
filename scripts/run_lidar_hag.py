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
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
from pipelines.lidar_profiles import as_policy_dict

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


def _crs_meta_from_args(crs_epsg: Optional[int], crs_wkt: Optional[str]) -> Optional[Dict[str, object]]:
    if crs_epsg is None and not crs_wkt:
        return None
    meta: Dict[str, object] = {}
    if crs_epsg is not None:
        meta["epsg"] = int(crs_epsg)
    if crs_wkt:
        meta["wkt"] = str(crs_wkt)
    return meta


def _estimate_grid_bytes(
    ny: int,
    nx: int,
    ground_method: str,
    top_method: str,
    slope_max_deg: Optional[float],
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


def build_ground_dem(las_path: Path, cell_res: float, chunk_size: int, verbose: bool,
                     ground_method: str = "min",
                     quantile_lr: float = 0.05,
                     bounds: Optional[Tuple[np.ndarray, np.ndarray]] = None) -> Tuple[np.ndarray, Dict]:
    if bounds is None:
        mins, maxs, _ = read_bounds_and_counts(las_path, chunk_size)
    else:
        mins, maxs = bounds
        mins = np.array(mins, dtype=float)
        maxs = np.array(maxs, dtype=float)
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
            if ground_method.lower() != "min":
                q05_flat = q05.ravel()
                _online_quantile_update_indexed(
                    q05_flat,
                    flat,
                    z_valid.astype(np.float32),
                    p=0.05,
                    lr=quantile_lr,
                )

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
                   top_zscore_cap: Optional[float] = None,
                   top_quantile_lr: float = 0.05) -> np.ndarray:
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
                _online_quantile_update_indexed(q95_flat, flat, hag_chunk, p=0.95, lr=top_quantile_lr)
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
                # Map local labels to globally unique labels.
                # Note: label ids must be unique across *all* regions, even if they are disjoint;
                # otherwise scikit-image treats same-id pixels as one region (even when disconnected).
                unique_ws = np.unique(ws[ws_mask])
                label_map = {int(l): int(i + current_max + 1) for i, l in enumerate(unique_ws)}
                current_max += len(unique_ws)
                patch = new_labeled[minr:maxr, minc:maxc]
                # Clear the original region
                patch[submask] = 0
                # Write new labels
                mapped = np.zeros_like(ws, dtype=int)
                for l, gid in label_map.items():
                    mapped[ws == l] = gid
                patch[ws_mask] = mapped[ws_mask]
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
                 connectivity: int = 2,
                 emit_geojson_path: Optional[Path] = None,
                 geojson_crs: Optional[Dict[str, object]] = None,
                 geojson_coord_units: str = "meters",
                 geojson_wgs84: bool = False,
                 strict_outputs: bool = False,
                 max_grid_mb: Optional[float] = None,
                 skip_oversized_tiles: bool = False) -> Dict:
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
        est_bytes = _estimate_grid_bytes(ny, nx, ground_method, top_method, slope_max_deg)
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
    dem, meta = build_ground_dem(
        las_path,
        cell_res,
        chunk_size,
        verbose,
        ground_method=ground_method,
        bounds=(mins, maxs),
    )
    hag = build_hag_grid(
        las_path,
        dem,
        meta,
        chunk_size,
        top_method=top_method,
        top_zscore_cap=top_zscore_cap,
        top_quantile_lr=top_quantile_lr,
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

    # Stable ordering + stable IDs (per-tile) for downstream joins and reproducibility.
    dets.sort(key=lambda d: (float(d.get("x", 0.0)), float(d.get("y", 0.0)), int(d.get("area_cells", 0))))
    for i, d in enumerate(dets, start=1):
        d.setdefault("tile", las_path.stem)
        d.setdefault("id", f"{las_path.stem}:{i:05d}")
        d.setdefault("file", str(las_path))
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
    if args.hag_min >= args.hag_max:
        raise SystemExit("hag_min must be < hag_max")
    if args.min_area_cells >= args.max_area_cells:
        raise SystemExit("min_area_cells must be < max_area_cells")

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

    crs_meta = _crs_meta_from_args(args.crs_epsg, args.crs_wkt)
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

    summary = {
        "schema_version": "1",
        "purpose": LIDAR_CANDIDATES_PURPOSE,
        "contract": LIDAR_CANDIDATES_CONTRACT,
        "policy": as_policy_dict(),
        "crs": crs_meta,
        "coord_units": coord_units,
        "data_root": str(data_root),
        "params": vars(args).copy(),
        "files": [],
        "total_count": 0,
    }

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
                            ny_tmp, nx_tmp, args.ground_method, args.top_method, args.slope_max_deg
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

    all_detections: list[dict] = []
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
            top_quantile_lr=args.top_quantile_lr,
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
            geojson_crs=crs_meta,
            geojson_coord_units=coord_units,
            geojson_wgs84=args.geojson_wgs84,
            strict_outputs=args.strict_outputs,
            max_grid_mb=args.max_grid_mb,
            skip_oversized_tiles=args.skip_oversized_tiles,
        )
        summary["files"].append(info)
        summary["total_count"] += int(info.get("count", 0))
        # Collect detection records for optional batch-level de-duplication
        for d in info.get("detections", []) or []:
            if "x" in d and "y" in d and d.get("id"):
                all_detections.append(d)

    # Cross-tile de-duplication (batch artifact + count)
    deduped: list[dict] | None = None
    dedupe_index: dict[str, dict] | None = None
    if args.dedupe_radius_m and all_detections:
        deduped, dedupe_index = _dedupe_detections(all_detections, radius_m=float(args.dedupe_radius_m))
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


if __name__ == "__main__":
    main()
