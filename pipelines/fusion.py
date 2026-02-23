"""
Fusion stage (thermal + LiDAR reconciliation).

This module performs a spatial join between LiDAR and thermal detections once
both are expressed in the same projected CRS (meters).  It deliberately does
not attempt to georeference thermal pixel detections; upstream code should
produce thermal detections with ``x``/``y`` coordinates in the target CRS.
"""

from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.spatial import cKDTree


@dataclass
class FusionParams:
    """Inputs and outputs required to produce the fusion rollup."""

    lidar_summary: Path
    thermal_summary: Path
    out_path: Path
    match_radius_m: float = 0.5
    qc_panel: Optional[Path] = None
    thermal_raster: Optional[Path] = None
    thermal_core_radius_m: float = 0.5
    thermal_neighborhood_inner_radius_m: float = 1.0
    thermal_neighborhood_outer_radius_m: float = 2.0
    thermal_z_method: str = "robust"


def run(params: FusionParams) -> Path:
    """Fuse detections from LiDAR and thermal summaries and write a rollup JSON."""

    lidar_obj = _load_json(params.lidar_summary)
    thermal_obj = _load_json(params.thermal_summary)

    lidar_crs = _extract_crs(lidar_obj)
    thermal_crs = _extract_crs(thermal_obj)
    if lidar_crs and thermal_crs and lidar_crs != thermal_crs:
        raise ValueError(f"CRS mismatch: lidar={lidar_crs} thermal={thermal_crs}")

    lidar_dets = _extract_detections(lidar_obj, source="lidar")
    thermal_dets = _extract_detections(thermal_obj, source="thermal")

    effective_crs = lidar_crs or thermal_crs
    _validate_coordinate_range(lidar_dets, effective_crs)
    _validate_coordinate_range(thermal_dets, effective_crs)

    thermal_sampling_meta: Optional[Dict[str, Any]] = None
    if params.thermal_raster is not None:
        thermal_sampling_meta = _sample_thermal_on_detections(
            detections=lidar_dets,
            thermal_raster=Path(params.thermal_raster),
            expected_crs=effective_crs,
            core_radius_m=float(params.thermal_core_radius_m),
            neighborhood_inner_radius_m=float(params.thermal_neighborhood_inner_radius_m),
            neighborhood_outer_radius_m=float(params.thermal_neighborhood_outer_radius_m),
            z_method=str(params.thermal_z_method),
        )

    out = _join_detections(
        lidar_dets=lidar_dets,
        thermal_dets=thermal_dets,
        match_radius_m=float(params.match_radius_m),
    )

    out["schema_version"] = "1"
    out["purpose"] = "qc_alignment"
    out["temperature_calibrated"] = False

    out["lidar_crs"] = lidar_crs
    out["thermal_crs"] = thermal_crs
    out["crs"] = lidar_crs or thermal_crs
    if thermal_sampling_meta is not None:
        out["thermal_sampling"] = thermal_sampling_meta

    params.out_path.parent.mkdir(parents=True, exist_ok=True)
    params.out_path.write_text(json.dumps(out, indent=2))
    return params.out_path


def _load_json(path: Path) -> Dict[str, Any]:
    if not Path(path).exists():
        raise FileNotFoundError(f"Missing summary JSON: {path}")
    return json.loads(Path(path).read_text())


def _extract_crs(summary: Dict[str, Any]) -> Optional[str]:
    for key in ("crs", "crs_epsg", "epsg", "epsg_code", "crs_code"):
        value = summary.get(key)
        if value is None:
            continue
        if isinstance(value, int):
            return f"EPSG:{value}"
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                if cleaned.isdigit():
                    return f"EPSG:{int(cleaned)}"
                return cleaned
    return None


def _is_geographic_crs(crs_str: str) -> bool:
    """Heuristic: return True if the CRS string looks like a geographic (degree-based) CRS."""
    crs_str_lower = crs_str.lower().strip()
    # EPSG:4326 and similar geographic CRS codes
    if crs_str_lower.startswith("epsg:"):
        try:
            code = int(crs_str_lower.split(":")[1])
            # Well-known geographic CRS codes
            return code in (4326, 4269, 4267, 4258, 4283, 4167, 4612)
        except (ValueError, IndexError):
            pass
    if "geogcs" in crs_str_lower:
        return True
    return False


