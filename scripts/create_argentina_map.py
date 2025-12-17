#!/usr/bin/env python3
"""
Argentina Penguin Survey - Interactive Multi-Layer Map

Creates a comprehensive Folium map with:
- Ground truth count zones (polygons)
- GPS waypoint markers
- Penguin density heatmaps
- Detection overlays (LiDAR/Thermal when available)
- Summary statistics panel

Sites:
- San Lorenzo: Caves (908), Plains (453), Road (359), Box Counts (32, 55)
- Caleta: Small Island (1557), Tiny Island (321), Box Counts (8, 12)

Usage:
    python scripts/create_argentina_map.py --output qc/panels/argentina_survey.html
"""

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional, Dict

try:
    import folium
    from folium import plugins
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: folium\n"
        "Install with: pip install folium"
    ) from exc

try:
    import branca.colormap as cm
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: branca\n"
        "Install with: pip install branca"
    ) from exc


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CountZone:
    """A counted penguin zone with boundary and metadata."""
    name: str
    site: str  # 'san_lorenzo' or 'caleta'
    penguin_count: int
    boundary_coords: List[Tuple[float, float]]  # [(lat, lon), ...]
    area_ha: Optional[float] = None
    density_per_ha: Optional[float] = None
    color: str = "#3388ff"
    notes: str = ""
    waypoints: List[Tuple[float, float, str]] = field(default_factory=list)  # [(lat, lon, label), ...]


# =============================================================================
# Ground Truth Data (from GPS Ground Truthing Notes PDF)
# =============================================================================

def get_san_lorenzo_zones() -> List[CountZone]:
    """Return San Lorenzo ground truth zones."""

    # High Density Caves - 908 penguins
    # Boundary from start/end points and right edge waypoints
    caves_boundary = [
        (-42.086263, -63.874072),  # Start 1
        (-42.086285, -63.874350),  # Start 2
        (-42.086656, -63.873951),  # Right edge
        (-42.087376, -63.873872),
        (-42.087740, -63.873728),
        (-42.088702, -63.873419),
        (-42.088878, -63.873310),  # End 1
        (-42.089107, -63.873427),  # End 2
        # Close back to start (estimate left edge)
        (-42.089000, -63.874500),
        (-42.087500, -63.874400),
    ]

    caves = CountZone(
        name="High Density Caves",
        site="san_lorenzo",
        penguin_count=908,
        boundary_coords=caves_boundary,
        area_ha=0.60,
        density_per_ha=1518.4,
        color="#e31a1c",  # Red - highest density
        notes="Start/end waypoints + right edge. 2 walked out between thermal and LiDAR.",
        waypoints=[
            (-42.086263, -63.874072, "Start 1"),
            (-42.086285, -63.874350, "Start 2"),
            (-42.088878, -63.873310, "End 1"),
            (-42.089107, -63.873427, "End 2"),
        ]
    )

    # The Plains - 453 penguins
    # Top and bottom edge waypoints form a strip
    plains_top = [
        (-42.084360, -63.867691),
        (-42.084418, -63.868053),
        (-42.084467, -63.868250),
        (-42.084534, -63.868537),
        (-42.084587, -63.868683),
        (-42.084671, -63.868935),
        (-42.084725, -63.869125),
        (-42.084772, -63.869388),
        (-42.084836, -63.869808),
        (-42.084864, -63.869953),
        (-42.084915, -63.870255),
        (-42.084953, -63.870431),
        (-42.085021, -63.870748),
    ]

    plains_bottom = [
        (-42.085187, -63.870152),
        (-42.085151, -63.869924),
        (-42.085140, -63.869811),
        (-42.085090, -63.869588),
        (-42.085049, -63.869395),
        (-42.085004, -63.869279),
        (-42.084942, -63.869132),
        (-42.084894, -63.868955),
        (-42.084867, -63.868800),
        (-42.084837, -63.868602),
        (-42.084813, -63.868448),
        (-42.084776, -63.868289),
        (-42.084741, -63.868187),
        (-42.084704, -63.868023),
        (-42.084658, -63.867900),
        (-42.084635, -63.867793),
        (-42.084597, -63.867633),
        (-42.084520, -63.867496),
    ]

    # Create closed polygon: top edge -> end -> bottom edge (reversed) -> start
    plains_boundary = plains_top + list(reversed(plains_bottom))

    plains = CountZone(
        name="The Plains",
        site="san_lorenzo",
        penguin_count=453,
        boundary_coords=plains_boundary,
        area_ha=0.98,
        density_per_ha=464.0,
        color="#fd8d3c",  # Orange
        notes="Extensive edge waypoints documented.",
        waypoints=[
            (-42.084371, -63.867582, "Start 1"),
            (-42.084520, -63.867496, "Start 2"),
            (-42.085076, -63.871035, "End 1"),
            (-42.085348, -63.870886, "End 2"),
        ]
    )

    # The Road - 359 penguins (no waypoints documented)
    # Estimate location between Plains and Caves
    road = CountZone(
        name="The Road",
        site="san_lorenzo",
        penguin_count=359,
        boundary_coords=[],  # No boundary available
        color="#fecc5c",  # Yellow
        notes="Waypoints not documented in PDF. Location estimated.",
    )

    # Box Count High Density Caves - 32 penguins
    # Area: 11,539.75 m² from PDF
    box_caves = CountZone(
        name="Box Count - Caves",
        site="san_lorenzo",
        penguin_count=32,
        boundary_coords=[],  # Approximate rectangle needed
        area_ha=1.154,
        density_per_ha=27.7,
        color="#91cf60",  # Light green
        notes="2 walked out between thermal and LiDAR.",
    )

    # Box Count High Density Bushes - 55 penguins
    # Area: 37,983.65 m² from PDF
    box_bushes = CountZone(
        name="Box Count - Bushes",
        site="san_lorenzo",
        penguin_count=55,
        boundary_coords=[],  # Approximate rectangle needed
        area_ha=3.798,
        density_per_ha=14.5,
        color="#1a9850",  # Dark green
        notes="Rectangular area in bushes.",
    )

    return [caves, plains, road, box_caves, box_bushes]


