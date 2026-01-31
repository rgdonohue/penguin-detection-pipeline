#!/usr/bin/env python3
"""
Create San Lorenzo AOI polygons from GPS waypoints with correct winding order.

This script fixes the bowtie polygon issue caused by concatenating edge waypoints
in the same direction instead of forming a proper closed perimeter.

For a two-edge transect (like Plains):
- Top edge points go in one direction (e.g., west to east)
- Bottom edge points must be REVERSED to trace back (east to west)
- This forms a proper closed polygon perimeter

Usage:
    python scripts/create_san_lorenzo_aois.py \
        --output data/processed/aoi_san_lorenzo_epsg5345.geojson
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import List, Tuple

try:
    from pyproj import Transformer
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: pyproj\n"
        "Install with: pip install pyproj"
    ) from exc

PROJECT_ROOT = Path(__file__).parent.parent

# San Lorenzo uses POSGAR 2007 / Argentina Zone 3
TARGET_EPSG = 5345
WGS84_TO_TARGET = Transformer.from_crs("EPSG:4326", f"EPSG:{TARGET_EPSG}", always_xy=True)


def load_waypoints_by_type(csv_path: Path) -> dict:
    """Load waypoints grouped by zone and point_type."""
    data = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            zone = row.get("zone", "").strip()
            point_type = row.get("point_type", "").strip()
            lat_str = row.get("lat", "").strip()
            lon_str = row.get("lon", "").strip()

            if not zone or not lat_str or not lon_str:
                continue

            lat = float(lat_str)
            lon = float(lon_str)

            if zone not in data:
                data[zone] = {}
            if point_type not in data[zone]:
                data[zone][point_type] = []

            data[zone][point_type].append((lat, lon))

    return data


def wgs84_to_projected(lat: float, lon: float) -> Tuple[float, float]:
    """Convert WGS84 lat/lon to projected coordinates."""
    x, y = WGS84_TO_TARGET.transform(lon, lat)
    return (round(x, 2), round(y, 2))


def points_to_projected(points: List[Tuple[float, float]]) -> List[List[float]]:
    """Convert list of (lat, lon) to projected [x, y] coordinates."""
    return [list(wgs84_to_projected(lat, lon)) for lat, lon in points]


def sort_points_by_longitude(points: List[Tuple[float, float]], reverse: bool = False) -> List[Tuple[float, float]]:
    """Sort points by longitude (west to east by default)."""
    return sorted(points, key=lambda p: p[1], reverse=reverse)


def compute_polygon_area(coords: List[List[float]]) -> float:
    """Compute polygon area using shoelace formula. Returns area in m²."""
    n = len(coords)
    if n < 3:
        return 0.0

    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i][0] * coords[j][1]
        area -= coords[j][0] * coords[i][1]

    return abs(area) / 2.0


def build_caves_polygon(waypoints: dict) -> dict:
    """Build the Caves polygon from start, end, and edge waypoints.

    The Caves area has waypoints along the right edge. We construct a
    rough polygon using convex hull approach since we don't have
    well-defined opposing edges.
    """
    all_points = []
    for point_type in ["start", "end", "edge"]:
        if point_type in waypoints:
            all_points.extend(waypoints[point_type])

    if len(all_points) < 3:
        return None

    # Use convex hull for caves since we don't have two clear edges
    hull = convex_hull(all_points)
    coords_proj = points_to_projected(hull)

    # Close the polygon
    if coords_proj[0] != coords_proj[-1]:
        coords_proj.append(coords_proj[0])

    area_m2 = compute_polygon_area(coords_proj)

    return {
        "type": "Feature",
        "properties": {
            "aoi_id": "san_lorenzo_caves",
            "site": "san_lorenzo",
            "zone": "caves",
            "name": "High Density Caves",
            "penguin_count": 908,
            "area_ha": round(area_m2 / 10000, 4),
            "density_per_ha": round(908 / (area_m2 / 10000), 2),
            "notes": "Start/end waypoints + right edge points",
            "source": "GPS Ground Truthing Notes 2025 - RD.pdf"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords_proj]
        }
    }


def build_plains_polygon(waypoints: dict) -> dict:
    """Build the Plains polygon from top and bottom edge waypoints.

    The waypoints were recorded while walking transects, not in perimeter order.
    Some bottom_edge points are duplicates or outliers. Using convex hull
    produces a clean polygon that encloses all survey points.
    """
    all_points = []
    for point_type in ["top_edge", "bottom_edge", "start", "end"]:
        if point_type in waypoints:
            all_points.extend(waypoints[point_type])

    if len(all_points) < 3:
        return None

    # Remove duplicate points (within ~1m tolerance)
    unique_points = []
    for pt in all_points:
        is_dup = False
        for existing in unique_points:
            # ~0.00001 degrees ≈ 1m
            if abs(pt[0] - existing[0]) < 0.00001 and abs(pt[1] - existing[1]) < 0.00001:
                is_dup = True
                break
        if not is_dup:
            unique_points.append(pt)

    # Use convex hull to create clean boundary
    hull = convex_hull(unique_points)
    coords_proj = points_to_projected(hull)

    # Close the polygon
    if coords_proj[0] != coords_proj[-1]:
        coords_proj.append(coords_proj[0])

    area_m2 = compute_polygon_area(coords_proj)

    return {
        "type": "Feature",
        "properties": {
            "aoi_id": "san_lorenzo_plains",
            "site": "san_lorenzo",
            "zone": "plains",
            "name": "The Plains",
            "penguin_count": 453,
            "area_ha": round(area_m2 / 10000, 4),
            "density_per_ha": round(453 / (area_m2 / 10000), 2),
            "notes": "Convex hull of top/bottom edge waypoints",
            "source": "GPS Ground Truthing Notes 2025 - RD.pdf"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords_proj]
        }
    }


def convex_hull(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Compute convex hull using monotone chain algorithm."""
    if len(points) < 3:
        return points

    # Project to UTM for 2D hull computation
    pts = []
    for lat, lon in points:
        x, y = wgs84_to_projected(lat, lon)
        pts.append((x, y, lat, lon))

    # Sort by x then y
    pts.sort(key=lambda p: (p[0], p[1]))

    def cross(o, a, b) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    # Build lower hull
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    # Build upper hull
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    # Concatenate, removing duplicate endpoints
    hull = lower[:-1] + upper[:-1]
    return [(lat, lon) for _, _, lat, lon in hull]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create San Lorenzo AOI polygons from GPS waypoints."
    )
    parser.add_argument(
        "--waypoints",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "san_lorenzo_waypoints.csv",
        help="Input waypoints CSV file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "aoi_san_lorenzo_epsg5345.geojson",
        help="Output GeoJSON file path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output without writing file",
    )
    args = parser.parse_args()

    if not args.waypoints.exists():
        print(f"Error: Waypoints file not found: {args.waypoints}")
        return 1

    print(f"Loading waypoints from: {args.waypoints}")
    waypoints = load_waypoints_by_type(args.waypoints)

    features = []

    # Build Caves polygon
    if "caves" in waypoints:
        caves_feature = build_caves_polygon(waypoints["caves"])
        if caves_feature:
            features.append(caves_feature)
            print(f"  Caves: {len(caves_feature['geometry']['coordinates'][0])} vertices, "
                  f"{caves_feature['properties']['area_ha']:.4f} ha")

    # Build Plains polygon (with corrected winding order)
    if "plains" in waypoints:
        plains_feature = build_plains_polygon(waypoints["plains"])
        if plains_feature:
            features.append(plains_feature)
            print(f"  Plains: {len(plains_feature['geometry']['coordinates'][0])} vertices, "
                  f"{plains_feature['properties']['area_ha']:.4f} ha")

    output = {
        "type": "FeatureCollection",
        "name": "san_lorenzo_aois_epsg5345",
        "crs": {"epsg": TARGET_EPSG},
        "features": features
    }

    if args.dry_run:
        print("\nDry run - would write:")
        print(json.dumps(output, indent=2))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"\nWrote {len(features)} features to: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