def _validate_coordinate_range(detections: List[Dict[str, Any]], crs: Optional[str]) -> None:
    """Warn (not fail) if coordinates look implausible for the declared CRS."""
    if crs is None:
        return  # Can't validate without known CRS
    xs = [float(d["x"]) for d in detections if "x" in d]
    if not xs:
        return
    max_abs_x = max(abs(x) for x in xs)
    if _is_geographic_crs(crs):
        # Geographic: expect degrees
        if max_abs_x > 360:
            warnings.warn(
                f"Geographic CRS {crs} but coordinates exceed 360: likely projected meters"
            )
    else:
        # Projected: expect meters (UTM range ~100k-900k)
        if max_abs_x < 360:
            warnings.warn(
                f"Projected CRS {crs} but coordinates < 360: likely geographic degrees"
            )


def _extract_detections(summary: Dict[str, Any], source: str) -> List[Dict[str, Any]]:
    dets: List[Dict[str, Any]] = []

    if isinstance(summary.get("detections"), list):
        for det in summary["detections"]:
            dets.append({**det, "_source": source})
        return dets

    files = summary.get("files")
    if not isinstance(files, list):
        raise ValueError(f"Unsupported {source} summary format (missing detections/files)")

    for file_entry in files:
        file_path = file_entry.get("path") or file_entry.get("file") or file_entry.get("source")
        for det in file_entry.get("detections", []) or []:
            dets.append({**det, "_source": source, "_file": file_path})

    return dets


def _xy_from_dets(dets: List[Dict[str, Any]]) -> Tuple[np.ndarray, List[int]]:
    coords: List[Tuple[float, float]] = []
    idxs: List[int] = []
    for i, det in enumerate(dets):
        if "x" not in det or "y" not in det:
            continue
        coords.append((float(det["x"]), float(det["y"])))
        idxs.append(i)
    if not coords:
        return np.zeros((0, 2), dtype=np.float64), []
    return np.asarray(coords, dtype=np.float64), idxs


