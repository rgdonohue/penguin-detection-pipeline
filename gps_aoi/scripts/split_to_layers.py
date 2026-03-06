#!/usr/bin/env python3
"""
Split combined GeoJSON files into individual layer files with metadata.

Reads lidar_coverage_wgs84.geojson and GPS AOI GeoJSONs, outputs one file per
feature with accompanying YAML metadata describing source, mission, and groupings.

Extracts flight dates and sensor info from LAS file headers when available.

Usage:
    python split_to_layers.py --out-dir gps_aoi/data/layers
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Optional

try:
    import laspy
    HAS_LASPY = True
except ImportError:
    HAS_LASPY = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_2025 = PROJECT_ROOT / "data" / "2025"

# Mission groupings from GPS Ground Truthing Notes 2025 - RD.pdf
MISSION_INFO = {
    # GeoCue LiDAR missions (San Lorenzo) - TrueView 515 sensor
    "San Lorenzo Full LiDAR LAS": {
        "mission": "san_lorenzo_full",
        "sensor": "GeoCue TrueView 515",
        "sensor_type": "lidar",
        "site": "san_lorenzo",
        "flight_group": "geocue_san_lorenzo",
        "notes": "Full 66 ha coverage of San Lorenzo site",
    },
    "San Lorenzo Box Count 11.10 LAS": {
        "mission": "san_lorenzo_box_bushes",
        "sensor": "GeoCue TrueView 515",
        "sensor_type": "lidar",
        "site": "san_lorenzo",
        "flight_group": "geocue_san_lorenzo",
        "notes": "High Density Bushes box count area (tile 11.10)",
    },
    "San Lorenzo Box Count 11.9.25 LAS": {
        "mission": "san_lorenzo_box_caves",
        "sensor": "GeoCue TrueView 515",
        "sensor_type": "lidar",
        "site": "san_lorenzo",
        "flight_group": "geocue_san_lorenzo",
        "notes": "High Density Caves box count area (tile 11.9)",
    },
    "San_Lorenzo_UTM": {
        "mission": "san_lorenzo_box_counts_utm",
        "sensor": "GeoCue TrueView 515",
        "sensor_type": "lidar",
        "site": "san_lorenzo",
        "flight_group": "geocue_san_lorenzo",
        "notes": "Box count tiles in UTM projection (11.9 + 11.10)",
    },
    # L2 LiDAR missions (Caleta)
    "Caleta Tiny Island": {
        "mission": "caleta_tiny_island",
        "sensor": "L2 LiDAR",
        "sensor_type": "lidar",
        "site": "caleta",
        "flight_group": "l2_caleta",
        "notes": "Tiny Island coverage; 321 penguins, 0.7 ha",
    },
    "Caleta Small Island": {
        "mission": "caleta_small_island",
        "sensor": "L2 LiDAR",
        "sensor_type": "lidar",
        "site": "caleta",
        "flight_group": "l2_caleta",
        "notes": "Small Island coverage; 1,557 penguins, 4 ha",
    },
    "Caleta Box Count 1": {
        "mission": "caleta_box1",
        "sensor": "L2 LiDAR",
        "sensor_type": "lidar",
        "site": "caleta",
        "flight_group": "l2_caleta",
        "notes": "Mainland box count 1; 8 penguins",
    },
    "Caleta Box Count 2": {
        "mission": "caleta_box2",
        "sensor": "L2 LiDAR",
        "sensor_type": "lidar",
        "site": "caleta",
        "flight_group": "l2_caleta",
        "notes": "Mainland box count 2; 12 penguins",
    },
    # Thermal targets (H30T sensor)
    "0076_T": {
        "mission": "thermal_target_0076",
        "sensor": "DJI H30T",
        "sensor_type": "thermal",
        "site": "san_lorenzo",
        "flight_group": "h30t_san_lorenzo",
        "notes": "LRF thermal target point; yaw -88°",
    },
    "0116_T": {
        "mission": "thermal_target_0116",
        "sensor": "DJI H30T",
        "sensor_type": "thermal",
        "site": "san_lorenzo",
        "flight_group": "h30t_san_lorenzo",
        "notes": "LRF thermal target point; yaw 1°",
    },
    "0158_T": {
        "mission": "thermal_target_0158",
        "sensor": "DJI H30T",
        "sensor_type": "thermal",
        "site": "san_lorenzo",
        "flight_group": "h30t_san_lorenzo",
        "notes": "LRF thermal target point; yaw 90°",
    },
    "0197_T": {
        "mission": "thermal_target_0197",
        "sensor": "DJI H30T",
        "sensor_type": "thermal",
        "site": "san_lorenzo",
        "flight_group": "h30t_san_lorenzo",
        "notes": "LRF thermal target point; yaw -179°",
    },
}

# GPS AOI info
AOI_INFO = {
    "san_lorenzo_caves": {
        "mission": "gps_caves_total_count",
        "sensor": "GPS (field survey)",
        "sensor_type": "gps_aoi",
        "site": "san_lorenzo",
        "flight_group": "field_survey_san_lorenzo",
        "penguin_count": 908,
        "notes": "High Density Caves total count area; convex hull of start/end/edge waypoints",
    },
    "san_lorenzo_plains": {
        "mission": "gps_plains_total_count",
        "sensor": "GPS (field survey)",
        "sensor_type": "gps_aoi",
        "site": "san_lorenzo",
        "flight_group": "field_survey_san_lorenzo",
        "penguin_count": 453,
        "notes": "The Plains total count area; perimeter winding of top/bottom edge waypoints",
    },
    "san_lorenzo_box_caves": {
        "mission": "gps_box_caves",
        "sensor": "GPS (field survey)",
        "sensor_type": "gps_aoi",
        "site": "san_lorenzo",
        "flight_group": "field_survey_san_lorenzo",
        "penguin_count": 32,
        "notes": "High Density Caves box count; 4 corner GPS coords from PDF p.4. Previously misattributed to Bushes.",
    },
    "san_lorenzo_road": {
        "mission": "gps_road_total_count",
        "sensor": "GPS (field survey)",
        "sensor_type": "gps_aoi",
        "site": "san_lorenzo",
        "flight_group": "field_survey_san_lorenzo",
        "penguin_count": 359,
        "notes": "Road total count; NO WAYPOINTS IN PDF - boundary data needed",
    },
    "caleta_tiny_island": {
        "mission": "gps_caleta_tiny",
        "sensor": "GPS (field survey)",
        "sensor_type": "gps_aoi",
        "site": "caleta",
        "flight_group": "field_survey_caleta",
        "penguin_count": 321,
        "notes": "Tiny Island boundary; NO WAYPOINTS IN PDF - use LiDAR coverage instead",
    },
    "caleta_small_island": {
        "mission": "gps_caleta_small",
        "sensor": "GPS (field survey)",
        "sensor_type": "gps_aoi",
        "site": "caleta",
        "flight_group": "field_survey_caleta",
        "penguin_count": 1557,
        "notes": "Small Island boundary; NO WAYPOINTS IN PDF - use LiDAR coverage instead",
    },
    "caleta_box1": {
        "mission": "gps_caleta_box1",
        "sensor": "GPS (field survey)",
        "sensor_type": "gps_aoi",
        "site": "caleta",
        "flight_group": "field_survey_caleta",
        "penguin_count": 8,
        "notes": "Box Count 1 (mainland); NO WAYPOINTS IN PDF",
    },
    "caleta_box2": {
        "mission": "gps_caleta_box2",
        "sensor": "GPS (field survey)",
        "sensor_type": "gps_aoi",
        "site": "caleta",
        "flight_group": "field_survey_caleta",
        "penguin_count": 12,
        "notes": "Box Count 2 (mainland); NO WAYPOINTS IN PDF",
    },
}


def extract_las_metadata(tiles: list[str], dataset_name: str) -> dict[str, Any]:
    """Extract metadata from LAS file headers.
    
    Returns dict with creation_date, generating_software, system_identifier, etc.
    Uses the first tile found as representative of the dataset.
    """
    if not HAS_LASPY:
        return {}
    
    # Map dataset names to data paths
    DATASET_PATHS = {
        "Caleta Box Count 1": DATA_2025 / "Caleta Box Count 1",
        "Caleta Box Count 2": DATA_2025 / "Caleta Box Count 2",
        "Caleta Small Island": DATA_2025 / "Caleta Small Island",
        "Caleta Tiny Island": DATA_2025 / "Caleta Tiny Island",
        "San Lorenzo Full LiDAR LAS": DATA_2025 / "San Lorenzo Full LiDAR LAS.las",
        "San Lorenzo Box Count 11.10 LAS": DATA_2025 / "San Lorenzo Box Count 11.10 LAS.las",
        "San Lorenzo Box Count 11.9.25 LAS": DATA_2025 / "San Lorenzo Box Count 11.9.25 LAS.las",
        "San_Lorenzo_UTM": DATA_2025 / "San_Lorenzo_UTM",
    }
    
    base_path = DATASET_PATHS.get(dataset_name)
    if base_path is None:
        return {}
    
    # Find first LAS file
    las_path: Optional[Path] = None
    if base_path.is_file() and base_path.suffix.lower() in (".las", ".laz"):
        las_path = base_path
    elif base_path.is_dir():
        for tile in tiles:
            candidate = base_path / tile
            if candidate.exists():
                las_path = candidate
                break
        if las_path is None:
            # Try first .las in directory
            las_files = list(base_path.glob("*.las")) + list(base_path.glob("*.laz"))
            if las_files:
                las_path = las_files[0]
    
    if las_path is None or not las_path.exists():
        return {}
    
    try:
        with laspy.open(las_path) as f:
            h = f.header
            meta = {
                "las_version": str(h.version),
                "creation_date": str(h.creation_date) if h.creation_date else None,
                "generating_software": h.generating_software.strip() if h.generating_software else None,
                "system_identifier": h.system_identifier.strip() if h.system_identifier else None,
                "source_las_file": las_path.name,
            }
            # Parse system_identifier for sensor info
            sys_id = meta.get("system_identifier", "") or ""
            if "TrueView" in sys_id:
                meta["sensor_model"] = sys_id.split(":")[0] if ":" in sys_id else sys_id
                meta["sensor_serial"] = sys_id.split(":")[1] if ":" in sys_id else None
            elif "DJI" in (meta.get("generating_software") or ""):
                meta["sensor_model"] = "DJI L2"
            return meta
    except Exception as e:
        print(f"  Warning: Could not read LAS metadata from {las_path}: {e}")
        return {}


def slugify(name: str) -> str:
    """Convert name to filesystem-safe slug."""
    return name.lower().replace(" ", "_").replace(".", "_").replace("-", "_")


def write_geojson(feature: dict, out_path: Path) -> None:
    """Write single feature as FeatureCollection."""
    fc = {"type": "FeatureCollection", "features": [feature]}
    out_path.write_text(json.dumps(fc, indent=2), encoding="utf-8")


def write_metadata(meta: dict, out_path: Path) -> None:
    """Write metadata as YAML-like text (simple key: value format)."""
    lines = ["# Layer metadata", f"# Generated: {date.today().isoformat()}", ""]
    for key, value in meta.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def process_lidar_coverage(coverage_path: Path, out_dir: Path) -> list[dict]:
    """Split lidar coverage into individual files."""
    if not coverage_path.exists():
        print(f"  Warning: {coverage_path} not found")
        return []

    with open(coverage_path, encoding="utf-8") as f:
        data = json.load(f)

    results = []
    for feat in data["features"]:
        props = feat["properties"]
        name = props.get("name", "unnamed")
        slug = slugify(name)

        # Get mission info
        info = MISSION_INFO.get(name, {})
        sensor_type = info.get("sensor_type", props.get("dataset_type", "unknown"))

        # Extract LAS file metadata (flight dates, software, etc.)
        tiles = props.get("tiles", [])
        las_meta = extract_las_metadata(tiles, name) if sensor_type == "lidar" else {}

        # Build metadata
        meta = {
            "name": name,
            "slug": slug,
            "layer_type": "sensor_coverage",
            "sensor_type": sensor_type,
            "sensor": info.get("sensor", "unknown"),
            "site": info.get("site", props.get("site", "unknown")),
            "mission": info.get("mission", slug),
            "flight_group": info.get("flight_group", "unknown"),
            "source_file": str(coverage_path.name),
            "source_crs_epsg": props.get("source_crs_epsg"),
            "output_crs": "EPSG:4326 (WGS84)",
            "geometry_type": feat["geometry"]["type"],
            "point_count": props.get("point_count"),
            "tile_count": props.get("tile_count"),
            "tiles": props.get("tiles", []),
            "notes": info.get("notes", ""),
        }

        # Add LAS metadata if available
        if las_meta:
            meta["flight_date"] = las_meta.get("creation_date")
            meta["las_version"] = las_meta.get("las_version")
            meta["generating_software"] = las_meta.get("generating_software")
            meta["system_identifier"] = las_meta.get("system_identifier")
            meta["sensor_model"] = las_meta.get("sensor_model")
            meta["sensor_serial"] = las_meta.get("sensor_serial")
            meta["source_las_file"] = las_meta.get("source_las_file")

        # Write files
        geojson_path = out_dir / f"{slug}.geojson"
        meta_path = out_dir / f"{slug}.meta.txt"

        write_geojson(feat, geojson_path)
        write_metadata(meta, meta_path)

        flight_info = f" (flight: {las_meta.get('creation_date')})" if las_meta.get("creation_date") else ""
        results.append({"name": name, "slug": slug, "type": "coverage", "path": str(geojson_path.name), "flight_date": las_meta.get("creation_date")})
        print(f"  {geojson_path.name}{flight_info}")

    return results


def process_gps_aois(aoi_dir: Path, out_dir: Path) -> list[dict]:
    """Split GPS AOIs into individual files with metadata."""
    results = []

    for geojson_path in sorted(aoi_dir.glob("*_wgs84.geojson")):
        if "combined" in geojson_path.name:
            continue

        with open(geojson_path, encoding="utf-8") as f:
            data = json.load(f)

        if not data["features"]:
            # Empty AOI
            aoi_id = geojson_path.stem.replace("_wgs84", "")
            info = AOI_INFO.get(aoi_id, {})
            meta = {
                "name": info.get("mission", aoi_id),
                "slug": f"aoi_{aoi_id}",
                "layer_type": "gps_aoi",
                "sensor_type": "gps_aoi",
                "sensor": "GPS (field survey)",
                "site": info.get("site", "unknown"),
                "mission": info.get("mission", aoi_id),
                "flight_group": info.get("flight_group", "unknown"),
                "source_file": geojson_path.name,
                "output_crs": "EPSG:4326 (WGS84)",
                "geometry_type": "EMPTY",
                "penguin_count": info.get("penguin_count"),
                "notes": info.get("notes", "No waypoints available"),
                "status": "empty",
            }
            slug = f"aoi_{aoi_id}"
            meta_path = out_dir / f"{slug}.meta.txt"
            write_metadata(meta, meta_path)
            results.append({"name": aoi_id, "slug": slug, "type": "aoi", "path": None, "status": "empty"})
            print(f"  {slug}.meta.txt (empty AOI)")
            continue

        feat = data["features"][0]
        props = feat["properties"]
        aoi_id = props.get("aoi_id", geojson_path.stem.replace("_wgs84", ""))
        info = AOI_INFO.get(aoi_id, {})
        slug = f"aoi_{aoi_id}"

        meta = {
            "name": props.get("name", aoi_id),
            "slug": slug,
            "layer_type": "gps_aoi",
            "sensor_type": "gps_aoi",
            "sensor": "GPS (field survey)",
            "site": info.get("site", "unknown"),
            "mission": info.get("mission", aoi_id),
            "flight_group": info.get("flight_group", "unknown"),
            "source_file": geojson_path.name,
            "source_pdf": "GPS Ground Truthing Notes 2025 - RD.pdf",
            "output_crs": "EPSG:4326 (WGS84)",
            "geometry_type": feat["geometry"]["type"],
            "penguin_count": props.get("penguin_count") or info.get("penguin_count"),
            "notes": info.get("notes", ""),
            "status": "valid",
        }

        geojson_out = out_dir / f"{slug}.geojson"
        meta_path = out_dir / f"{slug}.meta.txt"

        write_geojson(feat, geojson_out)
        write_metadata(meta, meta_path)

        results.append({"name": aoi_id, "slug": slug, "type": "aoi", "path": str(geojson_out.name)})
        print(f"  {geojson_out.name}")

    return results


def write_index(results: list[dict], out_dir: Path) -> None:
    """Write index file listing all layers grouped by flight/mission."""
    # Group by flight_group and collect metadata
    groups: dict[str, list[dict]] = {}
    by_date: dict[str, list[dict]] = {}
    
    for r in results:
        # Read metadata to get flight_group and flight_date
        meta_path = out_dir / f"{r['slug']}.meta.txt"
        flight_group = "unknown"
        flight_date = r.get("flight_date")
        if meta_path.exists():
            for line in meta_path.read_text().splitlines():
                if line.startswith("flight_group:"):
                    flight_group = line.split(":", 1)[1].strip()
                if line.startswith("flight_date:") and not flight_date:
                    flight_date = line.split(":", 1)[1].strip()
        groups.setdefault(flight_group, []).append(r)
        if flight_date and flight_date != "None":
            by_date.setdefault(flight_date, []).append(r)

    lines = [
        "# Layer Index",
        f"# Generated: {date.today().isoformat()}",
        f"# Total layers: {len(results)}",
        "",
        "## By Flight Date",
        "",
    ]

    for flight_date in sorted(by_date.keys()):
        items = by_date[flight_date]
        lines.append(f"### {flight_date}")
        for item in items:
            path = item.get("path") or "(no geometry)"
            lines.append(f"  - {item['name']}: {path}")
        lines.append("")

    lines.append("## By Sensor/Mission Group")
    lines.append("")

    for group, items in sorted(groups.items()):
        lines.append(f"### {group}")
        for item in items:
            status = f" ({item.get('status', 'valid')})" if item.get("status") == "empty" else ""
            path = item.get("path") or "(no geometry)"
            flight_date = item.get("flight_date")
            date_str = f" [{flight_date}]" if flight_date and flight_date != "None" else ""
            lines.append(f"  - {item['name']}: {path}{date_str}{status}")
        lines.append("")

    lines.append("## All Layers")
    lines.append("")
    for r in sorted(results, key=lambda x: x["slug"]):
        path = r.get("path") or "(no geometry)"
        lines.append(f"- {r['slug']}: {path}")

    (out_dir / "INDEX.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Split combined GeoJSON into individual layer files")
    ap.add_argument("--out-dir", type=Path, default=Path("gps_aoi/data/layers"), help="Output directory")
    ap.add_argument(
        "--lidar-coverage",
        type=Path,
        default=Path("data/processed/lidar_coverage_wgs84.geojson"),
        help="LiDAR coverage GeoJSON",
    )
    ap.add_argument(
        "--aoi-dir",
        type=Path,
        default=Path("gps_aoi/data/output"),
        help="GPS AOI GeoJSON directory",
    )
    args = ap.parse_args()

    # Resolve paths
    out_dir = (PROJECT_ROOT / args.out_dir).resolve() if not args.out_dir.is_absolute() else args.out_dir
    lidar_path = (PROJECT_ROOT / args.lidar_coverage).resolve() if not args.lidar_coverage.is_absolute() else args.lidar_coverage
    aoi_dir = (PROJECT_ROOT / args.aoi_dir).resolve() if not args.aoi_dir.is_absolute() else args.aoi_dir

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output directory: {out_dir}")
    results = []

    print("\nProcessing LiDAR coverage...")
    results.extend(process_lidar_coverage(lidar_path, out_dir))

    print("\nProcessing GPS AOIs...")
    results.extend(process_gps_aois(aoi_dir, out_dir))

    print("\nWriting index...")
    write_index(results, out_dir)
    print("  INDEX.txt")

    print(f"\nDone. {len(results)} layers written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
