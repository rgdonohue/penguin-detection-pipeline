#!/usr/bin/env python3
"""
Extract a "max visible land footprint" AOI polygon from LiDAR coverage.

This is intended for bounded natural AOIs like islands where the shoreline/land
extent is a defensible boundary in LiDAR space.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipelines.aoi_from_lidar import AoiFromLidarParams, run


def main() -> None:
    p = argparse.ArgumentParser(description="Derive island footprint AOI GeoJSON from LiDAR coverage.")
    p.add_argument("--data-root", required=True, help="Folder containing LAS/LAZ files (projected CRS).")
    p.add_argument("--out", required=True, help="Output AOI GeoJSON path.")
    p.add_argument("--crs-epsg", type=int, default=32720, help="EPSG code for input/output CRS (projected meters).")
    p.add_argument("--aoi-id", required=True, help="AOI identifier (e.g., caleta_tiny_island).")

    # Grid + morphology
    p.add_argument("--cell-res-m", type=float, default=1.0, help="Grid resolution in meters.")
    p.add_argument(
        "--threshold-method",
        type=str,
        default="fixed",
        choices=["fixed", "otsu"],
        help="Land mask threshold method: fixed count-per-cell or Otsu on non-zero densities.",
    )
    p.add_argument("--min-points-per-cell", type=int, default=1, help="Land mask threshold: points per cell.")
    p.add_argument("--closing-radius-m", type=float, default=2.0, help="Binary closing radius in meters.")
    p.add_argument("--opening-radius-m", type=float, default=1.0, help="Binary opening radius in meters.")
    p.add_argument("--no-fill-holes", action="store_true", help="Disable hole filling.")
    p.add_argument("--no-keep-largest", action="store_true", help="Do not keep only the largest connected component.")
    p.add_argument("--simplify-tol-m", type=float, default=None, help="Optional polygon simplification tolerance (meters).")
    p.add_argument(
        "--roi-from-detections",
        default=None,
        help="Optional LiDAR summary JSON to compute an ROI bbox from detection x/y (useful to isolate an island).",
    )
    p.add_argument("--roi-buffer-m", type=float, default=0.0, help="Buffer (meters) to expand the detection-derived ROI bbox.")

    # Metadata
    p.add_argument("--site", default=None, help="Site name (e.g., caleta).")
    p.add_argument("--zone", default=None, help="Zone name (e.g., tiny_island).")
    p.add_argument("--name", default=None, help="Human-friendly AOI name.")
    p.add_argument("--penguin-count", type=int, default=None, help="Observed field count for this AOI (optional).")
    p.add_argument("--expected-area-ha", type=float, default=None, help="Expected area (ha) for sanity checking (optional).")

    args = p.parse_args()

    props = {}
    if args.site:
        props["site"] = args.site
    if args.zone:
        props["zone"] = args.zone
    if args.name:
        props["name"] = args.name
    if args.penguin_count is not None:
        props["penguin_count"] = int(args.penguin_count)
    if args.expected_area_ha is not None:
        props["expected_area_ha"] = float(args.expected_area_ha)

    out_path = run(
        AoiFromLidarParams(
            data_root=Path(args.data_root),
            out_path=Path(args.out),
            crs_epsg=int(args.crs_epsg),
            aoi_id=str(args.aoi_id),
            cell_res_m=float(args.cell_res_m),
            threshold_method=str(args.threshold_method),
            min_points_per_cell=int(args.min_points_per_cell),
            closing_radius_m=float(args.closing_radius_m),
            opening_radius_m=float(args.opening_radius_m),
            fill_holes=not bool(args.no_fill_holes),
            keep_largest_component=not bool(args.no_keep_largest),
            simplify_tolerance_m=(float(args.simplify_tol_m) if args.simplify_tol_m is not None else None),
            roi_from_detections=(Path(args.roi_from_detections) if args.roi_from_detections else None),
            roi_buffer_m=float(args.roi_buffer_m),
            properties=props,
        )
    )
    print(str(out_path))

    # Optional: print quick sanity checks.
    try:
        obj = json.loads(Path(out_path).read_text())
        feat = (obj.get("features") or [None])[0] or {}
        pr = feat.get("properties") or {}
        area_m2 = pr.get("area_m2_poly") or pr.get("area_m2_mask")
        if area_m2 is not None:
            area_ha = float(area_m2) / 10_000.0
            print(json.dumps({"aoi_id": args.aoi_id, "area_ha": round(area_ha, 4)}, indent=2))
    except Exception:
        pass


if __name__ == "__main__":
    main()