def get_caleta_zones() -> List[CountZone]:
    """Return Caleta ground truth zones."""

    # Small Island - 1557 penguins, 4 ha
    small_island = CountZone(
        name="Small Island",
        site="caleta",
        penguin_count=1557,
        boundary_coords=[],  # Island boundary from imagery
        area_ha=4.0,
        density_per_ha=389.2,
        color="#2166ac",  # Blue
        notes="Sensors: L2 (ortho), H30T",
    )

    # Tiny Island - 321 penguins, 0.7 ha
    tiny_island = CountZone(
        name="Tiny Island",
        site="caleta",
        penguin_count=321,
        boundary_coords=[],  # Island boundary from imagery
        area_ha=0.7,
        density_per_ha=458.6,
        color="#4393c3",  # Light blue
        notes="Sensors: L2 (ortho), H30T. Area: 6,859.41 m²",
    )

    # Box Count 1 - 8 penguins
    box1 = CountZone(
        name="Box Count 1",
        site="caleta",
        penguin_count=8,
        boundary_coords=[],
        color="#92c5de",
        notes="One walked outside collection zone during flight.",
    )

    # Box Count 2 - 12 penguins
    box2 = CountZone(
        name="Box Count 2",
        site="caleta",
        penguin_count=12,
        boundary_coords=[],
        color="#d1e5f0",
        notes="Only counted inside rope bounds.",
    )

    return [small_island, tiny_island, box1, box2]


# =============================================================================
# Map Creation
# =============================================================================

