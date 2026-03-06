#!/usr/bin/env python3
"""
Create AOI catalogue GeoJSON in WGS84 with boundary confidence metadata.

Usage:
    python scripts/create_aoi_catalogue.py \
        --output data/processed/aoi_catalogue_wgs84.geojson
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Optional

try:
    from pyproj import Transformer
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: pyproj\n"
        "Install with: pip install pyproj"
    ) from exc


PROJECT_ROOT = Path(__file__).parent.parent


def load_geojson(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def transform_coords(coords: Iterable, transformer: Transformer) -> list:
    transformed = []
    for lon, lat in coords:
        new_lon, new_lat = transformer.transform(lon, lat)
        transformed.append([new_lon, new_lat])
    return transformed


def transform_polygon(coords: list, transformer: Transformer) -> list:
    return [transform_coords(coords, transformer)]


def transform_geometry(geometry: dict, transformer: Transformer) -> dict:
    geom_type = geometry.get("type")
    if geom_type == "Polygon":
        return {
            "type": "Polygon",
            "coordinates": transform_polygon(geometry.get("coordinates", [[]])[0], transformer),
        }
    if geom_type == "MultiPolygon":
        polygons = []
        for poly in geometry.get("coordinates", []):
            if not poly:
                continue
            polygons.append(transform_polygon(poly[0], transformer))
        return {
            "type": "MultiPolygon",
            "coordinates": polygons,
        }
    if geom_type == "Point":
        lon, lat = geometry.get("coordinates", [None, None])
        new_lon, new_lat = transformer.transform(lon, lat)
        return {"type": "Point", "coordinates": [new_lon, new_lat]}
    return geometry


def polygon_centroid(coords: list[list[float]]) -> list[float]:
    if not coords:
        return [0.0, 0.0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return [sum(lons) / len(lons), sum(lats) / len(lats)]


def ensure_wgs84(feature: dict, source_epsg: int) -> dict:
    if source_epsg == 4326:
        return feature
    transformer = Transformer.from_crs(f"EPSG:{source_epsg}", "EPSG:4326", always_xy=True)
    geometry = transform_geometry(feature["geometry"], transformer)
    feature = dict(feature)
    feature["geometry"] = geometry
    return feature


def add_confidence_properties(feature: dict, confidence: str, notes: str) -> dict:
    props = dict(feature.get("properties", {}))
    props["boundary_confidence"] = confidence
    props["confidence_notes"] = notes
    feature["properties"] = props
    return feature


def make_missing_point(
    name: str,
    site: str,
    penguin_count: int,
    lon: float,
    lat: float,
    notes: str,
) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "name": name,
            "site": site,
            "penguin_count": penguin_count,
            "boundary_confidence": "missing",
            "confidence_notes": notes,
        },
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def load_source_features(path: Path, source_epsg: int, confidence_map: dict[str, tuple[str, str]]) -> list[dict]:
    data = load_geojson(path)
    features = []
    for feature in data.get("features", []):
        feature = ensure_wgs84(feature, source_epsg)
        aoi_id = feature.get("properties", {}).get("aoi_id")
        confidence, notes = confidence_map.get(
            aoi_id,
            ("reconstructed", "Boundary confidence not specified."),
        )
        feature = add_confidence_properties(feature, confidence, notes)
        features.append(feature)
    return features


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create AOI catalogue GeoJSON in WGS84 with confidence metadata."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "aoi_catalogue_wgs84.geojson",
        help="Output GeoJSON file path",
    )
    args = parser.parse_args()

    san_lorenzo_path = PROJECT_ROOT / "data" / "processed" / "aoi_san_lorenzo_epsg5345.geojson"
    caleta_islands_path = PROJECT_ROOT / "data" / "processed" / "aoi_caleta_islands_epsg32720.geojson"
    caleta_ground_truth_path = PROJECT_ROOT / "data" / "processed" / "aoi_caleta_small_island_ground_truth_epsg32720.geojson"

    features: list[dict] = []

    san_lorenzo_confidence = {
        "san_lorenzo_caves": ("reconstructed", "Waypoints + estimated left edge."),
        "san_lorenzo_plains": ("reconstructed", "Top/bottom edge waypoints; lateral bounds estimated."),
        "san_lorenzo_box_caves": ("confirmed", "4-corner GPS coordinates from PDF p.4 (Caves heading)."),
        "san_lorenzo_road": ("confirmed", "Convex hull of 34 GPS waypoints."),
    }
    features.extend(load_source_features(san_lorenzo_path, 5345, san_lorenzo_confidence))

    # Caleta LiDAR coverage polygons (full island footprints)
    caleta_coverage_confidence = {
        "caleta_small_island": ("confirmed", "LiDAR footprint-derived polygon (full coverage)."),
        "caleta_tiny_island": ("confirmed", "LiDAR footprint-derived polygon (full coverage)."),
    }
    features.extend(load_source_features(caleta_islands_path, 32720, caleta_coverage_confidence))

    # Caleta ground truth count area (subset of LiDAR coverage where penguins were counted)
    if caleta_ground_truth_path.exists():
        caleta_gt_confidence = {
            "caleta_small_island_ground_truth": (
                "reconstructed",
                "Count area reconstructed from PDF measurements; clipped at Y=5308823 to match 3.88 ha target.",
            ),
        }
        features.extend(load_source_features(caleta_ground_truth_path, 32720, caleta_gt_confidence))

    # Note: Missing AOI markers (Box Count - Caves, Caleta Box Counts)
    # are intentionally omitted. We have penguin counts but no boundary data,
    # and vague point markers at estimated locations are not useful for the map.
    # Counts are preserved in san_lorenzo_analysis.json for reference.

    features = sorted(
        features,
        key=lambda f: (
            f.get("properties", {}).get("site", ""),
            f.get("properties", {}).get("boundary_confidence", ""),
            f.get("properties", {}).get("name", ""),
        ),
    )

    output = {
        "type": "FeatureCollection",
        "name": "aoi_catalogue_wgs84",
        "crs": {"epsg": 4326, "name": "WGS 84"},
        "features": features,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(features)} AOI features to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
