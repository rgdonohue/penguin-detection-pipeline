"""
Derive AOI polygons from LiDAR coverage (lightweight, deterministic).

Primary use-case: extract a *max visible land footprint* AOI for an island survey
in a projected CRS (meters). This allows AOI-clipped evaluation without manual
digitizing when the AOI boundary is a natural closed form (e.g., shoreline).

Design constraints:
- Deterministic: no randomness; stable ordering of outputs.
- Lightweight: avoids heavyweight geo stacks (no shapely/geopandas required).
- CRS-safe: assumes inputs are already in the desired projected CRS.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
from scipy import ndimage as ndi
from skimage import measure, morphology
from skimage.filters import threshold_otsu

try:
    import laspy  # type: ignore

    LASPY_AVAILABLE = True
except Exception:  # pragma: no cover
    LASPY_AVAILABLE = False


@dataclass(frozen=True)
class AoiFromLidarParams:
    data_root: Path
    out_path: Path
    crs_epsg: int = 32720
    cell_res_m: float = 1.0
    chunk_size: int = 1_000_000
    min_points_per_cell: int = 1
    threshold_method: str = "fixed"  # fixed|otsu
    closing_radius_m: float = 2.0
    opening_radius_m: float = 1.0
    fill_holes: bool = True
    keep_largest_component: bool = True
    simplify_tolerance_m: Optional[float] = None
    # Optional: constrain the AOI extraction to a region-of-interest (ROI) in
    # the same projected CRS. This is useful when a dataset includes nearby
    # mainland; for islands we want the local footprint around the island.
    roi_from_detections: Optional[Path] = None
    roi_buffer_m: float = 0.0
    roi_bounds: Optional[Tuple[float, float, float, float]] = None  # xmin,ymin,xmax,ymax
    aoi_id: str = "aoi"
    properties: Dict[str, Any] = field(default_factory=dict)


def run(params: AoiFromLidarParams) -> Path:
    if not LASPY_AVAILABLE:
        raise RuntimeError("laspy not available; install requirements.txt (LiDAR stage deps).")
    data_root = Path(params.data_root)
    files = find_lidar_files(data_root)
    if not files:
        raise FileNotFoundError(f"No LAS/LAZ files found under {data_root}")

    selector_xy: Optional[Tuple[float, float]] = None
    if params.roi_from_detections is not None:
        selector_xy = _detections_centroid_xy(Path(params.roi_from_detections))

    if params.roi_bounds is not None:
        xmin, ymin, xmax, ymax = params.roi_bounds
        mins_xy = np.asarray([xmin, ymin], dtype=np.float64)
        maxs_xy = np.asarray([xmax, ymax], dtype=np.float64)
    elif params.roi_from_detections is not None and float(params.roi_buffer_m) > 0:
        mins_xy, maxs_xy = _roi_bounds_from_detections(
            Path(params.roi_from_detections),
            buffer_m=float(params.roi_buffer_m),
        )
    else:
        mins_xy, maxs_xy = _bounds_xy(files)

    counts = _density_grid(files, mins_xy, maxs_xy, params.cell_res_m, params.chunk_size)

    mask = _land_mask(
        counts,
        method=str(params.threshold_method),
        min_points_per_cell=int(params.min_points_per_cell),
    )
    mask = _clean_mask(
        mask,
        cell_res_m=float(params.cell_res_m),
        closing_radius_m=float(params.closing_radius_m),
        opening_radius_m=float(params.opening_radius_m),
        fill_holes=bool(params.fill_holes),
        keep_largest=bool(params.keep_largest_component and selector_xy is None),
    )
    if selector_xy is not None:
        mask = _select_component_by_xy(
            mask,
            origin_xy=(float(mins_xy[0]), float(mins_xy[1])),
            cell_res_m=float(params.cell_res_m),
            point_xy=selector_xy,
        )

    ring = polygonize_mask(
        mask,
        origin_xy=(float(mins_xy[0]), float(mins_xy[1])),
        cell_res_m=float(params.cell_res_m),
        simplify_tolerance_m=params.simplify_tolerance_m,
    )

    area_m2_mask = float(mask.sum()) * float(params.cell_res_m) ** 2
    area_m2_poly = float(abs(_ring_area_signed(np.asarray(ring, dtype=np.float64))))

    # Deterministic properties: sort keys when writing.
    props: Dict[str, Any] = {"aoi_id": params.aoi_id, **(params.properties or {})}
    props.setdefault("source", "derived_from_lidar")
    props.setdefault("method", "grid_occupancy+morphology+contour")
    props.setdefault("cell_res_m", float(params.cell_res_m))
    props.setdefault("threshold_method", str(params.threshold_method))
    props.setdefault("min_points_per_cell", int(params.min_points_per_cell))
    props.setdefault("area_m2_mask", area_m2_mask)
    props.setdefault("area_m2_poly", area_m2_poly)
    if params.roi_from_detections is not None:
        props.setdefault("roi_from_detections", str(Path(params.roi_from_detections)))
        props.setdefault("roi_buffer_m", float(params.roi_buffer_m))
        if selector_xy is not None:
            props.setdefault("component_selector_xy", [float(selector_xy[0]), float(selector_xy[1])])
    if params.roi_bounds is not None:
        props.setdefault("roi_bounds", [float(v) for v in params.roi_bounds])

    fc = {
        "type": "FeatureCollection",
        "name": f"{params.aoi_id}_epsg{int(params.crs_epsg)}",
        "crs": {"epsg": int(params.crs_epsg)},
        "features": [
            {
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        ],
    }

    params.out_path.parent.mkdir(parents=True, exist_ok=True)
    params.out_path.write_text(json.dumps(fc, indent=2, sort_keys=True))
    return params.out_path


def find_lidar_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for dp, _dns, fns in os.walk(root):
        for fn in fns:
            if Path(fn).suffix.lower() in {".las", ".laz"}:
                files.append(Path(dp) / fn)
    return sorted(files, key=str)


def _bounds_xy(files: List[Path]) -> Tuple[np.ndarray, np.ndarray]:
    mins = np.array([np.inf, np.inf], dtype=np.float64)
    maxs = np.array([-np.inf, -np.inf], dtype=np.float64)
    for p in files:
        lo, hi = _bounds_xy_one(p)
        mins = np.minimum(mins, lo)
        maxs = np.maximum(maxs, hi)
    if not np.isfinite(mins).all() or not np.isfinite(maxs).all():
        raise RuntimeError("Failed to compute bounds (non-finite)")
    return mins, maxs


def _bounds_xy_one(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    # Prefer header bounds: fast and typically reliable.
    try:
        with laspy.open(str(path)) as fh:  # type: ignore[attr-defined]
            h = fh.header
            mins_arr = getattr(h, "mins", None)
            maxs_arr = getattr(h, "maxs", None)
            if mins_arr is not None and maxs_arr is not None:
                lo = np.asarray(mins_arr[:2], dtype=np.float64)
                hi = np.asarray(maxs_arr[:2], dtype=np.float64)
            else:
                lo = np.asarray([float(h.min_x), float(h.min_y)], dtype=np.float64)
                hi = np.asarray([float(h.max_x), float(h.max_y)], dtype=np.float64)
    except Exception:
        lo, hi = _bounds_xy_stream(path, chunk_size=1_000_000)
    if not np.isfinite(lo).all() or not np.isfinite(hi).all() or np.any((hi - lo) <= 0):
        lo, hi = _bounds_xy_stream(path, chunk_size=1_000_000)
    return lo, hi


def _bounds_xy_stream(path: Path, *, chunk_size: int) -> Tuple[np.ndarray, np.ndarray]:
    lo = np.array([np.inf, np.inf], dtype=np.float64)
    hi = np.array([-np.inf, -np.inf], dtype=np.float64)
    for x, y in _stream_xy(path, chunk_size=chunk_size):
        if x.size:
            lo[0] = min(lo[0], float(np.min(x)))
            lo[1] = min(lo[1], float(np.min(y)))
            hi[0] = max(hi[0], float(np.max(x)))
            hi[1] = max(hi[1], float(np.max(y)))
    if not np.isfinite(lo).all() or not np.isfinite(hi).all():
        lo = np.zeros(2, dtype=np.float64)
        hi = np.zeros(2, dtype=np.float64)
    return lo, hi


def _stream_xy(path: Path, *, chunk_size: int) -> Iterable[Tuple[np.ndarray, np.ndarray]]:
    with laspy.open(str(path)) as fh:  # type: ignore[attr-defined]
        if hasattr(fh, "chunk_iterator"):
            for pts in fh.chunk_iterator(int(chunk_size)):  # type: ignore[attr-defined]
                x = np.asarray(pts.x, dtype=np.float64)
                y = np.asarray(pts.y, dtype=np.float64)
                yield x, y
        else:
            total = int(getattr(fh.header, "point_count", 0))  # type: ignore[attr-defined]
            start = 0
            while start < total:
                count = min(int(chunk_size), total - start)
                pts = fh.read_points(start=start, count=count)  # type: ignore[attr-defined]
                x = np.asarray(pts.x, dtype=np.float64)
                y = np.asarray(pts.y, dtype=np.float64)
                yield x, y
                start += count


def _density_grid(
    files: List[Path],
    mins_xy: np.ndarray,
    maxs_xy: np.ndarray,
    cell_res_m: float,
    chunk_size: int,
) -> np.ndarray:
    cell_res_m = float(cell_res_m)
    nx = int(np.ceil((maxs_xy[0] - mins_xy[0]) / cell_res_m)) + 1
    ny = int(np.ceil((maxs_xy[1] - mins_xy[1]) / cell_res_m)) + 1
    if nx <= 0 or ny <= 0:
        raise ValueError("Invalid grid shape computed from bounds")

    counts = np.zeros((ny, nx), dtype=np.uint32)
    for path in files:
        for x, y in _stream_xy(path, chunk_size=int(chunk_size)):
            if x.size == 0:
                continue
            ix = np.floor((x - mins_xy[0]) / cell_res_m).astype(np.int64)
            iy = np.floor((y - mins_xy[1]) / cell_res_m).astype(np.int64)
            valid = (ix >= 0) & (iy >= 0) & (ix < nx) & (iy < ny)
            if not np.any(valid):
                continue
            idx = (iy[valid] * nx + ix[valid]).astype(np.int64)
            # Deterministic within-chunk aggregation.
            counts_flat = counts.ravel()
            bc = np.bincount(idx, minlength=counts_flat.size).astype(np.uint32)
            counts_flat[:] = counts_flat + bc
    return counts


def _roi_bounds_from_detections(path: Path, *, buffer_m: float) -> Tuple[np.ndarray, np.ndarray]:
    """Compute an ROI bbox from a LiDAR summary JSON containing detections with x/y."""
    obj = json.loads(Path(path).read_text())
    xs: List[float] = []
    ys: List[float] = []
    # Support both summary formats:
    # - {"detections":[...]} (flat)
    # - {"files":[{"detections":[...]} ...]} (per-file)
    if isinstance(obj.get("detections"), list):
        det_lists = [obj["detections"]]
    else:
        det_lists = [fi.get("detections", []) for fi in (obj.get("files") or []) if isinstance(fi, dict)]
    for dets in det_lists:
        for d in dets or []:
            if not isinstance(d, dict):
                continue
            if "x" in d and "y" in d:
                xs.append(float(d["x"]))
                ys.append(float(d["y"]))
    if not xs:
        raise ValueError(f"No x/y detections found in {path}")
    xmin = min(xs) - float(buffer_m)
    ymin = min(ys) - float(buffer_m)
    xmax = max(xs) + float(buffer_m)
    ymax = max(ys) + float(buffer_m)
    return np.asarray([xmin, ymin], dtype=np.float64), np.asarray([xmax, ymax], dtype=np.float64)


def _detections_centroid_xy(path: Path) -> Tuple[float, float]:
    """Return (mean_x, mean_y) for detections in a summary JSON."""
    obj = json.loads(Path(path).read_text())
    xs: List[float] = []
    ys: List[float] = []
    if isinstance(obj.get("detections"), list):
        det_lists = [obj["detections"]]
    else:
        det_lists = [fi.get("detections", []) for fi in (obj.get("files") or []) if isinstance(fi, dict)]
    for dets in det_lists:
        for d in dets or []:
            if not isinstance(d, dict):
                continue
            if "x" in d and "y" in d:
                xs.append(float(d["x"]))
                ys.append(float(d["y"]))
    if not xs:
        raise ValueError(f"No x/y detections found in {path}")
    return float(np.mean(xs)), float(np.mean(ys))


def _select_component_by_xy(
    mask: np.ndarray,
    *,
    origin_xy: Tuple[float, float],
    cell_res_m: float,
    point_xy: Tuple[float, float],
) -> np.ndarray:
    """Keep the connected component that contains (or is nearest to) a target point.

    This is useful when a dataset includes multiple land masses (e.g., nearby mainland).
    """
    m = np.asarray(mask, dtype=bool)
    labeled = measure.label(m, connectivity=2)
    if labeled.max() <= 0:
        return m

    px = int(np.floor((float(point_xy[0]) - float(origin_xy[0])) / float(cell_res_m)))
    py = int(np.floor((float(point_xy[1]) - float(origin_xy[1])) / float(cell_res_m)))
    py = min(max(py, 0), labeled.shape[0] - 1)
    px = min(max(px, 0), labeled.shape[1] - 1)
    lab = int(labeled[py, px])
    if lab > 0:
        return labeled == lab

    # Otherwise choose nearest component centroid in XY.
    props = measure.regionprops(labeled)
    if not props:
        return m

    def centroid_xy(rp: Any) -> Tuple[float, float]:
        cy, cx = rp.centroid  # row, col
        x = float(origin_xy[0]) + float(cx) * float(cell_res_m)
        y = float(origin_xy[1]) + float(cy) * float(cell_res_m)
        return x, y

    tx, ty = float(point_xy[0]), float(point_xy[1])
    best_label = min(
        (rp.label for rp in props),
        key=lambda label: (
            (centroid_xy(next(rp for rp in props if rp.label == label))[0] - tx) ** 2
            + (centroid_xy(next(rp for rp in props if rp.label == label))[1] - ty) ** 2
        ),
    )
    return labeled == int(best_label)


def _clean_mask(
    mask: np.ndarray,
    *,
    cell_res_m: float,
    closing_radius_m: float,
    opening_radius_m: float,
    fill_holes: bool,
    keep_largest: bool,
) -> np.ndarray:
    mask = np.asarray(mask, dtype=bool)
    close_px = max(0, int(round(float(closing_radius_m) / max(float(cell_res_m), 1e-6))))
    open_px = max(0, int(round(float(opening_radius_m) / max(float(cell_res_m), 1e-6))))
    if close_px > 0:
        mask = morphology.binary_closing(mask, morphology.disk(close_px))
    if open_px > 0:
        mask = morphology.binary_opening(mask, morphology.disk(open_px))
    if fill_holes:
        mask = ndi.binary_fill_holes(mask)
    if keep_largest:
        labeled = measure.label(mask, connectivity=2)
        if labeled.max() > 0:
            sizes = np.bincount(labeled.ravel())
            sizes[0] = 0
            keep = int(np.argmax(sizes))
            mask = labeled == keep
    return np.asarray(mask, dtype=bool)


def _land_mask(counts: np.ndarray, *, method: str, min_points_per_cell: int) -> np.ndarray:
    """Convert a point-density grid into a land mask.

    - fixed: mask = counts >= min_points_per_cell
    - otsu: derive a threshold from non-zero counts (good for separating sparse water returns)
    """
    c = np.asarray(counts, dtype=np.uint32)
    m = (method or "fixed").strip().lower()
    if m not in {"fixed", "otsu"}:
        raise ValueError(f"Unsupported threshold_method: {method!r}")
    if m == "fixed":
        return c >= int(min_points_per_cell)

    nz = c[c > 0]
    if nz.size < 50:
        # Too little signal for Otsu; fall back.
        return c >= int(min_points_per_cell)
    thr = int(threshold_otsu(nz.astype(np.int32)))
    thr = max(thr, int(min_points_per_cell))
    return c >= thr


def polygonize_mask(
    mask: np.ndarray,
    *,
    origin_xy: Tuple[float, float],
    cell_res_m: float,
    simplify_tolerance_m: Optional[float] = None,
) -> List[List[float]]:
    """Return the outer ring polygon for a boolean mask.

    - `origin_xy` is the (xmin, ymin) origin of the grid.
    - Ring coordinates are in projected meters: [[x,y], ...], closed.
    """
    m = np.asarray(mask, dtype=bool)
    if m.size == 0 or not m.any():
        raise ValueError("Mask is empty; cannot polygonize")

    # Pad mask with False border to ensure contours close properly when
    # the mask touches grid edges (fix for degenerate wedge polygons).
    m_padded = np.pad(m, pad_width=1, mode='constant', constant_values=False)
    # Adjust origin to account for padding
    origin_xy = (float(origin_xy[0]) - float(cell_res_m), float(origin_xy[1]) - float(cell_res_m))

    contours = measure.find_contours(m_padded.astype(np.uint8), level=0.5)
    if not contours:
        raise ValueError("No contours found in mask")

    rings: List[List[List[float]]] = []
    for c in contours:
        if c.shape[0] < 3:
            continue
        # c is Nx2 in (row, col) float coords
        xs = float(origin_xy[0]) + c[:, 1] * float(cell_res_m)
        ys = float(origin_xy[1]) + c[:, 0] * float(cell_res_m)
        ring = [[float(x), float(y)] for x, y in zip(xs, ys)]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        if simplify_tolerance_m is not None and simplify_tolerance_m > 0:
            ring = _simplify_ring_rdp(ring, float(simplify_tolerance_m))
        if len(ring) >= 4:
            rings.append(ring)
    if not rings:
        raise ValueError("Contours found but no valid rings constructed")

    # Select the outer ring by max absolute area.
    best = max(rings, key=lambda r: abs(_ring_area_signed(np.asarray(r, dtype=np.float64))))
    return best


def _ring_area_signed(xy: np.ndarray) -> float:
    if xy.ndim != 2 or xy.shape[1] != 2 or xy.shape[0] < 4:
        return 0.0
    x = xy[:, 0]
    y = xy[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _simplify_ring_rdp(ring: List[List[float]], tol: float) -> List[List[float]]:
    # Keep closure semantics: simplify open polyline then re-close.
    if len(ring) < 6:
        return ring
    pts = np.asarray(ring[:-1], dtype=np.float64)
    keep = _rdp_keep_mask(pts, tol=float(tol))
    simplified = pts[keep]
    out = [[float(x), float(y)] for x, y in simplified.tolist()]
    if out[0] != out[-1]:
        out.append(out[0])
    return out


def _rdp_keep_mask(points: np.ndarray, tol: float) -> np.ndarray:
    """Return boolean mask of points to keep using RDP (deterministic)."""
    n = int(points.shape[0])
    if n <= 2:
        return np.ones((n,), dtype=bool)

    keep = np.zeros((n,), dtype=bool)
    keep[0] = True
    keep[-1] = True
    stack: List[Tuple[int, int]] = [(0, n - 1)]

    def seg_dist(i: int, j: int) -> Tuple[int, float]:
        a = points[i]
        b = points[j]
        ab = b - a
        denom = float(np.dot(ab, ab))
        if denom <= 0:
            # Degenerate segment
            d2 = np.sum((points - a) ** 2, axis=1)
            k = int(np.argmax(d2))
            return k, float(np.sqrt(float(d2[k])))
        # Project each point onto the segment and compute perpendicular distance.
        idxs = np.arange(i + 1, j, dtype=int)
        if idxs.size == 0:
            return i, 0.0
        p = points[idxs]
        t = np.clip(((p - a) @ ab) / denom, 0.0, 1.0)
        proj = a + t[:, None] * ab
        d = np.sqrt(np.sum((p - proj) ** 2, axis=1))
        m = int(np.argmax(d))
        return int(idxs[m]), float(d[m])

    while stack:
        i, j = stack.pop()
        k, d = seg_dist(i, j)
        if d > tol:
            keep[k] = True
            stack.append((i, k))
            stack.append((k, j))
    return keep


