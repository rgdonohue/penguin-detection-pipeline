#!/usr/bin/env python3
"""
Convert GPS waypoint CSVs to AOI polygon GeoJSON files.

Reads from gps_aoi/data/waypoints/*.csv, builds polygons (convex hull
or point buffer), writes WGS84 GeoJSON to gps_aoi/data/output/ for QGIS.

Usage:
  python waypoints_to_geojson.py --waypoints-dir ../data/waypoints --out-dir ../data/output
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

try:
    from pyproj import Transformer
except ImportError as exc:
    raise SystemExit("Missing dependency: pyproj. Install with: pip install pyproj") from exc

# Site metadata: aoi_id, name, penguin_count, area_ha (optional), crs_epsg, is_point
SITE_CONFIG: dict[str, dict[str, Any]] = {
    "caleta_tiny_island": {"name": "Caleta Tiny Island", "penguin_count": 321, "area_ha": 0.7, "crs_epsg": 32720, "is_point": False},
    "caleta_small_island": {"name": "Caleta Small Island", "penguin_count": 1557, "area_ha": 4.0, "crs_epsg": 32720, "is_point": False},
    "caleta_box1": {"name": "Caleta Box Count 1", "penguin_count": 8, "area_ha": None, "crs_epsg": 32720, "is_point": True},
    "caleta_box2": {"name": "Caleta Box Count 2", "penguin_count": 12, "area_ha": None, "crs_epsg": 32720, "is_point": True},
    "san_lorenzo_caves": {"name": "High Density Caves", "penguin_count": 908, "area_ha": None, "crs_epsg": 5345, "is_point": False},
    "san_lorenzo_plains": {"name": "The Plains", "penguin_count": 453, "area_ha": None, "crs_epsg": 5345, "is_point": False},
    "san_lorenzo_road": {"name": "Road Total Count", "penguin_count": 359, "area_ha": None, "crs_epsg": 5345, "is_point": False},
    "san_lorenzo_box_caves": {"name": "Box Count High Density Caves", "penguin_count": 32, "area_ha": None, "crs_epsg": 5345, "is_point": True},
    "san_lorenzo_box_bushes": {"name": "Box Count High Density Bushes", "penguin_count": 55, "area_ha": None, "crs_epsg": 5345, "is_point": True},
}

WGS84 = "EPSG:4326"
BUFFER_M = 15.0  # meters for single-point (box) AOIs


def load_waypoints(csv_path: Path) -> list[tuple[float, float]]:
    """Return list of (lat, lon) for rows with valid coordinates."""
    points: list[tuple[float, float]] = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lat_s = (row.get("lat") or "").strip()
            lon_s = (row.get("lon") or "").strip()
            if not lat_s or not lon_s:
                continue
            try:
                lat, lon = float(lat_s), float(lon_s)
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    points.append((lat, lon))
            except ValueError:
                continue
    return points


def convex_hull_latlon(points: list[tuple[float, float]], crs_epsg: int) -> list[tuple[float, float]]:
    """Convex hull in projected space, return hull as (lat, lon)."""
    if len(points) < 3:
        return points
    trans_wgs_to_proj = Transformer.from_crs(WGS84, f"EPSG:{crs_epsg}", always_xy=True)
    trans_proj_to_wgs = Transformer.from_crs(f"EPSG:{crs_epsg}", WGS84, always_xy=True)
    pts_xy = [trans_wgs_to_proj.transform(lon, lat) for lat, lon in points]
    pts_xy = list(dict.fromkeys(pts_xy))
    if len(pts_xy) < 3:
        return points

    pts_xy.sort(key=lambda p: (p[0], p[1]))

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts_xy:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts_xy):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull_xy = lower[:-1] + upper[:-1]
    hull_latlon = []
    for x, y in hull_xy:
        lon, lat = trans_proj_to_wgs.transform(x, y)
        hull_latlon.append((lat, lon))
    return hull_latlon


def buffer_point_meters(lat: float, lon: float, meters: float, crs_epsg: int) -> list[tuple[float, float]]:
    """Return a square (4 vertices) around the point in WGS84."""
    trans_wgs_to_proj = Transformer.from_crs(WGS84, f"EPSG:{crs_epsg}", always_xy=True)
    trans_proj_to_wgs = Transformer.from_crs(f"EPSG:{crs_epsg}", WGS84, always_xy=True)
    x, y = trans_wgs_to_proj.transform(lon, lat)
    h = meters / 2
    square_xy = [(x - h, y - h), (x + h, y - h), (x + h, y + h), (x - h, y + h)]
    ring = []
    for sx, sy in square_xy:
        lon_out, lat_out = trans_proj_to_wgs.transform(sx, sy)
        ring.append((lat_out, lon_out))
    ring.append(ring[0])
    return ring


def ring_to_geojson_coords(ring: list[tuple[float, float]]) -> list[list[float]]:
    """GeoJSON exterior ring: [[lon, lat], ...] closed."""
    coords = [[lon, lat] for lat, lon in ring]
    if coords and (coords[0] != coords[-1]):
        coords.append(coords[0])
    return coords


def build_feature(
    site_id: str,
    ring: list[tuple[float, float]],
) -> dict[str, Any]:
    cfg = SITE_CONFIG.get(site_id, {})
    name = cfg.get("name", site_id)
    penguin_count = cfg.get("penguin_count")
    area_ha = cfg.get("area_ha")
    props: dict[str, Any] = {"aoi_id": site_id, "name": name, "source": "GPS Ground Truthing Notes 2025 - RD.pdf"}
    if penguin_count is not None:
        props["penguin_count"] = penguin_count
    if area_ha is not None:
        props["area_ha"] = area_ha
    coords = ring_to_geojson_coords(ring)
    return {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [coords]}}


def process_site(site_id: str, points: list[tuple[float, float]], cfg: dict[str, Any]) -> dict[str, Any] | None:
    if not points:
        return None
    crs_epsg = cfg.get("crs_epsg", 4326)
    is_point = cfg.get("is_point", False)

    if len(points) == 1 and is_point:
        ring = buffer_point_meters(points[0][0], points[0][1], BUFFER_M, crs_epsg)
    elif len(points) < 3:
        return None
    else:
        hull = convex_hull_latlon(points, crs_epsg)
        ring = hull if hull[0] == hull[-1] else hull + [hull[0]]

    return build_feature(site_id, ring)


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert waypoint CSVs to WGS84 GeoJSON AOIs")
    ap.add_argument("--waypoints-dir", type=Path, default=Path("../data/waypoints"), help="Directory of waypoint CSVs")
    ap.add_argument("--out-dir", type=Path, default=Path("../data/output"), help="Output directory for GeoJSON")
    ap.add_argument("--combined", action="store_true", default=True, help="Write all_aois_combined_wgs84.geojson")
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    w, o = Path(args.waypoints_dir), Path(args.out_dir)
    from_cwd = False
    if w.is_absolute():
        waypoints_dir = w.resolve()
    else:
        waypoints_dir = (script_dir / w).resolve()
        if not waypoints_dir.exists():
            waypoints_dir = (Path.cwd() / w).resolve()
            from_cwd = True
    if o.is_absolute():
        out_dir = o.resolve()
    else:
        out_dir = (Path.cwd() / o).resolve() if from_cwd else (script_dir / o).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    features: list[dict[str, Any]] = []
    csv_paths = sorted(waypoints_dir.glob("*.csv"))
    for path in csv_paths:
        site_id = path.stem
        cfg = SITE_CONFIG.get(site_id, {"name": site_id, "crs_epsg": 4326, "is_point": False})
        points = load_waypoints(path)
        feat = process_site(site_id, points, cfg)
        out_path = out_dir / f"{site_id}_wgs84.geojson"
        if feat is None:
            fc = {"type": "FeatureCollection", "features": []}
            out_path.write_text(json.dumps(fc, indent=2), encoding="utf-8")
            print(f"  {out_path.name} (empty)")
            continue
        features.append(feat)
        fc = {"type": "FeatureCollection", "features": [feat]}
        out_path.write_text(json.dumps(fc, indent=2), encoding="utf-8")
        print(f"  {out_path.name}")

    if args.combined and features:
        combined_path = out_dir / "all_aois_combined_wgs84.geojson"
        combined_path.write_text(
            json.dumps({"type": "FeatureCollection", "features": features}, indent=2),
            encoding="utf-8",
        )
        print(f"  {combined_path.name} (combined)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