def _normalize_crs_code(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    upper = cleaned.upper()
    if upper.startswith("EPSG:"):
        tail = upper.split(":", 1)[1].strip()
        if tail.isdigit():
            return f"EPSG:{int(tail)}"
    if cleaned.isdigit():
        return f"EPSG:{int(cleaned)}"
    return cleaned


def _raster_crs_code(dataset: Any) -> Optional[str]:
    crs = getattr(dataset, "crs", None)
    if crs is None:
        return None
    try:
        epsg = crs.to_epsg()
    except Exception:
        epsg = None
    if epsg is not None:
        return f"EPSG:{int(epsg)}"
    try:
        return str(crs.to_string())
    except Exception:
        text = str(crs)
        return text if text.strip() else None


def _valid_data_mask(values: np.ndarray, nodata: Optional[float]) -> np.ndarray:
    valid = np.isfinite(values)
    if nodata is None:
        return valid
    try:
        nodata_f = float(nodata)
    except (TypeError, ValueError):
        return valid
    if math.isnan(nodata_f):
        return valid & ~np.isnan(values)
    return valid & (values != nodata_f)


def _sample_thermal_point(
    *,
    dataset: Any,
    x: Optional[float],
    y: Optional[float],
    core_radius_m: float,
    neighborhood_inner_radius_m: float,
    neighborhood_outer_radius_m: float,
    z_method: str,
) -> Dict[str, Any]:
    if x is None or y is None:
        return {
            "thermal_mean_c": None,
            "thermal_max_c": None,
            "thermal_z_local": None,
            "thermal_sample_reason": "missing_xy",
            "thermal_n_core": 0,
            "thermal_n_neighborhood": 0,
        }

    row, col = dataset.index(float(x), float(y))
    if row < 0 or row >= int(dataset.height) or col < 0 or col >= int(dataset.width):
        return {
            "thermal_mean_c": None,
            "thermal_max_c": None,
            "thermal_z_local": None,
            "thermal_sample_reason": "point_outside_raster",
            "thermal_n_core": 0,
            "thermal_n_neighborhood": 0,
        }

    pixel_x = abs(float(dataset.transform.a))
    pixel_y = abs(float(dataset.transform.e))
    if pixel_x <= 0 or pixel_y <= 0:
        raise ValueError("Thermal raster has invalid pixel size (non-positive).")
    max_radius_px = int(math.ceil(float(neighborhood_outer_radius_m) / min(pixel_x, pixel_y)))
    row_min = max(0, int(row - max_radius_px))
    row_max = min(int(dataset.height), int(row + max_radius_px + 1))
    col_min = max(0, int(col - max_radius_px))
    col_max = min(int(dataset.width), int(col + max_radius_px + 1))

    from rasterio.windows import Window

    arr = dataset.read(
        1,
        window=Window(col_off=col_min, row_off=row_min, width=col_max - col_min, height=row_max - row_min),
        masked=False,
    ).astype(np.float64, copy=False)
    if arr.size == 0:
        return {
            "thermal_mean_c": None,
            "thermal_max_c": None,
            "thermal_z_local": None,
            "thermal_sample_reason": "point_outside_raster",
            "thermal_n_core": 0,
            "thermal_n_neighborhood": 0,
        }

    rows = np.arange(row_min, row_max, dtype=np.float64)
    cols = np.arange(col_min, col_max, dtype=np.float64)
    grid_cols, grid_rows = np.meshgrid(cols, rows)
    t = dataset.transform
    xs = t.c + (grid_cols + 0.5) * t.a + (grid_rows + 0.5) * t.b
    ys = t.f + (grid_cols + 0.5) * t.d + (grid_rows + 0.5) * t.e
    distances = np.hypot(xs - float(x), ys - float(y))

    valid = _valid_data_mask(arr, dataset.nodata)
    core_mask = distances <= float(core_radius_m)
    neighborhood_mask = (
        (distances >= float(neighborhood_inner_radius_m))
        & (distances <= float(neighborhood_outer_radius_m))
    )

    core_values = arr[core_mask & valid]
    if core_values.size == 0:
        return {
            "thermal_mean_c": None,
            "thermal_max_c": None,
            "thermal_z_local": None,
            "thermal_sample_reason": "core_nodata",
            "thermal_n_core": 0,
            "thermal_n_neighborhood": int(np.count_nonzero(neighborhood_mask & valid)),
        }

    neighborhood_values = arr[neighborhood_mask & valid]
    reason: Optional[str] = None
    z_local: Optional[float] = None
    if neighborhood_values.size < 3:
        reason = "insufficient_neighborhood"
    else:
        if z_method == "robust":
            core_signal = float(np.median(core_values))
            neigh_med = float(np.median(neighborhood_values))
            mad = float(np.median(np.abs(neighborhood_values - neigh_med)))
            robust_scale = 1.4826 * mad
            if robust_scale > 1e-9:
                z_local = float((core_signal - neigh_med) / robust_scale)
            else:
                neigh_std = float(np.std(neighborhood_values))
                if neigh_std > 1e-9:
                    reason = "mad_zero_fallback_std"
                    z_local = float((core_signal - float(np.mean(neighborhood_values))) / neigh_std)
                else:
                    reason = "zero_neighborhood_variance"
        elif z_method == "standard":
            core_signal = float(np.mean(core_values))
            neigh_mean = float(np.mean(neighborhood_values))
            neigh_std = float(np.std(neighborhood_values))
            if neigh_std > 1e-9:
                z_local = float((core_signal - neigh_mean) / neigh_std)
            else:
                reason = "zero_neighborhood_variance"
        else:
            raise ValueError(f"Unsupported thermal z method: {z_method}")

    return {
        "thermal_mean_c": float(np.mean(core_values)),
        "thermal_max_c": float(np.max(core_values)),
        "thermal_z_local": z_local,
        "thermal_sample_reason": reason,
        "thermal_n_core": int(core_values.size),
        "thermal_n_neighborhood": int(neighborhood_values.size),
    }


def _sample_thermal_on_detections(
    *,
    detections: List[Dict[str, Any]],
    thermal_raster: Path,
    expected_crs: Optional[str],
    core_radius_m: float,
    neighborhood_inner_radius_m: float,
    neighborhood_outer_radius_m: float,
    z_method: str,
) -> Dict[str, Any]:
    if core_radius_m <= 0:
        raise ValueError(f"thermal_core_radius_m must be > 0, got {core_radius_m}")
    if neighborhood_inner_radius_m < core_radius_m:
        raise ValueError(
            "thermal_neighborhood_inner_radius_m must be >= thermal_core_radius_m"
        )
    if neighborhood_outer_radius_m <= neighborhood_inner_radius_m:
        raise ValueError(
            "thermal_neighborhood_outer_radius_m must be > thermal_neighborhood_inner_radius_m"
        )
    if expected_crs is None:
        raise ValueError("Thermal sampling requires CRS on fusion detections.")

    try:
        import rasterio  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("rasterio is required for thermal raster sampling.") from exc

    raster_path = Path(thermal_raster)
    if not raster_path.exists():
        raise FileNotFoundError(f"Thermal raster not found: {raster_path}")

    expected_norm = _normalize_crs_code(expected_crs)
    if expected_norm is None:
        raise ValueError(f"Unrecognized detection CRS: {expected_crs!r}")

    sampled = 0
    with rasterio.open(raster_path) as ds:
        raster_crs = _raster_crs_code(ds)
        raster_norm = _normalize_crs_code(raster_crs)
        if raster_norm is None:
            raise ValueError(f"Thermal raster CRS missing: {raster_path}")
        if raster_norm != expected_norm:
            raise ValueError(
                f"CRS mismatch: detections={expected_norm} thermal_raster={raster_norm}"
            )

        for det in detections:
            result = _sample_thermal_point(
                dataset=ds,
                x=det.get("x"),
                y=det.get("y"),
                core_radius_m=float(core_radius_m),
                neighborhood_inner_radius_m=float(neighborhood_inner_radius_m),
                neighborhood_outer_radius_m=float(neighborhood_outer_radius_m),
                z_method=str(z_method),
            )
            det.update(result)
            if result.get("thermal_mean_c") is not None:
                sampled += 1

    return {
        "enabled": True,
        "thermal_raster": str(raster_path),
        "core_radius_m": float(core_radius_m),
        "neighborhood_inner_radius_m": float(neighborhood_inner_radius_m),
        "neighborhood_outer_radius_m": float(neighborhood_outer_radius_m),
        "z_method": str(z_method),
        "z_method_note": (
            "robust uses median/MAD and falls back to mean/std when MAD is zero."
            if str(z_method) == "robust"
            else "standard uses mean/std and is more sensitive to outliers."
        ),
        "detections_total": int(len(detections)),
        "detections_with_thermal_samples": int(sampled),
    }


def _join_detections(
    *,
    lidar_dets: List[Dict[str, Any]],
    thermal_dets: List[Dict[str, Any]],
    match_radius_m: float,
) -> Dict[str, Any]:
    lidar_xy, lidar_idxs = _xy_from_dets(lidar_dets)
    thermal_xy, thermal_idxs = _xy_from_dets(thermal_dets)

    lidar_matches: List[Optional[int]] = [None] * len(lidar_dets)
    lidar_match_dist_m: List[Optional[float]] = [None] * len(lidar_dets)
    thermal_matched: List[bool] = [False] * len(thermal_dets)

    if lidar_xy.size and thermal_xy.size:
        tree = cKDTree(thermal_xy)
        dists, nn = tree.query(lidar_xy, k=1, distance_upper_bound=float(match_radius_m))
        for local_i, (dist, nn_local) in enumerate(zip(dists, nn)):
            global_lidar_i = lidar_idxs[local_i]
            if not np.isfinite(dist):
                continue
            if nn_local >= len(thermal_idxs):
                continue
            global_thermal_i = thermal_idxs[int(nn_local)]
            lidar_matches[global_lidar_i] = global_thermal_i
            lidar_match_dist_m[global_lidar_i] = float(dist)
            thermal_matched[global_thermal_i] = True

    lidar_matched_count = sum(1 for m in lidar_matches if m is not None)
    thermal_matched_count = sum(1 for m in thermal_matched if m)

    return {
        "match_radius_m": float(match_radius_m),
        "lidar_count": len(lidar_dets),
        "thermal_count": len(thermal_dets),
        "lidar_matched_count": int(lidar_matched_count),
        "thermal_matched_count": int(thermal_matched_count),
        "lidar_only_count": int(len(lidar_dets) - lidar_matched_count),
        "thermal_only_count": int(len(thermal_dets) - thermal_matched_count),
        "lidar": [
            {
                **det,
                "match_thermal_index": lidar_matches[i],
                "match_dist_m": lidar_match_dist_m[i],
                "label": "both" if lidar_matches[i] is not None else "lidar_only",
            }
            for i, det in enumerate(lidar_dets)
        ],
        "thermal": [
            {
                **det,
                "matched_by_lidar": bool(thermal_matched[i]),
                "label": "both" if thermal_matched[i] else "thermal_only",
            }
            for i, det in enumerate(thermal_dets)
        ],
    }
