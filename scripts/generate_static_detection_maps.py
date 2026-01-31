#!/usr/bin/env python3
"""
Generate static PNG maps from LiDAR detection GeoJSON files.

Produces publication-ready maps with explicit provenance metadata showing:
- Source data files
- Processing parameters
- Detection counts
- CRS information
- Generation timestamp

Usage:
    python scripts/generate_static_detection_maps.py

Output:
    qc/panels/static_maps/*.png
"""

import json
import sys
from datetime import datetime
import math
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def load_geojson(geojson_path: Path) -> dict:
    """Load GeoJSON file and return parsed data."""
    with open(geojson_path) as f:
        return json.load(f)


def load_summary_json(summary_path: Path) -> Optional[dict]:
    """Load processing summary JSON if it exists."""
    if summary_path.exists():
        with open(summary_path) as f:
            return json.load(f)
    return None


def extract_coordinates(geojson: dict) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Extract x, y coordinates and properties from GeoJSON features."""
    xs, ys, props = [], [], []
    for feat in geojson.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") == "Point":
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                xs.append(coords[0])
                ys.append(coords[1])
                props.append(feat.get("properties", {}))
    return np.array(xs), np.array(ys), props


def _resolve_epsg(geojson: dict, summary: Optional[dict], fallback_epsg: Optional[int]) -> str:
    """Return EPSG code as a string when available."""
    metadata = geojson.get("metadata", {}) if isinstance(geojson, dict) else {}
    crs_info = metadata.get("crs", {}) if isinstance(metadata, dict) else {}
    epsg = crs_info.get("epsg")
    if epsg is None and summary and isinstance(summary.get("crs"), dict):
        epsg = summary["crs"].get("epsg")
    if epsg is None and fallback_epsg is not None:
        epsg = fallback_epsg
    return str(epsg) if epsg is not None else "unknown"


def _nice_scale_length(target: float) -> float:
    """Choose a human-friendly scale length <= target."""
    if target <= 0:
        return 0.0
    magnitude = 10 ** math.floor(math.log10(target))
    for factor in (5, 2, 1):
        length = factor * magnitude
        if length <= target:
            return length
    return magnitude


def _add_scale_bar(ax: plt.Axes, length_m: float) -> None:
    """Add a simple scale bar to the plot."""
    if length_m <= 0:
        return
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    x_range = x_max - x_min
    y_range = y_max - y_min
    x0 = x_min + 0.05 * x_range
    y0 = y_min + 0.05 * y_range
    x1 = x0 + length_m
    ax.plot([x0, x1], [y0, y0], color="black", linewidth=2.0)
    ax.plot([x0, x0], [y0, y0 + 0.01 * y_range], color="black", linewidth=2.0)
    ax.plot([x1, x1], [y0, y0 + 0.01 * y_range], color="black", linewidth=2.0)
    ax.text(
        (x0 + x1) / 2.0,
        y0 + 0.02 * y_range,
        f"{int(length_m)} m",
        ha="center",
        va="bottom",
        fontsize=9,
        color="black",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8, edgecolor="gray"),
    )


def _add_north_arrow(ax: plt.Axes) -> None:
    """Add a north arrow in axes coordinates."""
    ax.annotate(
        "",
        xy=(0.94, 0.92),
        xytext=(0.94, 0.82),
        xycoords="axes fraction",
        arrowprops=dict(facecolor="black", width=2, headwidth=8),
    )
    ax.text(0.94, 0.94, "N", transform=ax.transAxes, ha="center", va="bottom", fontsize=10, fontweight="bold")


def create_detection_map(
    geojson_path: Path,
    summary_path: Optional[Path],
    output_path: Path,
    title: str,
    site_name: str,
    fallback_epsg: Optional[int] = None,
) -> None:
    """
    Create a static detection map with comprehensive metadata labels.

    Args:
        geojson_path: Path to detection GeoJSON file
        summary_path: Path to processing summary JSON (optional)
        output_path: Where to save the PNG
        title: Map title
        site_name: Human-readable site name
    """
    # Load data
    geojson = load_geojson(geojson_path)
    summary = load_summary_json(summary_path) if summary_path else None

    # Extract coordinates
    xs, ys, props = extract_coordinates(geojson)
    n_detections = len(xs)

    if n_detections == 0:
        print(f"  WARNING: No detections in {geojson_path.name}")
        return

    # CRS metadata (with fallback override)
    epsg = _resolve_epsg(geojson, summary, fallback_epsg)

    # Get processing parameters from summary
    params = {}
    if summary:
        params = summary.get("params", {})

    # Extract HAG parameters for display
    hag_min = params.get("hag_min", "N/A")
    hag_max = params.get("hag_max", "N/A")
    cell_res = params.get("cell_res", "N/A")
    min_area = params.get("min_area_cells", "N/A")
    max_area = params.get("max_area_cells", "N/A")

    # Color by HAG if available
    hag_values = np.array([p.get("hag_mean", 0.35) for p in props])

    # Create figure with dedicated metadata panel
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_axes([0.07, 0.12, 0.58, 0.78])
    cax = fig.add_axes([0.67, 0.28, 0.02, 0.46])
    meta_ax = fig.add_axes([0.72, 0.12, 0.26, 0.78])
    meta_ax.axis("off")

    # Plot detections
    scatter = ax.scatter(
        xs, ys,
        c=hag_values,
        cmap="YlOrRd",
        s=8,
        alpha=0.7,
        edgecolors="none",
    )

    # Colorbar
    cbar = fig.colorbar(scatter, cax=cax)
    cbar.set_label("Mean HAG (m)", fontsize=10)

    # Title
    ax.set_title(f"{title}\n{n_detections:,} candidate detections", fontsize=14, fontweight="bold")

    # Axis labels with CRS
    ax.set_xlabel(f"Easting (m) — EPSG:{epsg}", fontsize=10)
    ax.set_ylabel(f"Northing (m) — EPSG:{epsg}", fontsize=10)

    # Equal aspect ratio for geographic data
    ax.set_aspect("equal")

    # Grid
    ax.grid(True, alpha=0.3, linestyle="--")

    # Format axis ticks
    formatter = mticker.ScalarFormatter(useOffset=False)
    formatter.set_scientific(False)
    ax.xaxis.set_major_formatter(formatter)
    ax.yaxis.set_major_formatter(formatter)

    # Build metadata text block
    generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    metadata_lines = [
        "PROVENANCE",
        "─" * 40,
        f"Site: {site_name}",
        f"Detections: {n_detections:,}",
        f"CRS: EPSG:{epsg}",
        "",
        "PROCESSING PARAMETERS",
        "─" * 40,
        f"Cell resolution: {cell_res} m" if cell_res != "N/A" else "Cell resolution: N/A",
        f"HAG range: {hag_min}–{hag_max} m" if hag_min != "N/A" else "HAG range: N/A",
        f"Area filter: {min_area}–{max_area} cells" if min_area != "N/A" else "Area filter: N/A",
        "",
        "SOURCE FILES",
        "─" * 40,
        f"GeoJSON: {geojson_path.name}",
        f"Summary: {summary_path.name if summary_path else 'N/A'}",
        "",
        "GENERATION",
        "─" * 40,
        f"Script: scripts/generate_static_detection_maps.py",
        f"Generated: {generation_time}",
    ]

    metadata_text = "\n".join(metadata_lines)

    # Add metadata panel
    props_box = dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.95, edgecolor="gray")
    meta_ax.text(
        0.0, 1.0, metadata_text,
        fontsize=8,
        fontfamily="monospace",
        verticalalignment="top",
        bbox=props_box,
        transform=meta_ax.transAxes,
    )

    # Bounding box info at bottom
    bbox_text = (
        f"Extent: X [{xs.min():.1f}, {xs.max():.1f}] "
        f"Y [{ys.min():.1f}, {ys.max():.1f}]"
    )
    ax.text(
        0.5, -0.07, bbox_text,
        transform=ax.transAxes,
        fontsize=9,
        ha="center",
        style="italic",
    )

    # Disclaimer
    fig.text(
        0.36, 0.04,
        "NOTE: Detections are CANDIDATES (blob centroids), not validated penguin counts.",
        fontsize=9,
        ha="center",
        color="red",
        fontweight="bold",
    )

    # Scale bar + north arrow
    x_range = float(xs.max() - xs.min())
    _add_scale_bar(ax, _nice_scale_length(x_range * 0.2))
    _add_north_arrow(ax)

    # Adjust layout
    plt.tight_layout()

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(f"  Saved: {output_path}")
    print(f"    Detections: {n_detections:,}")
    print(f"    CRS: EPSG:{epsg}")


def main():
    """Generate static maps for key datasets."""

    output_dir = PROJECT_ROOT / "qc" / "panels" / "static_maps"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("STATIC DETECTION MAP GENERATION")
    print("=" * 60)
    print(f"Output directory: {output_dir}")
    print()

    # Define maps to generate
    maps_to_generate = [
        {
            "geojson": "data/interim/lidar_hag_geojson/San Lorenzo Full LiDAR LAS_detections.geojson",
            "summary": "data/interim/san_lorenzo_full.json",
            "output": "san_lorenzo_full_detections.png",
            "title": "San Lorenzo Full LiDAR — Detection Map",
            "site": "San Lorenzo (Argentina 2025)",
            "epsg": 5345,
        },
        {
            "geojson": "data/interim/lidar_hag_geojson/San Lorenzo Box Count 11.10 LAS_detections.geojson",
            "summary": "data/interim/san_lorenzo_full.json",  # Same run
            "output": "san_lorenzo_box_11.10_detections.png",
            "title": "San Lorenzo Box Count 11.10 — Detection Map",
            "site": "San Lorenzo Box Count (Argentina 2025)",
            "epsg": 5345,
        },
        {
            "geojson": "data/interim/lidar_hag_geojson/cloud3_detections.geojson",
            "summary": "data/interim/lidar_test.json",
            "output": "golden_aoi_cloud3_detections.png",
            "title": "Golden AOI (cloud3.las) — Detection Map",
            "site": "Legacy Punta Tombo (Golden Baseline)",
            "epsg": 32720,
        },
        {
            "geojson": "data/interim/lidar_hag_geojson/cloud0_detections.geojson",
            "summary": "data/interim/caleta_small_island.json",
            "output": "caleta_small_island_cloud0_detections.png",
            "title": "Caleta Small Island (cloud0) — Detection Map",
            "site": "Caleta Small Island (Argentina 2025)",
            "epsg": 32720,
        },
    ]

    for i, config in enumerate(maps_to_generate, 1):
        geojson_path = PROJECT_ROOT / config["geojson"]
        summary_path = PROJECT_ROOT / config["summary"] if config["summary"] else None
        output_path = output_dir / config["output"]

        print(f"[{i}/{len(maps_to_generate)}] {config['title']}")

        if not geojson_path.exists():
            print(f"  SKIP: GeoJSON not found: {geojson_path}")
            continue

        try:
            create_detection_map(
                geojson_path=geojson_path,
                summary_path=summary_path,
                output_path=output_path,
                title=config["title"],
                site_name=config["site"],
                fallback_epsg=config.get("epsg"),
            )
        except Exception as e:
            print(f"  ERROR: {e}")

    print()
    print("=" * 60)
    print("COMPLETE")
    print(f"Maps saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
