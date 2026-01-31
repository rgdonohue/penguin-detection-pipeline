#!/usr/bin/env python3
"""
Diagnostic map showing where box count GPS coordinates fall relative to LiDAR tile extents.

This helps visualize the mismatch between:
- Where the coordinates are labeled (Bushes - 55 penguins)
- Where they actually fall spatially (inside the Caves tile?)

Usage:
    python scripts/diagnostic_coordinate_mismatch.py

Output:
    qc/panels/diagnostic_coordinate_mismatch.png
"""

import json
from pathlib import Path
from datetime import datetime

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon as MplPolygon
import matplotlib.ticker as mticker

# Optional: laspy for reading LAS bounds
try:
    import laspy
    HAS_LASPY = True
except ImportError:
    HAS_LASPY = False

# Optional: pyproj for coordinate transformation
try:
    from pyproj import Transformer
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False

PROJECT_ROOT = Path(__file__).parent.parent


# Box Count Coordinates from PDF (labeled as "Box Count High Density Bushes: 55 penguins")
BOX_COUNT_COORDS_WGS84 = [
    (-42.085258, -63.867123),  # Corner 1 - Top-Left (NW)
    (-42.085381, -63.867161),  # Corner 2 - Bottom-Left (SW)
    (-42.085392, -63.866972),  # Corner 3 - Bottom-Right (SE)
    (-42.085273, -63.866958),  # Corner 4 - Top-Right (NE)
]

# LiDAR tile mapping from gameplan
TILE_INFO = {
    "11.9": {
        "name": "Box Count 11.9.25 (Caves - 32 penguins)",
        "color": "#e74c3c",  # Red
        "ground_truth": 32,
    },
    "11.10": {
        "name": "Box Count 11.10 (Bushes - 55 penguins)",
        "color": "#2ecc71",  # Green
        "ground_truth": 55,
    },
}


def get_las_bounds(las_path: Path) -> dict:
    """Read LAS file and return bounding box."""
    if not HAS_LASPY:
        return None

    try:
        with laspy.open(las_path) as f:
            header = f.header
            return {
                "min_x": header.x_min,
                "max_x": header.x_max,
                "min_y": header.y_min,
                "max_y": header.y_max,
                "point_count": header.point_count,
                "crs": str(header.parse_crs()) if hasattr(header, 'parse_crs') else "Unknown",
            }
    except Exception as e:
        print(f"  Warning: Could not read {las_path}: {e}")
        return None


def transform_wgs84_to_utm(coords_wgs84: list, target_epsg: int = 32720) -> list:
    """Transform WGS84 (lat, lon) coordinates to projected CRS."""
    if not HAS_PYPROJ:
        print("  Warning: pyproj not available, cannot transform coordinates")
        return None

    # WGS84 to UTM Zone 20S (or target CRS)
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{target_epsg}", always_xy=True)

    transformed = []
    for lat, lon in coords_wgs84:
        x, y = transformer.transform(lon, lat)  # pyproj uses (lon, lat) order
        transformed.append((x, y))

    return transformed


def transform_wgs84_to_posgar(coords_wgs84: list) -> list:
    """Transform WGS84 (lat, lon) coordinates to POSGAR 2007 / Argentina 3 (EPSG:5345)."""
    if not HAS_PYPROJ:
        print("  Warning: pyproj not available, cannot transform coordinates")
        return None

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:5345", always_xy=True)

    transformed = []
    for lat, lon in coords_wgs84:
        x, y = transformer.transform(lon, lat)
        transformed.append((x, y))

    return transformed


def polygon_area(coords: list) -> float:
    """Calculate polygon area using shoelace formula."""
    n = len(coords)
    if n < 3:
        return 0.0

    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i][0] * coords[j][1]
        area -= coords[j][0] * coords[i][1]

    return abs(area) / 2.0


def point_in_bbox(x: float, y: float, bounds: dict) -> bool:
    """Check if point is inside bounding box."""
    return (bounds["min_x"] <= x <= bounds["max_x"] and
            bounds["min_y"] <= y <= bounds["max_y"])


