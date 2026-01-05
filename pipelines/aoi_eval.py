"""
AOI-clipped evaluation helpers (CRS-aware, deterministic).

Design goal: no heavy geo deps (no shapely/geopandas). We rely on:
- stdlib json/pathlib
- numpy
- matplotlib.path for point-in-polygon

This is sufficient for QA/QC counting inside pre-projected AOI polygons.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from matplotlib.path import Path as MplPath


@dataclass(frozen=True)
class AoiEvalParams:
    lidar_summary: Path
    aoi_geojson: Path
    out_path: Path
    aoi_crs_epsg: Optional[int] = None
    emit_detection_ids: bool = False
    allow_geographic_crs: bool = False


def run(params: AoiEvalParams) -> Path:
    lidar_obj = _load_json(params.lidar_summary)
    aoi_obj = _load_json(params.aoi_geojson)

    lidar_crs = _extract_crs_code(lidar_obj)
    aoi_crs = f"EPSG:{int(params.aoi_crs_epsg)}" if params.aoi_crs_epsg is not None else _extract_crs_code(aoi_obj)
    if lidar_crs and aoi_crs and lidar_crs != aoi_crs:
        raise ValueError(f"CRS mismatch: lidar={lidar_crs} aoi={aoi_crs}")

    dets = _extract_detections(lidar_obj)
    pts_xy, det_ids = _xy_and_ids(dets)

    aois = _extract_aois(aoi_obj)
    results: List[Dict[str, Any]] = []
    geographic = _is_geographic_crs(aoi_crs or lidar_crs)
    if geographic and not params.allow_geographic_crs:
        raise ValueError(
            "AOI CRS appears geographic (degrees). Provide AOIs in the same projected CRS as LiDAR "
            "(meters), or pass allow_geographic_crs=True (area/density will be omitted)."
        )
    for aoi in aois:
        mask = _points_in_geometry(pts_xy, aoi["geometry"])
        count = int(mask.sum())
        area_m2: Optional[float]
        density_per_ha: Optional[float]
        if geographic:
            area_m2 = None
            density_per_ha = None
        else:
            area_m2 = float(_geometry_area_m2(aoi["geometry"]))
            density_per_ha = float(count / (area_m2 / 10_000.0)) if area_m2 > 0 else None
        row: Dict[str, Any] = {
            "aoi_id": aoi["aoi_id"],
            "properties": aoi["properties"],
            "count": count,
            "area_m2": area_m2,
            "density_per_ha": density_per_ha,
        }
        if params.emit_detection_ids:
            ids = [det_ids[i] for i in np.nonzero(mask)[0].tolist()]
            ids.sort()
            row["detection_ids"] = ids
        results.append(row)

    results.sort(key=lambda r: str(r.get("aoi_id", "")))

    out: Dict[str, Any] = {
        "schema_version": "1",
        "purpose": "lidar_aoi_eval",
        "lidar_summary": str(Path(params.lidar_summary)),
        "aoi_geojson": str(Path(params.aoi_geojson)),
        "crs": lidar_crs or aoi_crs,
        "lidar_crs": lidar_crs,
        "aoi_crs": aoi_crs,
        "total_detections": int(len(det_ids)),
        "aoi_count": int(len(results)),
        "results": results,
    }

    params.out_path.parent.mkdir(parents=True, exist_ok=True)
    params.out_path.write_text(json.dumps(out, indent=2))
    return params.out_path


def _load_json(path: Path) -> Dict[str, Any]:
    if not Path(path).exists():
        raise FileNotFoundError(f"Missing JSON: {path}")
    return json.loads(Path(path).read_text())


def _extract_crs_code(obj: Mapping[str, Any]) -> Optional[str]:
    # GeoJSON often uses a top-level `crs` object, but some AOI files also include
    # CRS info inside `metadata` blocks. Prefer `crs`, fall back to `metadata.crs`.
    crs = obj.get("crs")
    if crs is None and isinstance(obj.get("metadata"), dict):
        crs = obj["metadata"].get("crs")
    if crs is None:
        return None
    if isinstance(crs, str):
        cleaned = crs.strip()
        if cleaned.isdigit():
            return f"EPSG:{int(cleaned)}"
        upper = cleaned.upper()
        if upper in {"CRS84", "OGC:CRS84"}:
            return "EPSG:4326"
        if upper in {"WGS84", "EPSG:4326"}:
            return "EPSG:4326"
        return _normalize_crs_string(cleaned)
    if isinstance(crs, int):
        return f"EPSG:{int(crs)}"
    if isinstance(crs, dict):
        # Common GeoJSON crs form:
        # {"type":"name","properties":{"name":"urn:ogc:def:crs:OGC:1.3:CRS84"}}
        if crs.get("type") == "name" and isinstance(crs.get("properties"), dict):
            name = crs["properties"].get("name")
            if isinstance(name, str) and name.strip():
                n = name.strip()
                u = n.upper()
                if u.endswith("CRS84") or "CRS84" in u:
                    return "EPSG:4326"
                if "EPSG" in u and ":" in n:
                    return _normalize_crs_string(n)
        epsg = crs.get("epsg")
        if epsg is not None:
            return f"EPSG:{int(epsg)}"
        wkt = crs.get("wkt")
        if isinstance(wkt, str) and wkt.strip():
            # We can't normalize WKT without pyproj; return the raw WKT marker.
            return wkt.strip()
    return None


def _is_geographic_crs(crs: Optional[str]) -> bool:
    if crs is None:
        return False
    norm = _normalize_crs_string(crs) or ""
    u = norm.strip().upper()
    if u == "EPSG:4326":
        return True
    if u in {"CRS84", "OGC:CRS84"}:
        return True
    if "CRS84" in u:
        # URN forms sometimes include CRS84; treat as geographic.
        return True
    return False


def _normalize_crs_string(value: str) -> Optional[str]:
    """Normalize common CRS strings into a comparable canonical form."""
    cleaned = (value or "").strip()
    if not cleaned:
        return None

    u = cleaned.upper()
    if u in {"CRS84", "OGC:CRS84"}:
        return "EPSG:4326"
    if u == "WGS84":
        return "EPSG:4326"

    # URN forms (common in GeoJSON): urn:ogc:def:crs:EPSG::32720
    if u.startswith("URN:OGC:DEF:CRS:"):
        # Try to extract EPSG code from the tail.
        if "EPSG" in u:
            parts = cleaned.split(":")
            for token in reversed(parts):
                token = token.strip()
                if token.isdigit():
                    return f"EPSG:{int(token)}"
        # Unknown URN: keep as-is.
        return cleaned

    # EPSG:#### forms (case-insensitive)
    if u.startswith("EPSG:"):
        tail = cleaned.split(":", 1)[1].strip()
        if tail.isdigit():
            return f"EPSG:{int(tail)}"
        return cleaned

    # Raw numeric
    if cleaned.isdigit():
        return f"EPSG:{int(cleaned)}"

    return cleaned


def _extract_detections(summary: Mapping[str, Any]) -> List[Dict[str, Any]]:
    dets: List[Dict[str, Any]] = []
    if isinstance(summary.get("detections"), list):
        for det in summary["detections"]:
            if isinstance(det, dict):
                dets.append(det)
        return dets
    files = summary.get("files")
    if not isinstance(files, list):
        raise ValueError("Unsupported LiDAR summary format (missing detections/files)")
    for file_entry in files:
        if not isinstance(file_entry, dict):
            continue
        for det in file_entry.get("detections", []) or []:
            if isinstance(det, dict):
                dets.append(det)
    return dets


def _xy_and_ids(dets: Sequence[Mapping[str, Any]]) -> Tuple[np.ndarray, List[str]]:
    coords: List[Tuple[float, float]] = []
    ids: List[str] = []
    for i, det in enumerate(dets):
        if "x" not in det or "y" not in det:
            continue
        coords.append((float(det["x"]), float(det["y"])))
        det_id = det.get("id") or det.get("tile_id") or f"det:{i:06d}"
        ids.append(str(det_id))
    if not coords:
        return np.zeros((0, 2), dtype=np.float64), []
    return np.asarray(coords, dtype=np.float64), ids


def _extract_aois(geojson: Mapping[str, Any]) -> List[Dict[str, Any]]:
    if geojson.get("type") != "FeatureCollection":
        raise ValueError("AOI input must be a GeoJSON FeatureCollection")
    feats = geojson.get("features")
    if not isinstance(feats, list):
        raise ValueError("AOI FeatureCollection missing features")
    out: List[Dict[str, Any]] = []
    for i, feat in enumerate(feats):
        if not isinstance(feat, dict):
            continue
        geom = feat.get("geometry")
        if not isinstance(geom, dict):
            continue
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        props = feat.get("properties") if isinstance(feat.get("properties"), dict) else {}
        aoi_id = (
            props.get("id")
            or props.get("aoi_id")
            or props.get("name")
            or feat.get("id")
            or f"aoi_{i:03d}"
        )
        out.append({"aoi_id": str(aoi_id), "properties": dict(props), "geometry": geom})
    if not out:
        raise ValueError("No Polygon/MultiPolygon AOIs found in GeoJSON")
    return out


def _points_in_geometry(points_xy: np.ndarray, geom: Mapping[str, Any]) -> np.ndarray:
    if points_xy.size == 0:
        return np.zeros((0,), dtype=bool)
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Polygon":
        return _points_in_polygon(points_xy, coords)
    if gtype == "MultiPolygon":
        masks = [_points_in_polygon(points_xy, poly_coords) for poly_coords in coords]
        if not masks:
            return np.zeros((points_xy.shape[0],), dtype=bool)
        out = masks[0].copy()
        for m in masks[1:]:
            out |= m
        return out
    raise ValueError(f"Unsupported geometry type: {gtype}")


def _points_in_polygon(points_xy: np.ndarray, rings: Any) -> np.ndarray:
    # GeoJSON Polygon: [outer, hole1, hole2, ...] where each ring is [[x,y], ...]
    if not isinstance(rings, list) or not rings:
        return np.zeros((points_xy.shape[0],), dtype=bool)
    outer = np.asarray(rings[0], dtype=np.float64)
    if outer.ndim != 2 or outer.shape[1] != 2 or outer.shape[0] < 3:
        return np.zeros((points_xy.shape[0],), dtype=bool)
    outer_path = MplPath(outer)
    inside = outer_path.contains_points(points_xy)
    # Subtract holes.
    for hole in rings[1:]:
        h = np.asarray(hole, dtype=np.float64)
        if h.ndim != 2 or h.shape[1] != 2 or h.shape[0] < 3:
            continue
        hole_path = MplPath(h)
        inside &= ~hole_path.contains_points(points_xy)
    return inside


def _geometry_area_m2(geom: Mapping[str, Any]) -> float:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Polygon":
        return float(_polygon_area(coords))
    if gtype == "MultiPolygon":
        return float(sum(_polygon_area(poly) for poly in coords))
    raise ValueError(f"Unsupported geometry type: {gtype}")


def _polygon_area(rings: Any) -> float:
    if not isinstance(rings, list) or not rings:
        return 0.0
    outer = np.asarray(rings[0], dtype=np.float64)
    area = abs(_ring_area(outer))
    for hole in rings[1:]:
        h = np.asarray(hole, dtype=np.float64)
        area -= abs(_ring_area(h))
    return float(max(area, 0.0))


def _ring_area(xy: np.ndarray) -> float:
    if xy.ndim != 2 or xy.shape[1] != 2 or xy.shape[0] < 3:
        return 0.0
    x = xy[:, 0]
    y = xy[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