def create_argentina_map(
    output_path: Path,
    detection_geojson: Optional[Path] = None,
    show_heatmap: bool = True,
) -> None:
    """
    Create comprehensive Argentina survey map.

    Args:
        output_path: Output HTML path
        detection_geojson: Optional LiDAR detection GeoJSON
        show_heatmap: Whether to show density heatmap layer
    """

    # Get all zones
    san_lorenzo_zones = get_san_lorenzo_zones()
    caleta_zones = get_caleta_zones()
    all_zones = san_lorenzo_zones + caleta_zones

    # Calculate map center (San Lorenzo area)
    # San Lorenzo approximate center
    san_lorenzo_center = (-42.086, -63.871)

    # Create base map
    m = folium.Map(
        location=san_lorenzo_center,
        zoom_start=15,
        tiles=None,
    )

    # ==========================================================================
    # Base Layers
    # ==========================================================================

    # Esri Satellite (default)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Satellite",
        overlay=False,
        control=True,
    ).add_to(m)

    # OpenStreetMap
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True,
    ).add_to(m)

    # CartoDB Dark (good for heatmaps)
    folium.TileLayer(
        tiles="CartoDB dark_matter",
        name="Dark Mode",
        overlay=False,
        control=True,
    ).add_to(m)

    # ==========================================================================
    # San Lorenzo Count Zones
    # ==========================================================================

    sl_group = folium.FeatureGroup(name="San Lorenzo Zones", show=True)

    for zone in san_lorenzo_zones:
        if zone.boundary_coords:
            # Create polygon
            folium.Polygon(
                locations=zone.boundary_coords,
                color=zone.color,
                weight=3,
                fill=True,
                fillColor=zone.color,
                fillOpacity=0.3,
                popup=folium.Popup(
                    f"""<div style="font-family: sans-serif; min-width: 200px;">
                        <h4 style="margin: 0 0 8px 0; color: {zone.color};">{zone.name}</h4>
                        <table style="font-size: 12px;">
                            <tr><td><b>Count:</b></td><td>{zone.penguin_count} penguins</td></tr>
                            <tr><td><b>Area:</b></td><td>{zone.area_ha:.2f} ha</td></tr>
                            <tr><td><b>Density:</b></td><td>{zone.density_per_ha:.0f}/ha</td></tr>
                        </table>
                        <p style="font-size: 11px; color: #666; margin-top: 8px;">{zone.notes}</p>
                    </div>""",
                    max_width=300
                ),
                tooltip=f"{zone.name}: {zone.penguin_count} penguins",
            ).add_to(sl_group)

            # Add waypoint markers
            for lat, lon, label in zone.waypoints:
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=4,
                    color=zone.color,
                    fill=True,
                    fillColor="white",
                    fillOpacity=1,
                    weight=2,
                    tooltip=f"{zone.name} - {label}",
                ).add_to(sl_group)
        else:
            # No boundary - just add a marker at estimated center
            if zone.name == "The Road":
                # Estimate Road location between Plains and Caves
                marker_loc = (-42.0855, -63.872)
            else:
                marker_loc = san_lorenzo_center

            folium.Marker(
                location=marker_loc,
                popup=f"{zone.name}: {zone.penguin_count} penguins<br>{zone.notes}",
                tooltip=f"{zone.name}: {zone.penguin_count}",
                icon=folium.Icon(color='orange', icon='info-sign'),
            ).add_to(sl_group)

    sl_group.add_to(m)

    # ==========================================================================
    # Caleta Zones (separate feature group - different location)
    # ==========================================================================

    caleta_group = folium.FeatureGroup(name="Caleta Zones", show=False)

    # Caleta is in a different location - add markers only
    # (Would need actual coordinates to place properly)
    for zone in caleta_zones:
        folium.Marker(
            location=san_lorenzo_center,  # Placeholder - need real coords
            popup=f"{zone.name}: {zone.penguin_count} penguins<br>{zone.notes}",
            tooltip=f"[Caleta] {zone.name}: {zone.penguin_count}",
            icon=folium.Icon(color='blue', icon='info-sign'),
        ).add_to(caleta_group)

    caleta_group.add_to(m)

    # ==========================================================================
    # GPS Waypoints Layer
    # ==========================================================================

    waypoints_group = folium.FeatureGroup(name="GPS Waypoints", show=True)

    # Add all edge waypoints from Plains as track
    plains_top = [
        (-42.084360, -63.867691), (-42.084418, -63.868053),
        (-42.084467, -63.868250), (-42.084534, -63.868537),
        (-42.084587, -63.868683), (-42.084671, -63.868935),
        (-42.084725, -63.869125), (-42.084772, -63.869388),
        (-42.084836, -63.869808), (-42.084864, -63.869953),
        (-42.084915, -63.870255), (-42.084953, -63.870431),
        (-42.085021, -63.870748),
    ]

    folium.PolyLine(
        locations=plains_top,
        color="#fd8d3c",
        weight=4,
        opacity=0.8,
        tooltip="Plains - Top Edge Track",
    ).add_to(waypoints_group)

    # Caves right edge track
    caves_edge = [
        (-42.086656, -63.873951), (-42.087376, -63.873872),
        (-42.087740, -63.873728), (-42.088702, -63.873419),
    ]

    folium.PolyLine(
        locations=caves_edge,
        color="#e31a1c",
        weight=4,
        opacity=0.8,
        tooltip="Caves - Right Edge Track",
    ).add_to(waypoints_group)

    waypoints_group.add_to(m)

    # ==========================================================================
    # Density Heatmap Layer
    # ==========================================================================

    if show_heatmap:
        # Create pseudo-heatmap from zone centroids weighted by count
        heatmap_data = []

        for zone in san_lorenzo_zones:
            if zone.boundary_coords:
                # Centroid
                lats = [p[0] for p in zone.boundary_coords]
                lons = [p[1] for p in zone.boundary_coords]
                centroid = (sum(lats)/len(lats), sum(lons)/len(lons))

                # Add multiple points weighted by count
                weight = zone.penguin_count / 100  # Normalize
                heatmap_data.append([centroid[0], centroid[1], weight])

        if heatmap_data:
            plugins.HeatMap(
                heatmap_data,
                name="Density Heatmap",
                min_opacity=0.3,
                radius=30,
                blur=20,
                gradient={0.2: 'blue', 0.4: 'lime', 0.6: 'yellow', 0.8: 'orange', 1: 'red'},
                show=False,  # Hidden by default
            ).add_to(m)

    # ==========================================================================
    # Summary Statistics Panel
    # ==========================================================================

    sl_total = sum(z.penguin_count for z in san_lorenzo_zones)
    caleta_total = sum(z.penguin_count for z in caleta_zones)
    grand_total = sl_total + caleta_total

    summary_html = f'''
    <div style="position: fixed;
                top: 10px; right: 10px;
                background: rgba(255,255,255,0.95);
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                z-index: 9999;
                font-family: Arial, sans-serif;
                max-width: 280px;">
        <h3 style="margin: 0 0 10px 0; color: #333;">Argentina Survey 2025</h3>
        <hr style="margin: 8px 0; border: none; border-top: 1px solid #ddd;">

        <div style="margin-bottom: 12px;">
            <b style="color: #c41e3a;">San Lorenzo</b>
            <table style="font-size: 12px; width: 100%; margin-top: 4px;">
                <tr><td>Caves</td><td align="right"><b>908</b></td><td style="color:#666; font-size:10px;">1,518/ha</td></tr>
                <tr><td>Plains</td><td align="right"><b>453</b></td><td style="color:#666; font-size:10px;">464/ha</td></tr>
                <tr><td>Road</td><td align="right"><b>359</b></td><td style="color:#666; font-size:10px;">-</td></tr>
                <tr><td>Box Counts</td><td align="right"><b>87</b></td><td style="color:#666; font-size:10px;">15-28/ha</td></tr>
                <tr style="border-top: 1px solid #eee;"><td><b>Subtotal</b></td><td align="right"><b>{sl_total}</b></td><td></td></tr>
            </table>
        </div>

        <div style="margin-bottom: 12px;">
            <b style="color: #2166ac;">Caleta</b>
            <table style="font-size: 12px; width: 100%; margin-top: 4px;">
                <tr><td>Small Island</td><td align="right"><b>1,557</b></td><td style="color:#666; font-size:10px;">389/ha</td></tr>
                <tr><td>Tiny Island</td><td align="right"><b>321</b></td><td style="color:#666; font-size:10px;">459/ha</td></tr>
                <tr><td>Box Counts</td><td align="right"><b>20</b></td><td style="color:#666; font-size:10px;">-</td></tr>
                <tr style="border-top: 1px solid #eee;"><td><b>Subtotal</b></td><td align="right"><b>{caleta_total}</b></td><td></td></tr>
            </table>
        </div>

        <div style="background: #f0f0f0; padding: 8px; border-radius: 4px; text-align: center;">
            <span style="font-size: 14px;">Grand Total:</span>
            <span style="font-size: 24px; font-weight: bold; color: #333;">{grand_total:,}</span>
            <span style="font-size: 12px; color: #666;">penguins</span>
        </div>

        <p style="font-size: 10px; color: #999; margin: 8px 0 0 0; text-align: center;">
            Density range: 15 - 1,518 penguins/ha
        </p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(summary_html))

    # ==========================================================================
    # Legend
    # ==========================================================================

    legend_html = '''
    <div style="position: fixed;
                bottom: 30px; left: 10px;
                background: rgba(255,255,255,0.95);
                padding: 10px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                z-index: 9999;
                font-family: Arial, sans-serif;
                font-size: 11px;">
        <b>Density</b><br>
        <span style="background: #e31a1c; padding: 2px 8px; color: white;">High (&gt;500/ha)</span><br>
        <span style="background: #fd8d3c; padding: 2px 8px;">Medium (100-500/ha)</span><br>
        <span style="background: #91cf60; padding: 2px 8px;">Low (&lt;100/ha)</span>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    # ==========================================================================
    # Plugins
    # ==========================================================================

    # Layer control
    folium.LayerControl(collapsed=False).add_to(m)

    # Fullscreen button
    plugins.Fullscreen().add_to(m)

    # Mouse position
    plugins.MousePosition(
        position='bottomright',
        separator=' | ',
        prefix='Cursor:',
        lat_formatter=lambda x: f'{x:.6f}°',
        lng_formatter=lambda x: f'{x:.6f}°',
    ).add_to(m)

    # Minimap
    plugins.MiniMap(
        tile_layer=folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
        ),
        toggle_display=True,
        minimized=True,
    ).add_to(m)

    # Measure tool
    plugins.MeasureControl(position='topleft').add_to(m)

    # ==========================================================================
    # Save
    # ==========================================================================

    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))

    print(f"Map saved to: {output_path}")
    print(f"  San Lorenzo: {sl_total} penguins")
    print(f"  Caleta: {caleta_total} penguins")
    print(f"  Total: {grand_total} penguins")


def main():
    parser = argparse.ArgumentParser(
        description="Create Argentina penguin survey interactive map"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("qc/panels/argentina_survey.html"),
        help="Output HTML file"
    )
    parser.add_argument(
        "--detections", "-d",
        type=Path,
        default=None,
        help="Optional LiDAR detection GeoJSON to overlay"
    )
    parser.add_argument(
        "--no-heatmap",
        action="store_true",
        help="Disable density heatmap layer"
    )

    args = parser.parse_args()

    create_argentina_map(
        output_path=args.output,
        detection_geojson=args.detections,
        show_heatmap=not args.no_heatmap,
    )


if __name__ == "__main__":
    main()