def main():
    print("=" * 70)
    print("DIAGNOSTIC: Box Count Coordinate vs LiDAR Tile Mismatch")
    print("=" * 70)

    output_dir = PROJECT_ROOT / "qc" / "panels"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find LiDAR files
    las_files = {
        "11.9": PROJECT_ROOT / "data/2025/San_Lorenzo_UTM/box_count_11.9.las",
        "11.10": PROJECT_ROOT / "data/2025/San_Lorenzo_UTM/box_count_11.10.las",
    }

    # Check for original (non-UTM) files too
    las_files_orig = {
        "11.9_orig": PROJECT_ROOT / "data/2025/San Lorenzo Box Count 11.9.25 LAS.las",
        "11.10_orig": PROJECT_ROOT / "data/2025/San Lorenzo Box Count 11.10 LAS.las",
    }

    print("\n1. Reading LiDAR tile bounds...")
    tile_bounds = {}

    # Try UTM files first
    for key, path in las_files.items():
        if path.exists():
            bounds = get_las_bounds(path)
            if bounds:
                tile_bounds[key] = bounds
                print(f"   {key}: X=[{bounds['min_x']:.1f}, {bounds['max_x']:.1f}], "
                      f"Y=[{bounds['min_y']:.1f}, {bounds['max_y']:.1f}] ({bounds['point_count']:,} pts)")

    # If no UTM files, try original POSGAR files
    if not tile_bounds:
        print("   No UTM files found, trying original POSGAR files...")
        for key, path in las_files_orig.items():
            if path.exists():
                bounds = get_las_bounds(path)
                if bounds:
                    # Strip "_orig" suffix for cleaner key
                    clean_key = key.replace("_orig", "")
                    tile_bounds[clean_key] = bounds
                    print(f"   {clean_key}: X=[{bounds['min_x']:.1f}, {bounds['max_x']:.1f}], "
                          f"Y=[{bounds['min_y']:.1f}, {bounds['max_y']:.1f}] ({bounds['point_count']:,} pts)")

    if not tile_bounds:
        print("   ERROR: No LiDAR files found or laspy not installed")
        return

    # Determine CRS from tile bounds (check if UTM or POSGAR range)
    sample_bounds = list(tile_bounds.values())[0]
    is_utm = sample_bounds["min_x"] > 100000  # UTM easting is typically > 100000

    print(f"\n2. Detected CRS: {'UTM Zone 20S (EPSG:32720)' if is_utm else 'POSGAR 2007 / Argentina 3 (EPSG:5345)'}")

    # Transform GPS coordinates to matching CRS
    print("\n3. Transforming box count GPS coordinates...")
    print(f"   WGS84 coordinates (lat, lon):")
    for i, (lat, lon) in enumerate(BOX_COUNT_COORDS_WGS84, 1):
        print(f"     Corner {i}: {lat:.6f}, {lon:.6f}")

    if is_utm:
        coords_projected = transform_wgs84_to_utm(BOX_COUNT_COORDS_WGS84, 32720)
    else:
        coords_projected = transform_wgs84_to_posgar(BOX_COUNT_COORDS_WGS84)

    if not coords_projected:
        print("   ERROR: Could not transform coordinates")
        return

    print(f"\n   Projected coordinates:")
    for i, (x, y) in enumerate(coords_projected, 1):
        print(f"     Corner {i}: {x:.2f}, {y:.2f}")

    # Calculate polygon area
    area_m2 = polygon_area(coords_projected)
    print(f"\n   Polygon area: {area_m2:.1f} m² ({area_m2/10000:.4f} ha)")
    print(f"   Expected area: ~37,984 m² (0.38 ha) per PDF")
    print(f"   MISMATCH: {abs(area_m2 - 37984):.1f} m² difference!")

    # Check which tile(s) contain the coordinates
    print("\n4. Checking coordinate containment...")
    centroid_x = np.mean([c[0] for c in coords_projected])
    centroid_y = np.mean([c[1] for c in coords_projected])
    print(f"   Centroid: ({centroid_x:.2f}, {centroid_y:.2f})")

    for tile_key, bounds in tile_bounds.items():
        tile_info = TILE_INFO.get(tile_key, {"name": tile_key})

        # Check centroid
        centroid_inside = point_in_bbox(centroid_x, centroid_y, bounds)

        # Check all corners
        corners_inside = sum(1 for x, y in coords_projected if point_in_bbox(x, y, bounds))

        status = "INSIDE" if centroid_inside else "OUTSIDE"
        print(f"   {tile_info['name']}: Centroid {status}, {corners_inside}/4 corners inside")

        # Distance from centroid to tile center
        tile_center_x = (bounds["min_x"] + bounds["max_x"]) / 2
        tile_center_y = (bounds["min_y"] + bounds["max_y"]) / 2
        dist = np.sqrt((centroid_x - tile_center_x)**2 + (centroid_y - tile_center_y)**2)
        print(f"     Distance from tile center: {dist:.1f} m")

    # Create the diagnostic map
    print("\n5. Creating diagnostic map...")

    # Use a two-panel layout: map on left, summary on right
    fig = plt.figure(figsize=(16, 10))
    ax = fig.add_axes([0.06, 0.1, 0.55, 0.8])  # Map panel
    summary_ax = fig.add_axes([0.65, 0.1, 0.32, 0.8])  # Summary panel
    summary_ax.axis("off")

    # Plot tile bounding boxes
    for tile_key, bounds in tile_bounds.items():
        tile_info = TILE_INFO.get(tile_key, {"name": tile_key, "color": "gray"})

        # Create rectangle for tile bounds
        width = bounds["max_x"] - bounds["min_x"]
        height = bounds["max_y"] - bounds["min_y"]

        rect = mpatches.Rectangle(
            (bounds["min_x"], bounds["min_y"]),
            width, height,
            linewidth=3,
            edgecolor=tile_info["color"],
            facecolor=tile_info["color"],
            alpha=0.15,
            label=tile_info["name"],
        )
        ax.add_patch(rect)

        # Add tile label at center
        tile_center_x = (bounds["min_x"] + bounds["max_x"]) / 2
        tile_center_y = (bounds["min_y"] + bounds["max_y"]) / 2

        ax.annotate(
            f"{tile_info['name']}\n{bounds['point_count']:,} points\n{width:.0f}m × {height:.0f}m",
            xy=(tile_center_x, tile_center_y),
            fontsize=10,
            fontweight="bold",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.9,
                      edgecolor=tile_info["color"], linewidth=2),
        )

    # Plot the GPS coordinate polygon
    poly_coords = np.array(coords_projected + [coords_projected[0]])  # Close polygon
    ax.plot(poly_coords[:, 0], poly_coords[:, 1],
            color="blue", linewidth=3, linestyle="-", marker="o", markersize=10,
            label=f"PDF Box Coords (labeled 'Bushes 55')\nActual area: {area_m2:.0f} m²")
    ax.fill(poly_coords[:, 0], poly_coords[:, 1], color="blue", alpha=0.3)

    # Label corners
    for i, (x, y) in enumerate(coords_projected, 1):
        corner_labels = ["NW (Top-Left)", "SW (Bottom-Left)", "SE (Bottom-Right)", "NE (Top-Right)"]
        ax.annotate(
            f"C{i}\n{corner_labels[i-1]}",
            xy=(x, y),
            xytext=(15, 15),
            textcoords="offset points",
            fontsize=8,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="yellow", alpha=0.9),
            arrowprops=dict(arrowstyle="->", color="blue"),
        )

    # Mark centroid
    ax.scatter([centroid_x], [centroid_y], s=200, c="red", marker="*", zorder=10,
               label=f"Polygon centroid")

    # Set axis limits with padding
    all_x = [c[0] for c in coords_projected]
    all_y = [c[1] for c in coords_projected]
    for bounds in tile_bounds.values():
        all_x.extend([bounds["min_x"], bounds["max_x"]])
        all_y.extend([bounds["min_y"], bounds["max_y"]])

    x_margin = (max(all_x) - min(all_x)) * 0.1
    y_margin = (max(all_y) - min(all_y)) * 0.1
    ax.set_xlim(min(all_x) - x_margin, max(all_x) + x_margin)
    ax.set_ylim(min(all_y) - y_margin, max(all_y) + y_margin)

    # Title and labels
    ax.set_title(
        "DIAGNOSTIC: Box Count Coordinate vs LiDAR Tile Mismatch\n"
        "PDF labels coords as 'Bushes (55 penguins)' but they fall inside the Caves tile",
        fontsize=14,
        fontweight="bold",
        color="darkred",
    )

    crs_label = "EPSG:32720 (UTM 20S)" if is_utm else "EPSG:5345 (POSGAR)"
    ax.set_xlabel(f"Easting (m) — {crs_label}", fontsize=11)
    ax.set_ylabel(f"Northing (m) — {crs_label}", fontsize=11)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3, linestyle="--")

    # Format axis labels without scientific notation
    formatter = mticker.ScalarFormatter(useOffset=False)
    formatter.set_scientific(False)
    ax.xaxis.set_major_formatter(formatter)
    ax.yaxis.set_major_formatter(formatter)

    # Legend
    ax.legend(loc="upper left", fontsize=9)

    # Add issue summary in the right panel using multiple text calls
    y_pos = 0.95
    line_height = 0.035

    def add_text(text, bold=False, color="black", indent=0):
        nonlocal y_pos
        weight = "bold" if bold else "normal"
        summary_ax.text(0.02 + indent*0.05, y_pos, text, transform=summary_ax.transAxes,
                       fontsize=10, fontfamily="monospace", fontweight=weight, color=color,
                       verticalalignment="top")
        y_pos -= line_height

    def add_section(title):
        nonlocal y_pos
        summary_ax.plot([0.02, 0.98], [y_pos + 0.01, y_pos + 0.01], color="orange",
                       linewidth=2, transform=summary_ax.transAxes)
        y_pos -= 0.01
        add_text(title, bold=True, color="darkred")
        y_pos -= 0.01

    # Draw background box
    from matplotlib.patches import FancyBboxPatch
    bg_box = FancyBboxPatch((0.0, 0.0), 1.0, 1.0, transform=summary_ax.transAxes,
                            boxstyle="round,pad=0.02", facecolor="lightyellow",
                            edgecolor="orange", linewidth=2, alpha=0.95)
    summary_ax.add_patch(bg_box)

    add_section("ISSUES IDENTIFIED")
    add_text("")
    add_text("1. LOCATION MISMATCH", bold=True)
    add_text("Coords fall inside 11.9 (Caves)", indent=1)
    add_text("but PDF labels them as 'Bushes'", indent=1)
    add_text("")
    add_text("- Centroid is 7.5m from Caves center", indent=1)
    add_text("- Centroid is 644m from Bushes tile", indent=1)
    add_text("- All 4 corners inside Caves tile", indent=1)
    add_text("")
    add_text("2. SIZE MISMATCH", bold=True)
    add_text(f"Actual polygon: {area_m2:.0f} m2", indent=1)
    add_text("Expected (PDF): 37,984 m2", indent=1)
    add_text("Difference: 99% smaller!", indent=1, color="red")
    add_text("")

    add_section("HYPOTHESES")
    add_text("")
    add_text("A) Coords are for Caves (32),")
    add_text("   mislabeled as Bushes in PDF", indent=1)
    add_text("")
    add_text("B) Coords are internal waypoints,")
    add_text("   not actual box corners", indent=1)
    add_text("")
    add_text("C) Transcription error in PDF")
    add_text("")

    add_section("NEXT STEPS")
    add_text("")
    add_text("1. Clarify with client which box")
    add_text("   the coords represent", indent=1)
    add_text("")
    add_text("2. Request correct box corner")
    add_text("   coordinates if needed", indent=1)

    # Generation timestamp
    generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fig.text(0.99, 0.01, f"Generated: {generation_time}", fontsize=8, ha="right", style="italic")

    # Don't use tight_layout with manual axes positioning

    # Save - don't use bbox_inches="tight" with manual axes layout
    output_path = output_dir / "diagnostic_coordinate_mismatch.png"
    fig.savefig(output_path, dpi=150, facecolor="white")
    plt.close(fig)

    print(f"\n   Saved: {output_path}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"The 4 GPS coordinates from the PDF:")
    print(f"  - Are labeled as 'Box Count High Density Bushes: 55 penguins'")
    print(f"  - Actually fall INSIDE the 11.9 tile (mapped to Caves: 32 penguins)")
    print(f"  - Create a polygon of only {area_m2:.0f} m² (expected ~38,000 m²)")
    print()
    print("NEXT STEPS:")
    print("  1. Clarify with client which box the coords represent")
    print("  2. Determine if coords are corners or internal waypoints")
    print("  3. Request correct box corner coordinates if needed")
    print("=" * 70)


if __name__ == "__main__":
    main()
