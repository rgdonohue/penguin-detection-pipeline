#!/usr/bin/env python3
"""
Generate static map showing LiDAR detections with AOI boundaries overlaid.

Shows the comparison between full-scene detections and AOI-clipped counts,
with field count reference data.

Usage:
    python scripts/generate_aoi_comparison_map.py

Output:
    qc/panels/static_maps/san_lorenzo_aoi_comparison.png
"""

import json
from datetime import datetime
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PolyCollection
import matplotlib.ticker as mticker
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def extract_polygon_coords(geometry: dict) -> list:
    """Extract polygon coordinates from GeoJSON geometry."""
    if geometry.get("type") == "Polygon":
        return geometry.get("coordinates", [[]])[0]
    elif geometry.get("type") == "MultiPolygon":
        # Return first polygon for simplicity
        coords = geometry.get("coordinates", [[[]]])
        return coords[0][0] if coords else []
    return []


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


def main():
    output_dir = PROJECT_ROOT / "qc" / "panels" / "static_maps"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("AOI COMPARISON MAP GENERATION")
    print("=" * 60)

    # Load detection GeoJSON
    geojson_path = PROJECT_ROOT / "data/interim/lidar_hag_geojson/San Lorenzo Full LiDAR LAS_detections.geojson"
    geojson = load_json(geojson_path)

    # Load AOI polygons
    aoi_path = PROJECT_ROOT / "data/processed/aoi_san_lorenzo_epsg5345.geojson"
    aoi_geojson = load_json(aoi_path)

    # Load AOI evaluation results
    eval_path = PROJECT_ROOT / "data/processed/san_lorenzo_aoi_eval.json"
    eval_data = load_json(eval_path)

    # Load summary for parameters
    summary_path = PROJECT_ROOT / "data/interim/san_lorenzo_full.json"
    summary = load_json(summary_path)
    params = summary.get("params", {})

    # Extract detection coordinates
    xs, ys, hags = [], [], []
    for feat in geojson.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") == "Point":
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                xs.append(coords[0])
                ys.append(coords[1])
                hags.append(feat.get("properties", {}).get("hag_mean", 0.35))

    xs = np.array(xs)
    ys = np.array(ys)
    hags = np.array(hags)
    n_total = len(xs)

    print(f"Loaded {n_total:,} detections")

    # Extract AOI polygons and evaluation data
    aoi_data = []
    for feat in aoi_geojson.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = extract_polygon_coords(geom)

        if coords:
            # Find matching evaluation result
            aoi_name = props.get("name", "Unknown")
            aoi_id = props.get("aoi_id", "")

            eval_result = None
            for r in eval_data.get("results", []):
                if r.get("aoi_id") == aoi_id:
                    eval_result = r
                    break

            aoi_data.append({
                "name": aoi_name,
                "aoi_id": aoi_id,
                "coords": np.array(coords),
                "field_count": props.get("penguin_count", 0),
                "lidar_count": eval_result.get("count", 0) if eval_result else 0,
                "density": eval_result.get("density_per_ha", 0) if eval_result else 0,
            })

    print(f"Loaded {len(aoi_data)} AOI polygons")

    # Create figure with dedicated metadata panel
    fig = plt.figure(figsize=(16, 12))
    ax = fig.add_axes([0.06, 0.12, 0.58, 0.78])
    cax = fig.add_axes([0.66, 0.28, 0.02, 0.46])
    meta_ax = fig.add_axes([0.70, 0.12, 0.28, 0.78])
    meta_ax.axis("off")

    # Plot all detections (gray, small)
    ax.scatter(xs, ys, c="lightgray", s=3, alpha=0.4, label=f"All detections ({n_total:,})")

    # Plot detections colored by HAG
    scatter = ax.scatter(xs, ys, c=hags, cmap="YlOrRd", s=5, alpha=0.6, edgecolors="none")
    cbar = fig.colorbar(scatter, cax=cax)
    cbar.set_label("Mean HAG (m)", fontsize=10)

    # Plot AOI polygons
    colors = ["#2ecc71", "#3498db"]  # Green for caves, blue for plains
    for i, aoi in enumerate(aoi_data):
        coords = aoi["coords"]
        if len(coords) > 0:
            # Plot polygon boundary
            poly_x = coords[:, 0]
            poly_y = coords[:, 1]

            # Close the polygon
            poly_x = np.append(poly_x, poly_x[0])
            poly_y = np.append(poly_y, poly_y[0])

            color = colors[i % len(colors)]
            ax.plot(poly_x, poly_y, color=color, linewidth=2.5, linestyle="-")
            ax.fill(poly_x, poly_y, color=color, alpha=0.15)

            # Add label at centroid
            centroid_x = coords[:, 0].mean()
            centroid_y = coords[:, 1].mean()

            label_text = (
                f"{aoi['name']}\n"
                f"Field: {aoi['field_count']} penguins\n"
                f"LiDAR: {aoi['lidar_count']} candidates\n"
                f"Ratio: {aoi['lidar_count']/aoi['field_count']:.1%}" if aoi['field_count'] > 0 else ""
            )

            ax.annotate(
                label_text,
                xy=(centroid_x, centroid_y),
                fontsize=9,
                fontweight="bold",
                ha="center",
                va="center",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.9, edgecolor=color, linewidth=2),
            )

    # Title
    ax.set_title(
        "San Lorenzo Full LiDAR — AOI Comparison Map\n"
        f"{n_total:,} total detections | {len(aoi_data)} AOIs with field counts",
        fontsize=14,
        fontweight="bold",
    )

    # Axis labels
    ax.set_xlabel("Easting (m) — EPSG:5345", fontsize=11)
    ax.set_ylabel("Northing (m) — EPSG:5345", fontsize=11)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3, linestyle="--")
    formatter = mticker.ScalarFormatter(useOffset=False)
    formatter.set_scientific(False)
    ax.xaxis.set_major_formatter(formatter)
    ax.yaxis.set_major_formatter(formatter)

    # Build metadata panel
    generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Summary stats
    total_field = sum(a["field_count"] for a in aoi_data)
    total_lidar = sum(a["lidar_count"] for a in aoi_data)

    metadata_lines = [
        "PROVENANCE",
        "─" * 45,
        f"Site: San Lorenzo (Argentina 2025)",
        f"Total detections: {n_total:,}",
        f"CRS: EPSG:5345 (POSGAR 2007 / Argentina 3)",
        "",
        "PROCESSING PARAMETERS",
        "─" * 45,
        f"Cell resolution: {params.get('cell_res', 'N/A')} m",
        f"HAG range: {params.get('hag_min', 'N/A')}–{params.get('hag_max', 'N/A')} m",
        f"Area filter: {params.get('min_area_cells', 'N/A')}–{params.get('max_area_cells', 'N/A')} cells",
        "",
        "AOI COMPARISON",
        "─" * 45,
    ]

    for aoi in aoi_data:
        ratio = aoi['lidar_count']/aoi['field_count'] if aoi['field_count'] > 0 else 0
        metadata_lines.append(f"{aoi['name']}:")
        metadata_lines.append(f"  Field count: {aoi['field_count']}")
        metadata_lines.append(f"  LiDAR candidates: {aoi['lidar_count']}")
        metadata_lines.append(f"  Detection ratio: {ratio:.1%}")

    metadata_lines.extend([
        "",
        f"TOTAL IN AOIs: {total_lidar} / {total_field} ({total_lidar/total_field:.1%})" if total_field > 0 else "",
        "",
        "SOURCE FILES",
        "─" * 45,
        f"Detections: San Lorenzo Full LiDAR LAS_detections.geojson",
        f"AOI: aoi_san_lorenzo_epsg5345.geojson",
        f"Eval: san_lorenzo_aoi_eval.json",
        "",
        "GENERATION",
        "─" * 45,
        f"Script: scripts/generate_aoi_comparison_map.py",
        f"Generated: {generation_time}",
    ])

    metadata_text = "\n".join(metadata_lines)

    # Add metadata box
    props_box = dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.95, edgecolor="gray")
    meta_ax.text(
        0.0, 1.0, metadata_text,
        transform=meta_ax.transAxes,
        fontsize=8,
        fontfamily="monospace",
        verticalalignment="top",
        bbox=props_box,
    )

    # Disclaimer at bottom
    fig.text(
        0.34, 0.04,
        "NOTE: Detections are CANDIDATES. AOI boundaries are approximate; ratios are provisional.",
        fontsize=10,
        ha="center",
        color="red",
        fontweight="bold",
    )

    # Extent info
    ax.text(
        0.5, -0.07,
        f"Extent: X [{xs.min():.1f}, {xs.max():.1f}] Y [{ys.min():.1f}, {ys.max():.1f}]",
        transform=ax.transAxes,
        fontsize=9,
        ha="center",
        style="italic",
    )

    # Scale bar + north arrow
    x_range = float(xs.max() - xs.min())
    _add_scale_bar(ax, _nice_scale_length(x_range * 0.2))
    _add_north_arrow(ax)

    # Legend for AOIs
    legend_patches = [
        mpatches.Patch(color=colors[0], alpha=0.3, label="High Density Caves AOI"),
        mpatches.Patch(color=colors[1], alpha=0.3, label="The Plains AOI"),
    ]
    ax.legend(handles=legend_patches, loc="lower left", fontsize=9)

    # Layout
    plt.tight_layout()

    # Save
    output_path = output_dir / "san_lorenzo_aoi_comparison.png"
    fig.savefig(output_path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(f"\nSaved: {output_path}")
    print(f"  Total detections: {n_total:,}")
    print(f"  AOIs: {len(aoi_data)}")
    for aoi in aoi_data:
        ratio = aoi['lidar_count']/aoi['field_count'] if aoi['field_count'] > 0 else 0
        print(f"    {aoi['name']}: {aoi['lidar_count']}/{aoi['field_count']} ({ratio:.1%})")

    print()
    print("=" * 60)
    print("COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
