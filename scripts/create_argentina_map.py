#!/usr/bin/env python3
"""
Argentina Penguin Survey - Interactive AOI and Coverage Map.

Creates a Folium map with:
- LiDAR dataset coverage extents (polygons)
- AOI boundaries with confidence styling
- Missing AOIs as markers
- Thermal image targets as markers

Usage:
    python scripts/create_argentina_map.py \
        --lidar-coverage data/processed/lidar_coverage_wgs84.geojson \
        --aoi-catalogue data/processed/aoi_catalogue_wgs84.geojson \
        --output qc/panels/argentina_aoi_overview.html
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

try:
    import folium
    from folium import plugins
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: folium\n"
        "Install with: pip install folium"
    ) from exc


@dataclass
class SiteCenter:
    lat: float
    lon: float
    zoom: int


CONFIDENCE_STYLES = {
    "confirmed": {"color": "#2ecc71", "fill": True, "fill_opacity": 0.25, "dash_array": None},
    "reconstructed": {"color": "#f39c12", "fill": False, "fill_opacity": 0.0, "dash_array": "8,4"},
    "missing": {"color": "#e74c3c"},
}


PROJECT_ROOT = Path(__file__).parent.parent


def load_geojson(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def iter_polygon_coords(geometry: dict) -> Iterable[list[list[float]]]:
    geom_type = geometry.get("type")
    if geom_type == "Polygon":
        coords = geometry.get("coordinates", [[]])[0]
        if coords:
            yield coords
    elif geom_type == "MultiPolygon":
        for poly in geometry.get("coordinates", []):
            if poly and poly[0]:
                yield poly[0]


def lonlat_to_latlon(coords: Iterable[list[float]]) -> list[list[float]]:
    return [[lat, lon] for lon, lat in coords]


def centroid_from_coords(coords: Iterable[list[float]]) -> list[float]:
    points = list(coords)
    if not points:
        return [0.0, 0.0]
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return [sum(lons) / len(lons), sum(lats) / len(lats)]


def build_site_centers(features: list[dict]) -> dict[str, SiteCenter]:
    site_points: dict[str, list[list[float]]] = {}
    for feature in features:
        props = feature.get("properties", {})
        site = props.get("site")
        if not site:
            continue
        geom = feature.get("geometry", {})
        if geom.get("type") == "Point":
            lon, lat = geom.get("coordinates", [None, None])
            if lon is not None and lat is not None:
                site_points.setdefault(site, []).append([lon, lat])
        else:
            for coords in iter_polygon_coords(geom):
                site_points.setdefault(site, []).append(centroid_from_coords(coords))

    centers = {}
    for site, points in site_points.items():
        lons = [p[0] for p in points]
        lats = [p[1] for p in points]
        centers[site] = SiteCenter(
            lat=sum(lats) / len(lats),
            lon=sum(lons) / len(lons),
            zoom=15 if site == "san_lorenzo" else 16,
        )
    return centers


def add_site_selector(m: folium.Map, centers: dict[str, SiteCenter], output_path: Path) -> None:
    """Add site selector buttons and inject JavaScript after map initialization."""
    map_id = m.get_name()
    buttons_html = []
    button_data = []
    for site, center in centers.items():
        label = "San Lorenzo" if site == "san_lorenzo" else "Caleta"
        buttons_html.append(
            f'<button id="btn-{site}" style="margin: 2px; padding: 4px 8px;">{label}</button>'
        )
        button_data.append({
            "id": f"btn-{site}",
            "lat": center.lat,
            "lon": center.lon,
            "zoom": center.zoom,
        })
    
    html = f"""
    <div id="site-selector" style="position: fixed; top: 180px; left: 10px; z-index: 9999;
                background: rgba(255,255,255,0.9); padding: 8px; border-radius: 6px;">
        <b>Jump to site</b><br>
        {''.join(buttons_html)}
    </div>
    """
    m.get_root().html.add_child(folium.Element(html))
    
    # Save map first, then inject JavaScript at the end of the script section
    m.save(str(output_path))
    
    # Read the saved HTML, move </body> to the end, and inject JavaScript.
    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    button_data_json = json.dumps(button_data)
    js_code = f"""
    <script>
        // Site selector button handlers
        (function() {{
            function setupButtons() {{
                if (typeof {map_id} === 'undefined') {{
                    setTimeout(setupButtons, 50);
                    return;
                }}
                var buttonData = {button_data_json};
                for (var i = 0; i < buttonData.length; i++) {{
                    var btn = document.getElementById(buttonData[i].id);
                    if (btn) {{
                        (function(btnId, lat, lon, zoom) {{
                            var button = document.getElementById(btnId);
                            if (button) {{
                                button.onclick = function() {{
                                    {map_id}.setView([lat, lon], zoom);
                                }};
                            }}
                        }})(buttonData[i].id, buttonData[i].lat, buttonData[i].lon, buttonData[i].zoom);
                    }}
                }}
            }}
            // Wait for page to be fully loaded
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', setupButtons);
            }} else {{
                setupButtons();
            }}
        }})();
    </script>
