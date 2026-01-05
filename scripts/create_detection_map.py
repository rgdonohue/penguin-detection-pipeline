#!/usr/bin/env python3
"""
Create interactive Folium map from LiDAR detection GeoJSON.

Overlays detections on satellite imagery for ground truth validation.

Usage:
    python scripts/create_detection_map.py \
        --geojson data/interim/lidar_hag_geojson/cloud0_detections.geojson \
        --output qc/panels/detection_map.html \
        --title "Caleta Box Count 1 - LiDAR Detections"
"""

import argparse
import json
import os
from pathlib import Path
from typing import Optional

try:
    import folium
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: folium\n"
        "Install with: pip install folium"
    ) from exc

try:
    from pyproj import Transformer
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: pyproj\n"
        "Install with: pip install pyproj"
    ) from exc


def load_geojson(path: Path) -> dict:
    """Load GeoJSON file."""
    with open(path) as f:
        return json.load(f)


def create_detection_map(
    geojson_path: Path,
    output_path: Path,
    title: str = "LiDAR Detections",
    ground_truth_path: Optional[Path] = None,
    source_crs: str = "EPSG:32720",  # UTM Zone 20S (Argentina)
    mapbox_token: Optional[str] = None,
) -> None:
    """
    Create interactive Folium map with detections.

    Args:
        geojson_path: Path to detection GeoJSON
        output_path: Output HTML path
        title: Map title
        ground_truth_path: Optional CSV with ground truth points
        source_crs: Source coordinate system (default: UTM 20S for Argentina)
    """
    # Load detections
    data = load_geojson(geojson_path)
    features = data.get("features", [])
    metadata = data.get("metadata") or {}

    if not features:
        print(f"No features found in {geojson_path}")
        return

    # Prefer CRS embedded by the producer (if present).
    inferred_epsg: Optional[int] = None
    if isinstance(metadata, dict):
        crs_meta = metadata.get("crs")
        if isinstance(crs_meta, dict) and "epsg" in crs_meta and crs_meta["epsg"] is not None:
            try:
                inferred_epsg = int(crs_meta["epsg"])
            except Exception:
                inferred_epsg = None
        # If the file says coordinates are degrees, treat as WGS84.
        if inferred_epsg is None and metadata.get("coord_units") == "degrees":
            inferred_epsg = 4326

    effective_source_crs = f"EPSG:{inferred_epsg}" if inferred_epsg is not None else source_crs
    already_wgs84 = effective_source_crs.upper() in {"EPSG:4326", "WGS84"}

    # Create transformer to WGS84 (lat/lon) only when needed.
    transformer = None if already_wgs84 else Transformer.from_crs(effective_source_crs, "EPSG:4326", always_xy=True)

    # Transform all coordinates to lat/lon
    transformed_features = []
    for f in features:
        x, y = f["geometry"]["coordinates"]
        if transformer is None:
            lon, lat = float(x), float(y)
            utm_x, utm_y = None, None
        else:
            utm_x, utm_y = float(x), float(y)
            lon, lat = transformer.transform(utm_x, utm_y)
        transformed_features.append({
            "lon": lon,
            "lat": lat,
            "utm_x": utm_x,
            "utm_y": utm_y,
            "props": f.get("properties", {}),
        })

    center_lon = sum(tf["lon"] for tf in transformed_features) / len(transformed_features)
    center_lat = sum(tf["lat"] for tf in transformed_features) / len(transformed_features)

    # Create map with satellite imagery
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=18,
        tiles=None,  # We'll add custom tiles
    )

    # Add satellite basemap (Esri World Imagery) - default
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Esri Satellite",
        overlay=False,
        control=True,
    ).add_to(m)

    if mapbox_token is None:
        mapbox_token = os.environ.get("MAPBOX_TOKEN")

    if mapbox_token:
        # Mapbox Satellite (high resolution, requires token)
        folium.TileLayer(
            tiles=(
                "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/"
                "{z}/{x}/{y}?access_token=" + mapbox_token
            ),
            attr="Mapbox",
            name="Mapbox Satellite",
            overlay=False,
            control=True,
            tileSize=512,
            zoomOffset=-1,
        ).add_to(m)

        # Mapbox Satellite Streets (satellite + labels)
        folium.TileLayer(
            tiles=(
                "https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/tiles/"
                "{z}/{x}/{y}?access_token=" + mapbox_token
            ),
            attr="Mapbox",
            name="Mapbox Hybrid",
            overlay=False,
            control=True,
            tileSize=512,
            zoomOffset=-1,
        ).add_to(m)

    # Google Satellite (backup - TOS gray area)
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google",
        name="Google Satellite",
        overlay=False,
        control=True,
    ).add_to(m)

    # OpenStreetMap as fallback
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True,
    ).add_to(m)

    # CartoDB Positron (clean, light basemap for presentations)
    folium.TileLayer(
        tiles="CartoDB positron",
        name="CartoDB Light",
        overlay=False,
        control=True,
    ).add_to(m)

    # Create feature group for detections
    detection_group = folium.FeatureGroup(name=f"Detections ({len(transformed_features)})")

    # Add detection markers
    for i, tf in enumerate(transformed_features):
        props = tf["props"]
        lat, lon = tf["lat"], tf["lon"]
        utm_x, utm_y = tf["utm_x"], tf["utm_y"]

        # Create popup with detection info
        popup_html = f"""
        <div style="font-family: monospace; font-size: 12px;">
            <b>Detection #{i+1}</b><br>
            <hr style="margin: 5px 0;">
            <b>HAG:</b> {props.get('hag_mean', 0):.2f}m (max: {props.get('hag_max', 0):.2f}m)<br>
            <b>Area:</b> {props.get('area_m2', 0):.2f} m² ({props.get('area_cells', 0)} cells)<br>
            <b>Circularity:</b> {props.get('circularity', 0):.2f}<br>
            <b>Solidity:</b> {props.get('solidity', 0):.2f}<br>
            <hr style="margin: 5px 0;">
            <b>XY:</b> {'' if utm_x is None else f'{utm_x:.1f} E, {utm_y:.1f} N'}<br>
            <b>WGS84:</b> {lat:.6f}, {lon:.6f}
        </div>
        """

        # Color by HAG: yellow (low) -> orange (mid) -> red (high)
        hag = props.get('hag_mean', 0.3)
        if hag >= 0.45:
            color = '#e31a1c'  # Red - tallest
        elif hag >= 0.35:
            color = '#fd8d3c'  # Orange - mid
        else:
            color = '#fecc5c'  # Yellow - shortest

        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            popup=folium.Popup(popup_html, max_width=300),
            color=None,
            fill=True,
            fillColor=color,
            fillOpacity=0.85,
            weight=0,
        ).add_to(detection_group)

    detection_group.add_to(m)

    # Add ground truth if provided
    if ground_truth_path and ground_truth_path.exists():
        gt_group = folium.FeatureGroup(name="Ground Truth")
        # TODO: Load and add ground truth points
        # This will be implemented when GPS waypoints are extracted
        gt_group.add_to(m)

    # Add layer control
    folium.LayerControl().add_to(m)

    # Add title
    title_html = f'''
    <div style="position: fixed;
                top: 10px; left: 50px;
                background-color: white;
                padding: 10px;
                border-radius: 5px;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
                z-index: 9999;
                font-family: Arial, sans-serif;">
        <b>{title}</b><br>
        <span style="font-size: 12px; color: #666;">
            {len(transformed_features)} detections |
            <span style="color: #fecc5c;">●</span> HAG&lt;0.35m
            <span style="color: #fd8d3c;">●</span> HAG 0.35-0.45m
            <span style="color: #e31a1c;">●</span> HAG≥0.45m
        </span>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))

    # Save map
    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))
    print(f"Map saved to: {output_path}")
    print(f"  - {len(features)} detections plotted")
    print(f"  - Center: {center_lat:.6f}, {center_lon:.6f}")


def main():
    parser = argparse.ArgumentParser(
        description="Create interactive Folium map from LiDAR detections"
    )
    parser.add_argument(
        "--geojson", "-g",
        type=Path,
        required=True,
        help="Path to detection GeoJSON file"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("qc/panels/detection_map.html"),
        help="Output HTML file path"
    )
    parser.add_argument(
        "--title", "-t",
        type=str,
        default="LiDAR Detections",
        help="Map title"
    )
    parser.add_argument(
        "--ground-truth", "-gt",
        type=Path,
        default=None,
        help="Optional ground truth CSV (lat,lon,label)"
    )
    parser.add_argument(
        "--source-crs",
        type=str,
        default="EPSG:32720",
        help="Override source CRS for GeoJSON coordinates (metadata is used when present)",
    )
    parser.add_argument(
        "--mapbox-token",
        type=str,
        default=None,
        help="Optional Mapbox access token (or set MAPBOX_TOKEN env var)",
    )

    args = parser.parse_args()

    if not args.geojson.exists():
        print(f"Error: GeoJSON not found: {args.geojson}")
        return 1

    create_detection_map(
        geojson_path=args.geojson,
        output_path=args.output,
        title=args.title,
        ground_truth_path=args.ground_truth,
        source_crs=args.source_crs,
        mapbox_token=args.mapbox_token,
    )
    return 0


if __name__ == "__main__":
    exit(main())
