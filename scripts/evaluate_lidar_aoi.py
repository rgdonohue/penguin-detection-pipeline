#!/usr/bin/env python3
"""
AOI-clipped evaluation for LiDAR detections.

This is an engineering/QC tool: given a LiDAR summary JSON (with x/y detections)
and AOI polygons (GeoJSON), it reports counts and densities inside each AOI.

No heavy geospatial dependencies are required; AOIs must be in the same CRS as
the LiDAR detections (typically a projected CRS in meters).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pipelines.aoi_eval import AoiEvalParams, run


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate LiDAR detections inside AOI polygons (GeoJSON).")
    p.add_argument("--lidar-summary", required=True, help="Path to LiDAR summary JSON (lidar_candidates).")
    p.add_argument("--aoi-geojson", required=True, help="Path to AOI polygons GeoJSON FeatureCollection.")
    p.add_argument("--out", required=True, help="Output JSON path.")
    p.add_argument(
        "--aoi-crs-epsg",
        type=int,
        default=None,
        help="Optional EPSG code for AOI polygons CRS (used for mismatch checks).",
    )
    p.add_argument(
        "--emit-detection-ids",
        action="store_true",
        help="Include the sorted detection IDs that fall inside each AOI (can be large).",
    )
    p.add_argument(
        "--allow-geographic-crs",
        action="store_true",
        help="Allow AOI CRS in degrees (EPSG:4326/CRS84). Area/density will be omitted.",
    )

    args = p.parse_args()
    out = run(
        AoiEvalParams(
            lidar_summary=Path(args.lidar_summary),
            aoi_geojson=Path(args.aoi_geojson),
            out_path=Path(args.out),
            aoi_crs_epsg=args.aoi_crs_epsg,
            emit_detection_ids=bool(args.emit_detection_ids),
            allow_geographic_crs=bool(args.allow_geographic_crs),
        )
    )
    print(str(out))


if __name__ == "__main__":
    main()


