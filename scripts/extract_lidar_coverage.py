#!/usr/bin/env python3
"""
Extract LiDAR dataset coverage extents from data/2025 and output WGS84 GeoJSON.

This script reads LAS/LZ files, aggregates bounds per dataset directory, and
outputs bounding polygons in EPSG:4326 for web mapping.

Usage:
    python scripts/extract_lidar_coverage.py \
        --data-root data/2025 \
        --output data/processed/lidar_coverage_wgs84.geojson
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
from skimage import measure

try:
    import laspy
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: laspy\n"
        "Install with: pip install laspy"
    ) from exc

try:
    from pyproj import Transformer
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: pyproj\n"
        "Install with: pip install pyproj"
    ) from exc

# Import outline extraction functions from aoi_from_lidar pipeline
from pipelines.aoi_from_lidar import (
    _bounds_xy,
    _clean_mask,
    _density_grid,
    _land_mask,
    _simplify_ring_rdp,
    _stream_xy,
    polygonize_mask,
)


PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class DatasetBounds:
    name: str
    site: str
    source_epsg: int
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    point_count: int
    tile_count: int
    tiles: list[str]

    def update(self, bounds: dict, tile_name: str) -> None:
        self.min_x = min(self.min_x, bounds["min_x"])
        self.min_y = min(self.min_y, bounds["min_y"])
        self.max_x = max(self.max_x, bounds["max_x"])
        self.max_y = max(self.max_y, bounds["max_y"])
        self.point_count += bounds["point_count"]
        self.tile_count += 1
        self.tiles.append(tile_name)


THERMAL_TARGETS = [
    {"name": "0076_T", "yaw_deg": -88, "lat": -42.08526, "lon": -63.86692},
    {"name": "0116_T", "yaw_deg": 1, "lat": -42.08544, "lon": -63.86698},
    {"name": "0158_T", "yaw_deg": 90, "lat": -42.08537, "lon": -63.86713},
    {"name": "0197_T", "yaw_deg": -179, "lat": -42.08522, "lon": -63.86713},
]


def infer_epsg(path: Path) -> Optional[int]:
    path_str = str(path).lower()
    if "san_lorenzo_utm" in path_str:
        return 32720
    if "san lorenzo" in path_str or "san_lorenzo" in path_str:
        return 5345
    if "caleta" in path_str:
        return 32720
    return None


def infer_site(path: Path) -> str:
    path_str = str(path).lower()
    if "san lorenzo" in path_str or "san_lorenzo" in path_str:
        return "san_lorenzo"
    if "caleta" in path_str:
        return "caleta"
    return "unknown"


def list_las_files(data_root: Path) -> list[Path]:
    las_files = []
    for ext in (".las", ".laz"):
        las_files.extend(data_root.rglob(f"*{ext}"))
    return sorted(las_files)


def read_las_bounds(las_path: Path) -> Optional[dict]:
    try:
        with laspy.open(las_path) as handle:
            header = handle.header
            epsg = None
            try:
                crs = header.parse_crs()
                if crs and crs.to_epsg():
                    epsg = int(crs.to_epsg())
            except Exception:
                epsg = None

            if epsg is None:
                epsg = infer_epsg(las_path)

            return {
                "min_x": float(header.x_min),
                "min_y": float(header.y_min),
                "max_x": float(header.x_max),
                "max_y": float(header.y_max),
                "point_count": int(header.point_count),
                "epsg": epsg,
            }
    except Exception as exc:
        print(f"Warning: Failed to read {las_path}: {exc}")
        return None


def group_by_dataset(las_files: Iterable[Path], data_root: Path) -> dict[str, list[Path]]:
    datasets: dict[str, list[Path]] = {}
    for path in las_files:
        if path.parent == data_root:
            key = path.stem
        else:
            key = path.parent.name
        datasets.setdefault(key, []).append(path)
    for key in datasets:
        datasets[key] = sorted(datasets[key])
    return dict(sorted(datasets.items()))


def reproject_bbox_to_wgs84(bounds: DatasetBounds) -> list[list[float]]:
    transformer = Transformer.from_crs(f"EPSG:{bounds.source_epsg}", "EPSG:4326", always_xy=True)
    corners = [
        (bounds.min_x, bounds.min_y),
        (bounds.min_x, bounds.max_y),
        (bounds.max_x, bounds.max_y),
        (bounds.max_x, bounds.min_y),
        (bounds.min_x, bounds.min_y),
    ]
    coords = []
    for x, y in corners:
        lon, lat = transformer.transform(x, y)
        coords.append([lon, lat])
    return coords


def reproject_polygon_to_wgs84(
    polygon_coords: list[list[float]], source_epsg: int
) -> list[list[float]]:
    """Reproject a polygon from source CRS to WGS84.

    Args:
        polygon_coords: List of [x, y] coordinates in source CRS
        source_epsg: Source CRS EPSG code

    Returns:
        List of [lon, lat] coordinates in WGS84
    """
    transformer = Transformer.from_crs(f"EPSG:{source_epsg}", "EPSG:4326", always_xy=True)
    wgs84_coords = []
    for x, y in polygon_coords:
        lon, lat = transformer.transform(x, y)
        wgs84_coords.append([lon, lat])
    return wgs84_coords


def compute_dataset_outline(
    dataset: DatasetBounds,
    las_files: list[Path],
    data_root: Path,
    cell_res_m: float = 2.0,
    simplify_tol_m: Optional[float] = 5.0,
    chunk_size: int = 1_000_000,
) -> Optional[dict]:
    """Compute actual outline polygon(s) for a dataset using density grid + contour extraction.

    Returns GeoJSON geometry dict (Polygon or MultiPolygon) or None if extraction fails.
    """
    # Get all LAS files for this dataset by matching tile names
    dataset_files = []
    tile_names_set = set(dataset.tiles)
    for f in las_files:
        if f.name in tile_names_set or f.stem in tile_names_set:
            dataset_files.append(f)
    
    # If no matches by tile name, try matching by dataset name (for single-file datasets)
    if not dataset_files:
        for f in las_files:
            if dataset.name in f.name or dataset.name in str(f.parent):
                dataset_files.append(f)
    
    if not dataset_files:
        print(f"Warning: No LAS files found for dataset {dataset.name} (tiles: {dataset.tiles})")
        return None

    try:
        # Compute bounds
        mins_xy, maxs_xy = _bounds_xy(dataset_files)
        mins_xy = np.asarray(mins_xy, dtype=np.float64)
        maxs_xy = np.asarray(maxs_xy, dtype=np.float64)

        # Build density grid
        counts = _density_grid(dataset_files, mins_xy, maxs_xy, cell_res_m, chunk_size)

        # Create land mask (fixed threshold, min 1 point per cell)
        mask = _land_mask(counts, method="fixed", min_points_per_cell=1)

        # Clean mask (morphological operations)
        mask = _clean_mask(
            mask,
            cell_res_m=cell_res_m,
            closing_radius_m=2.0,
            opening_radius_m=1.0,
            fill_holes=True,
            keep_largest=False,  # Keep all components for multi-island datasets
        )

        # Extract all contours (not just the largest)
        contours = measure.find_contours(mask.astype(np.uint8), level=0.5)
        if not contours:
            return None

        # Convert contours to polygons in source CRS
        origin_xy = (float(mins_xy[0]), float(mins_xy[1]))
        rings: list[list[list[float]]] = []
        for c in contours:
            if c.shape[0] < 3:
                continue
            # c is Nx2 in (row, col) float coords
            xs = origin_xy[0] + c[:, 1] * cell_res_m
            ys = origin_xy[1] + c[:, 0] * cell_res_m
            ring = [[float(x), float(y)] for x, y in zip(xs, ys)]
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            # Apply simplification if requested
            if simplify_tol_m is not None and simplify_tol_m > 0 and len(ring) >= 6:
                ring = _simplify_ring_rdp(ring, simplify_tol_m)
            if len(ring) >= 4:
                rings.append(ring)

        if not rings:
            return None

        # Reproject to WGS84
        wgs84_rings = [reproject_polygon_to_wgs84(ring, dataset.source_epsg) for ring in rings]

        # Return as Polygon (single ring) or MultiPolygon (multiple rings)
        if len(wgs84_rings) == 1:
            return {"type": "Polygon", "coordinates": [wgs84_rings[0]]}
        else:
            # MultiPolygon: multiple separate components
            return {"type": "MultiPolygon", "coordinates": [[ring] for ring in wgs84_rings]}

    except Exception as exc:
        print(f"Warning: Failed to compute outline for {dataset.name}: {exc}")
        return None


def dataset_to_feature(
    dataset: DatasetBounds,
    outline_mode: str = "bbox",
    las_files: Optional[list[Path]] = None,
    data_root: Optional[Path] = None,
    cell_res_m: float = 2.0,
    simplify_tol_m: Optional[float] = 5.0,
) -> dict:
    """Convert DatasetBounds to GeoJSON feature.

    Args:
        dataset: Dataset bounds information
        outline_mode: "bbox", "outline", or "both"
        las_files: List of LAS files (required for outline mode)
        data_root: Root directory for LAS files (required for outline mode)
        cell_res_m: Grid resolution for outline extraction
        simplify_tol_m: Simplification tolerance for outline extraction
    """
    props = {
        "name": dataset.name,
        "site": dataset.site,
        "dataset_type": "lidar",
        "tile_count": dataset.tile_count,
        "point_count": dataset.point_count,
        "source_crs_epsg": dataset.source_epsg,
        "tiles": dataset.tiles,
    }

    if outline_mode == "bbox":
        coords = reproject_bbox_to_wgs84(dataset)
        geometry = {"type": "Polygon", "coordinates": [coords]}
        props["geometry_type"] = "bbox"
    elif outline_mode == "outline":
        if las_files is None or data_root is None:
            raise ValueError("las_files and data_root required for outline mode")
        geometry = compute_dataset_outline(
            dataset, las_files, data_root, cell_res_m=cell_res_m, simplify_tol_m=simplify_tol_m
        )
        if geometry is None:
            # Fallback to bbox if outline extraction fails
            coords = reproject_bbox_to_wgs84(dataset)
            geometry = {"type": "Polygon", "coordinates": [coords]}
            props["geometry_type"] = "bbox"
            props["outline_extraction_failed"] = True
        else:
            props["geometry_type"] = "outline"
            props["cell_res_m"] = cell_res_m
            if simplify_tol_m is not None:
                props["simplify_tol_m"] = simplify_tol_m
    else:  # both
        # Use outline if available, fallback to bbox
        if las_files is None or data_root is None:
            raise ValueError("las_files and data_root required for outline mode")
        geometry = compute_dataset_outline(
            dataset, las_files, data_root, cell_res_m=cell_res_m, simplify_tol_m=simplify_tol_m
        )
        if geometry is None:
            coords = reproject_bbox_to_wgs84(dataset)
            geometry = {"type": "Polygon", "coordinates": [coords]}
            props["geometry_type"] = "bbox"
        else:
            props["geometry_type"] = "outline"
            props["cell_res_m"] = cell_res_m
            if simplify_tol_m is not None:
                props["simplify_tol_m"] = simplify_tol_m

    return {
        "type": "Feature",
        "properties": props,
        "geometry": geometry,
    }


def thermal_targets_to_features() -> list[dict]:
    features = []
    for target in THERMAL_TARGETS:
        features.append({
            "type": "Feature",
            "properties": {
                "name": target["name"],
                "dataset_type": "thermal",
                "yaw_deg": target["yaw_deg"],
                "site": "san_lorenzo",
                "source": "LRF targets from GPS Ground Truthing Notes",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [target["lon"], target["lat"]],
            },
        })
    return features


def build_datasets(las_files: list[Path], data_root: Path) -> list[DatasetBounds]:
    grouped = group_by_dataset(las_files, data_root)
    datasets: list[DatasetBounds] = []
    for dataset_name, files in grouped.items():
        dataset_bounds: Optional[DatasetBounds] = None
        for path in files:
            bounds = read_las_bounds(path)
            if bounds is None or bounds["epsg"] is None:
                print(f"Warning: Skipping {path} (missing CRS)")
                continue
            site = infer_site(path)
            if dataset_bounds is None:
                dataset_bounds = DatasetBounds(
                    name=dataset_name,
                    site=site,
                    source_epsg=bounds["epsg"],
                    min_x=bounds["min_x"],
                    min_y=bounds["min_y"],
                    max_x=bounds["max_x"],
                    max_y=bounds["max_y"],
                    point_count=bounds["point_count"],
                    tile_count=1,
                    tiles=[path.name],
                )
            else:
                if dataset_bounds.source_epsg != bounds["epsg"]:
                    print(
                        f"Warning: CRS mismatch in {dataset_name} "
                        f"({dataset_bounds.source_epsg} vs {bounds['epsg']})"
                    )
                dataset_bounds.update(bounds, path.name)
        if dataset_bounds is not None:
            datasets.append(dataset_bounds)
    return datasets


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract LiDAR dataset extents into WGS84 GeoJSON."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=PROJECT_ROOT / "data" / "2025",
        help="Path to data/2025 root directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "lidar_coverage_wgs84.geojson",
        help="Output GeoJSON file path",
    )
    parser.add_argument(
        "--include-thermal",
        action="store_true",
        help="Include thermal target points in output",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Write output even if no LAS files are found",
    )
    parser.add_argument(
        "--outline-mode",
        choices=["bbox", "outline", "both"],
        default="bbox",
        help="Geometry extraction mode: bbox (fast, bounding boxes), outline (actual data footprint), both (outline with bbox fallback)",
    )
    parser.add_argument(
        "--cell-res",
        type=float,
        default=2.0,
        help="Grid resolution in meters for outline extraction (default: 2.0)",
    )
    parser.add_argument(
        "--simplify-tol",
        type=float,
        default=5.0,
        help="RDP simplification tolerance in meters for outline extraction (default: 5.0, set to 0 to disable)",
    )

    args = parser.parse_args()
    data_root = args.data_root

    las_files = list_las_files(data_root) if data_root.exists() else []
    if not las_files and not args.allow_empty:
        raise SystemExit(
            f"No LAS/LZ files found under {data_root}. "
            "Mount data/2025 or pass --allow-empty."
        )

    datasets = build_datasets(las_files, data_root)

    # Determine simplify tolerance (None means disable)
    simplify_tol = args.simplify_tol if args.simplify_tol > 0 else None

    features = [
        dataset_to_feature(
            ds,
            outline_mode=args.outline_mode,
            las_files=las_files,
            data_root=data_root,
            cell_res_m=args.cell_res,
            simplify_tol_m=simplify_tol,
        )
        for ds in datasets
    ]

    if args.include_thermal:
        features.extend(thermal_targets_to_features())

    features = sorted(features, key=lambda f: (f["properties"]["dataset_type"], f["properties"]["name"]))

    output = {
        "type": "FeatureCollection",
        "name": "lidar_coverage_wgs84",
        "crs": {"epsg": 4326, "name": "WGS 84"},
        "features": features,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(features)} features to {args.output}")
    if datasets:
        for ds in datasets:
            geom_type = next(
                (f["properties"].get("geometry_type", "unknown") for f in features if f["properties"]["name"] == ds.name),
                "unknown",
            )
            print(
                f"  - {ds.name}: {ds.tile_count} tiles, "
                f"{ds.point_count:,} points, EPSG:{ds.source_epsg}, geometry={geom_type}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