"""
    
    # Ensure </body> is placed just before </html> (Folium writes scripts after </body>)
    if "</body>" in content and "</html>" in content:
        content = content.replace("</body>", "", 1)
        content = content.replace("</html>", "</body>\n</html>", 1)

    # Insert the script tag before </body>
    if "</body>" in content:
        content = content.replace("</body>", js_code + "\n</body>", 1)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


def create_map(
    output_path: Path,
    lidar_coverage_path: Path,
    aoi_catalogue_path: Path,
    detections_path: Optional[Path] = None,
) -> None:
    lidar_data = load_geojson(lidar_coverage_path)
    aoi_data = load_geojson(aoi_catalogue_path)

    aoi_features = aoi_data.get("features", [])
    centers = build_site_centers(aoi_features)
    default_center = centers.get("san_lorenzo", SiteCenter(lat=-42.086, lon=-63.871, zoom=15))

    m = folium.Map(
        location=[default_center.lat, default_center.lon],
        zoom_start=default_center.zoom,
        tiles=None,
    )

    # Single basemap: Google Satellite
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google",
        name="Google Satellite",
        overlay=False,
        control=True,
    ).add_to(m)

    # Layer groups
    coverage_group = folium.FeatureGroup(name="LiDAR Coverage Extents", show=True)
    thermal_group = folium.FeatureGroup(name="Thermal Image Targets", show=False)
    confirmed_group = folium.FeatureGroup(name="AOI Boundaries (Confirmed)", show=True)
    reconstructed_group = folium.FeatureGroup(name="AOI Boundaries (Reconstructed)", show=True)
    missing_group = folium.FeatureGroup(name="Ground Truth Markers (Missing Boundaries)", show=True)

    # LiDAR coverage + thermal targets
    for feature in lidar_data.get("features", []):
        props = feature.get("properties", {})
        dataset_type = props.get("dataset_type")
        geom = feature.get("geometry", {})
        if dataset_type == "thermal" and geom.get("type") == "Point":
            lon, lat = geom.get("coordinates", [None, None])
            popup = (
                f"{props.get('name')}<br>"
                f"Yaw: {props.get('yaw_deg')} deg<br>"
                f"Site: {props.get('site', 'unknown')}"
            )
            folium.Marker(
                location=[lat, lon],
                popup=popup,
                tooltip=f"Thermal target {props.get('name')}",
                icon=folium.Icon(color="purple", icon="camera", prefix="fa"),
            ).add_to(thermal_group)
            continue

        if geom.get("type") != "Polygon":
            continue

        coords = geom.get("coordinates", [[]])[0]
        polygon = lonlat_to_latlon(coords)
        popup = (
            f"{props.get('name')}<br>"
            f"Tiles: {props.get('tile_count', 0)}<br>"
            f"Points: {props.get('point_count', 0):,}<br>"
            f"CRS: EPSG:{props.get('source_crs_epsg')}"
        )
        folium.Polygon(
            locations=polygon,
            color="#3498db",
            weight=2,
            fill=True,
            fillColor="#3498db",
            fillOpacity=0.15,
            popup=popup,
            tooltip=f"{props.get('name')} (LiDAR coverage)",
        ).add_to(coverage_group)

    # AOI boundaries
    for feature in aoi_features:
        props = feature.get("properties", {})
        confidence = props.get("boundary_confidence", "reconstructed")
        geom = feature.get("geometry", {})
        name = props.get("name", "AOI")
        penguin_count = props.get("penguin_count", 0)
        notes = props.get("confidence_notes", "")

        if geom.get("type") == "Point":
            lon, lat = geom.get("coordinates", [None, None])
            popup = f"{name}: {penguin_count} penguins<br>{notes}"
            folium.Marker(
                location=[lat, lon],
                popup=popup,
                tooltip=f"{name}: {penguin_count}",
                icon=folium.Icon(color="red", icon="info-sign"),
            ).add_to(missing_group)
            continue

        style = CONFIDENCE_STYLES.get(confidence, CONFIDENCE_STYLES["reconstructed"])
        for coords in iter_polygon_coords(geom):
            polygon = lonlat_to_latlon(coords)
            popup = (
                f"{name}: {penguin_count} penguins<br>"
                f"Confidence: {confidence}<br>"
                f"{notes}"
            )
            folium.Polygon(
                locations=polygon,
                color=style["color"],
                weight=2,
                fill=style.get("fill", False),
                fillColor=style["color"],
                fillOpacity=style.get("fill_opacity", 0.0),
                dash_array=style.get("dash_array"),
                popup=popup,
                tooltip=f"{name}: {penguin_count} penguins",
            ).add_to(confirmed_group if confidence == "confirmed" else reconstructed_group)

    coverage_group.add_to(m)
    thermal_group.add_to(m)
    confirmed_group.add_to(m)
    reconstructed_group.add_to(m)
    missing_group.add_to(m)

    # Optional detections overlay
    if detections_path and detections_path.exists():
        detections = load_geojson(detections_path)
        det_group = folium.FeatureGroup(name="Detections", show=False)
        for feature in detections.get("features", []):
            geom = feature.get("geometry", {})
            if geom.get("type") != "Point":
                continue
            lon, lat = geom.get("coordinates", [None, None])
            folium.CircleMarker(
                location=[lat, lon],
                radius=3,
                color="#e31a1c",
                fill=True,
                fillOpacity=0.7,
                weight=0,
            ).add_to(det_group)
        det_group.add_to(m)

    # Summary panel
    site_totals = {"san_lorenzo": 0, "caleta": 0}
    for feature in aoi_features:
        props = feature.get("properties", {})
        site = props.get("site")
        if site in site_totals:
            site_totals[site] += int(props.get("penguin_count", 0) or 0)
    grand_total = site_totals["san_lorenzo"] + site_totals["caleta"]

    summary_html = f"""
    <div style="position: fixed;
                top: 10px; left: 10px;
                background: rgba(255,255,255,0.95);
                padding: 12px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                z-index: 9998;
                font-family: Arial, sans-serif;
                max-width: 260px;">
        <h3 style="margin: 0 0 8px 0; color: #333;">Argentina Survey 2025</h3>
        <table style="font-size: 12px; width: 100%;">
            <tr><td><b>San Lorenzo</b></td><td align="right">{site_totals['san_lorenzo']}</td></tr>
            <tr><td><b>Caleta</b></td><td align="right">{site_totals['caleta']}</td></tr>
            <tr style="border-top: 1px solid #eee;"><td><b>Total</b></td><td align="right">{grand_total}</td></tr>
        </table>
        <p style="font-size: 10px; color: #666; margin-top: 8px;">
            AOI confidence is shown by line style (solid vs dashed).
        </p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(summary_html))

    # Legend
    legend_html = """
    <div style="position: fixed;
                bottom: 30px; left: 10px;
                background: rgba(255,255,255,0.95);
                padding: 10px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                z-index: 9999;
                font-family: Arial, sans-serif;
                font-size: 11px;">
        <b>Legend</b><br>
        <span style="color:#3498db;">■</span> LiDAR coverage extent<br>
        <span style="color:#2ecc71;">■</span> Confirmed AOI boundary<br>
        <span style="color:#f39c12;">■</span> Reconstructed AOI (dashed)<br>
        <span style="color:#e74c3c;">●</span> Missing boundary (marker)<br>
        <span style="color:#9b59b6;">●</span> Thermal target<br>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)
    plugins.Fullscreen().add_to(m)
    plugins.MousePosition(
        position="bottomright",
        separator=" | ",
        prefix="Cursor:",
    ).add_to(m)
    plugins.MiniMap(
        tile_layer=folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            attr="Google",
        ),
        toggle_display=True,
        minimized=True,
    ).add_to(m)
    plugins.MeasureControl(position="topleft").add_to(m)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    add_site_selector(m, centers, output_path)

    print(f"Map saved to: {output_path}")
    print(f"  San Lorenzo: {site_totals['san_lorenzo']}")
    print(f"  Caleta: {site_totals['caleta']}")
    print(f"  Total: {grand_total}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create Argentina AOI and LiDAR coverage web map"
    )
    parser.add_argument(
        "--lidar-coverage",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "lidar_coverage_wgs84.geojson",
        help="LiDAR coverage GeoJSON (WGS84)",
    )
    parser.add_argument(
        "--aoi-catalogue",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "aoi_catalogue_wgs84.geojson",
        help="AOI catalogue GeoJSON (WGS84)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("qc/panels/argentina_aoi_overview.html"),
        help="Output HTML file",
    )
    parser.add_argument(
        "--detections",
        "-d",
        type=Path,
        default=None,
        help="Optional detection GeoJSON (WGS84)",
    )

    args = parser.parse_args()
    if not args.lidar_coverage.exists():
        raise SystemExit(f"LiDAR coverage file not found: {args.lidar_coverage}")
    if not args.aoi_catalogue.exists():
        raise SystemExit(f"AOI catalogue file not found: {args.aoi_catalogue}")

    create_map(
        output_path=args.output,
        lidar_coverage_path=args.lidar_coverage,
        aoi_catalogue_path=args.aoi_catalogue,
        detections_path=args.detections,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
