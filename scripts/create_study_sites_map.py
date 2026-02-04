#!/usr/bin/env python3
"""
Generate a two-panel static map of Argentina 2025 study sites for the README.

San Lorenzo (mainland) left panel; Caleta (islands) right panel. Uses CartoDB
Positron basemap and color-coded site boundaries with penguin counts.

Usage:
    python scripts/create_study_sites_map.py

Output:
    qc/panels/study_sites_map.png
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection
import numpy as np
import pyproj
import contextily as cx

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# WGS84 (lon, lat) -> Web Mercator (x, y meters)
WGS84 = "EPSG:4326"
WEB_MERCATOR = "EPSG:3857"
TRANSFORMER = pyproj.Transformer.from_crs(WGS84, WEB_MERCATOR, always_xy=True)

# Scientific palette: muted, distinguishable colors
SAN_LORENZO_COLORS = {
    "san_lorenzo_coverage": "#e8e8e8",    # light gray for full coverage background
    "san_lorenzo_caves": "#d46a5a",       # muted red
    "san_lorenzo_plains": "#5a8a7e",      # muted teal
    "san_lorenzo_box_bushes": "#c4a35a",  # muted gold
    "san_lorenzo_road": "#8a5a9a",        # muted purple
}
CALETA_COLORS = {
    "caleta_small_island": "#5a7a9a",     # muted blue
    "caleta_tiny_island": "#7a9ab0",      # lighter blue
}


def _transform_ring(lonlat_ring: list) -> np.ndarray:
    """Transform a single ring [[lon, lat], ...] to Web Mercator (x, y)."""
    if not lonlat_ring:
        return np.array([]).reshape(0, 2)
    arr = np.array(lonlat_ring)
    xs, ys = TRANSFORMER.transform(arr[:, 0], arr[:, 1])
    return np.column_stack([xs, ys])


def _polygon_area(ring: np.ndarray) -> float:
    """Compute polygon area using shoelace formula (signed area)."""
    if len(ring) < 3:
        return 0.0
    x, y = ring[:, 0], ring[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def _polygons_from_geojson(
    geojson: dict,
    largest_only: bool = False,
) -> list[tuple[np.ndarray, dict]]:
    """Extract (xy_rings, properties) from a GeoJSON FeatureCollection.

    Args:
        geojson: GeoJSON dict
        largest_only: If True, for MultiPolygon keep only the largest polygon by area.
                      Useful for filtering out LiDAR tile fragments.
    """
    out = []
    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        if geom.get("type") == "Polygon":
            coords = geom.get("coordinates", [])
            if coords:
                ring = _transform_ring(coords[0])
                if len(ring) >= 3:
                    out.append((ring, props))
        elif geom.get("type") == "MultiPolygon":
            rings_with_area = []
            for poly in geom.get("coordinates", []):
                if poly and poly[0]:
                    ring = _transform_ring(poly[0])
                    if len(ring) >= 3:
                        rings_with_area.append((ring, _polygon_area(ring)))
            if largest_only and rings_with_area:
                # Keep only the largest polygon
                rings_with_area.sort(key=lambda x: x[1], reverse=True)
                out.append((rings_with_area[0][0], props))
            else:
                for ring, _ in rings_with_area:
                    out.append((ring, props))
    return out


def _add_scale_bar(ax: plt.Axes, length_m: float) -> None:
    """Add a scale bar in meters (axes in Web Mercator)."""
    if length_m <= 0:
        return
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    x_range = x_max - x_min
    y_range = y_max - y_min
    x0 = x_min + 0.05 * x_range
    y0 = y_min + 0.05 * y_range
    x1 = x0 + length_m
    ax.plot([x0, x1], [y0, y0], color="black", linewidth=2.5)
    ax.plot([x0, x0], [y0, y0 + 0.015 * y_range], color="black", linewidth=2.5)
    ax.plot([x1, x1], [y0, y0 + 0.015 * y_range], color="black", linewidth=2.5)
    label = f"{length_m/1000:.1f} km" if length_m >= 1000 else f"{int(length_m)} m"
    ax.text(
        (x0 + x1) / 2.0,
        y0 + 0.025 * y_range,
        label,
        ha="center",
        va="bottom",
        fontsize=9,
        fontweight="bold",
        color="black",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.9, edgecolor="gray"),
    )


def _nice_scale_length_m(extent_m: float) -> float:
    """Choose a round scale bar length <= extent * 0.3."""
    target = max(50, extent_m * 0.25)
    if target <= 0:
        return 100.0
    magnitude = 10 ** math.floor(math.log10(target))
    for factor in (5, 2, 1):
        length = factor * magnitude
        if length <= target:
            return length
    return magnitude


def _plot_polygons_on_ax(
    ax: plt.Axes,
    polygons: list[tuple[np.ndarray, dict]],
    color_map: dict,
    title: str,
    background_polygons: list[tuple[np.ndarray, dict]] | None = None,
) -> None:
    """Plot polygons, add basemap, scale bar, and labels.

    Args:
        ax: Matplotlib axes
        polygons: Main polygons to display with labels
        color_map: Color mapping by aoi_id
        title: Panel title
        background_polygons: Optional background layer (e.g., full coverage extent)
    """
    # Build background patches (subtle, no labels)
    bg_patches = []
    if background_polygons:
        for ring, props in background_polygons:
            poly = mpatches.Polygon(ring, closed=True)
            bg_patches.append(poly)

    # Build main patches
    patches = []
    site_centroids: dict[str, list[tuple[float, float]]] = {}
    site_areas: dict[str, float] = {}
    site_labels: dict[str, str] = {}

    for ring, props in polygons:
        poly = mpatches.Polygon(ring, closed=True)
        patches.append(poly)
        cx_, cy_ = ring[:, 0].mean(), ring[:, 1].mean()
        area = _polygon_area(ring)
        aoi_id = props.get("aoi_id") or props.get("name", "").lower().replace(" ", "_")
        site_centroids.setdefault(aoi_id, []).append((cx_, cy_))
        site_areas[aoi_id] = site_areas.get(aoi_id, 0) + area
        count = props.get("penguin_count")
        if count is not None and aoi_id not in site_labels:
            name = props.get("name", aoi_id)
            short = name.replace("High Density Caves", "Caves").replace("The Plains", "Plains")
            short = short.replace("Box Count High Density Bushes", "Box Bushes")
            site_labels[aoi_id] = f"{short}: {count}"

    # Compute label positions; offset small polygons to avoid overlap
    labels_data = []
    for aoi_id, coords in site_centroids.items():
        if aoi_id in site_labels:
            cx_ = sum(c[0] for c in coords) / len(coords)
            cy_ = sum(c[1] for c in coords) / len(coords)
            # For small polygons (< 5000 m²), offset label above
            area = site_areas.get(aoi_id, 0)
            if area < 5000:
                cy_ += 40  # Offset label upward (in meters)
            labels_data.append((cx_, cy_, site_labels[aoi_id]))

    if not patches and not bg_patches:
        ax.set_title(title, fontsize=12, fontweight="bold")
        return

    # Compute extent from all polygons (background + main)
    all_rings = [r for r, _ in polygons]
    if background_polygons:
        all_rings += [r for r, _ in background_polygons]
    all_xy = np.vstack(all_rings)
    x_min, x_max = all_xy[:, 0].min(), all_xy[:, 0].max()
    y_min, y_max = all_xy[:, 1].min(), all_xy[:, 1].max()
    dx = (x_max - x_min) * 0.10 or 500
    dy = (y_max - y_min) * 0.10 or 500
    ax.set_xlim(x_min - dx, x_max + dx)
    ax.set_ylim(y_min - dy, y_max + dy)
    ax.set_aspect("equal")

    # Basemap (CartoDB Positron - light, clean)
    cx.add_basemap(
        ax,
        crs=WEB_MERCATOR,
        source=cx.providers.CartoDB.Positron,
        zoom="auto",
    )

    # Draw background polygons first (subtle fill, dashed outline)
    if bg_patches:
        bg_coll = PatchCollection(
            bg_patches,
            facecolor="#f0f0f0",
            edgecolor="#888888",
            linewidths=1.0,
            linestyle="--",
            alpha=0.5,
        )
        ax.add_collection(bg_coll)

    # Draw main polygons on top
    colors = []
    for _, props in polygons:
        aoi_id = props.get("aoi_id") or ""
        colors.append(color_map.get(aoi_id, "#888888"))

    if patches:
        coll = PatchCollection(
            patches,
            facecolor=colors,
            edgecolor="#333333",
            linewidths=1.2,
            alpha=0.7,
        )
        ax.add_collection(coll)

    # Labels
    for lx, ly, text in labels_data:
        ax.text(
            lx, ly, text,
            ha="center", va="center",
            fontsize=8,
            fontweight="bold",
            color="#222222",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.85, edgecolor="#666666", linewidth=0.5),
        )

    extent_m = max(x_max - x_min, y_max - y_min)
    scale_len = _nice_scale_length_m(extent_m)
    _add_scale_bar(ax, scale_len)

    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_axis_off()


def main() -> None:
    root = PROJECT_ROOT
    out_path = root / "qc" / "panels" / "study_sites_map.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # San Lorenzo full LiDAR coverage (background)
    sl_coverage_path = root / "gps_aoi" / "data" / "layers" / "san_lorenzo_full_lidar_las.geojson"
    with open(sl_coverage_path) as f:
        sl_coverage_gj = json.load(f)
    # Use largest_only to get the main coverage outline, not tiny fragments
    sl_background = _polygons_from_geojson(sl_coverage_gj, largest_only=True)

    # San Lorenzo: field-counted zones (Caves, Plains, Box Bushes)
    sl_path = root / "gps_aoi" / "data" / "output" / "all_aois_combined_wgs84.geojson"
    with open(sl_path) as f:
        sl_geojson = json.load(f)
    sl_polygons = _polygons_from_geojson(sl_geojson)

    # Caleta: Small Island + Tiny Island (layer GeoJSONs)
    analysis_path = root / "data" / "processed" / "san_lorenzo_analysis.json"
    with open(analysis_path) as af:
        analysis = json.load(af)
    caleta_sites = analysis.get("caleta", {})

    caleta_polygons = []
    for aoi_id, key in [("caleta_small_island", "small_island"), ("caleta_tiny_island", "tiny_island")]:
        path = root / "gps_aoi" / "data" / "layers" / f"caleta_{key}.geojson"
        with open(path) as f:
            gj = json.load(f)
        count = caleta_sites.get(key, {}).get("penguin_count")
        display_name = caleta_sites.get(key, {}).get("name", aoi_id.replace("_", " ").title())
        # Use largest_only=True to filter out LiDAR tile artifacts and small fragments
        for ring, props in _polygons_from_geojson(gj, largest_only=True):
            props = {**props, "name": display_name, "penguin_count": count, "aoi_id": aoi_id}
            caleta_polygons.append((ring, props))

    fig, (ax_sl, ax_caleta) = plt.subplots(1, 2, figsize=(13, 6))
    fig.suptitle("Study Sites — San Lorenzo & Caleta (Argentina 2025)", fontsize=13, fontweight="bold", y=1.01)

    _plot_polygons_on_ax(
        ax_sl,
        sl_polygons,
        SAN_LORENZO_COLORS,
        "San Lorenzo (mainland)",
        background_polygons=sl_background,
    )
    _plot_polygons_on_ax(
        ax_caleta,
        caleta_polygons,
        CALETA_COLORS,
        "Caleta (islands)",
    )

    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
