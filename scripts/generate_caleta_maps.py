#!/usr/bin/env python3
"""
Generate static maps for Caleta Small and Tiny Islands.

Shows LiDAR candidate detections with LiDAR-derived AOI boundaries overlaid,
including field count comparison.

Usage:
    python scripts/generate_caleta_maps.py

Output:
    qc/panels/static_maps/caleta_tiny_island_detections.png
    qc/panels/static_maps/caleta_small_island_detections.png
    qc/panels/static_maps/caleta_overview.png
"""

import json
import math
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
from matplotlib.path import Path as MplPath
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent


def points_in_polygon(xs: np.ndarray, ys: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    """Return boolean mask of points inside polygon."""
    if len(polygon) < 3:
        return np.zeros(len(xs), dtype=bool)
    path = MplPath(polygon)
    points = np.column_stack([xs, ys])
    return path.contains_points(points)


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def extract_detection_coords(summary: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract x, y, hag from summary JSON detections."""
    xs, ys, hags = [], [], []
    for file_info in summary.get("files", []):
        for det in file_info.get("detections", []):
            xs.append(det.get("x", 0))
            ys.append(det.get("y", 0))
            hags.append(det.get("hag_mean", 0.35))
    return np.array(xs), np.array(ys), np.array(hags)


def extract_polygon_coords(geojson: dict) -> list[np.ndarray]:
    """Extract polygon coordinates from GeoJSON."""
    polygons = []
    for feat in geojson.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") == "Polygon":
            coords = geom.get("coordinates", [[]])[0]
            if coords:
                polygons.append(np.array(coords))
        elif geom.get("type") == "MultiPolygon":
            for poly in geom.get("coordinates", []):
                if poly and poly[0]:
                    polygons.append(np.array(poly[0]))
    return polygons


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
    ax.plot([x0, x1], [y0, y0], color="black", linewidth=2.5)
    ax.plot([x0, x0], [y0, y0 + 0.015 * y_range], color="black", linewidth=2.5)
    ax.plot([x1, x1], [y0, y0 + 0.015 * y_range], color="black", linewidth=2.5)
    ax.text(
        (x0 + x1) / 2.0,
        y0 + 0.025 * y_range,
        f"{int(length_m)} m",
        ha="center",
        va="bottom",
        fontsize=10,
        fontweight="bold",
        color="black",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.9, edgecolor="gray"),
    )


def _add_north_arrow(ax: plt.Axes) -> None:
    """Add a north arrow in axes coordinates."""
    ax.annotate(
        "",
        xy=(0.94, 0.93),
        xytext=(0.94, 0.86),
        xycoords="axes fraction",
        arrowprops=dict(facecolor="black", width=1.8, headwidth=7),
    )
    ax.text(0.94, 0.94, "N", transform=ax.transAxes, ha="center", va="bottom",
            fontsize=10, fontweight="bold")


def generate_island_map(
    site_name: str,
    display_name: str,
    summary_path: Path,
    aoi_path: Path,
    eval_path: Path,
    output_path: Path,
    epsg: int = 32720,
) -> None:
    """Generate a detection map for an island site with AOI overlay."""

    print(f"Generating {display_name} map...")

    # Load data
    summary = load_json(summary_path)
    aoi_geojson = load_json(aoi_path)
    eval_data = load_json(eval_path)

    # Extract detections
    xs, ys, hags = extract_detection_coords(summary)
    n_total = len(xs)

    if n_total == 0:
        print(f"  WARNING: No detections found")
        return

    # Extract AOI polygons
    polygons = extract_polygon_coords(aoi_geojson)

    # Filter to only detections INSIDE the AOI (exclude ocean detections)
    if polygons:
        inside_mask = np.zeros(len(xs), dtype=bool)
        for poly in polygons:
            inside_mask |= points_in_polygon(xs, ys, poly)
        n_outside = (~inside_mask).sum()
        if n_outside > 0:
            print(f"  Filtering out {n_outside} detections outside AOI (ocean/noise)")
        xs = xs[inside_mask]
        ys = ys[inside_mask]
        hags = hags[inside_mask]

    # Get evaluation results
    eval_results = eval_data.get("results", [])
    if eval_results:
        result = eval_results[0]
        lidar_count = result.get("count", 0)
        field_count = result.get("properties", {}).get("penguin_count", 0)
        area_ha = result.get("area_m2", 0) / 10000
        density = result.get("density_per_ha", 0)
    else:
        lidar_count = n_total
        field_count = 0
        area_ha = 0
        density = 0

    # Get processing parameters
    params = summary.get("params", {})
    hag_min = params.get("hag_min", 0.2)
    hag_max = params.get("hag_max", 0.6)
    cell_res = params.get("cell_res", 0.25)

    # Create figure
    fig = plt.figure(figsize=(14, 11))
    ax = fig.add_axes([0.07, 0.12, 0.52, 0.78])
    cax = fig.add_axes([0.60, 0.35, 0.02, 0.40])
    meta_ax = fig.add_axes([0.69, 0.12, 0.28, 0.78])
    meta_ax.axis("off")

    # Plot detections
    scatter = ax.scatter(
        xs, ys,
        c=hags,
        cmap="YlOrRd",
        s=18,
        alpha=0.7,
        edgecolors="none",
    )

    # Colorbar
    cbar = fig.colorbar(scatter, cax=cax)
    cbar.set_label("Candidate Height (m)", fontsize=11)

    # Plot AOI boundary
    for poly in polygons:
        if len(poly) > 0:
            poly_closed = np.vstack([poly, poly[0]])
            ax.plot(poly_closed[:, 0], poly_closed[:, 1],
                   color="#2ecc71", linewidth=2.5, linestyle="-", label="AOI (LiDAR-derived)")
            ax.fill(poly_closed[:, 0], poly_closed[:, 1],
                   color="#2ecc71", alpha=0.1)

    # Title
    ratio = lidar_count / field_count if field_count > 0 else 0
    ax.set_title(
        f"{display_name} — LiDAR Detection Map\n"
        f"{lidar_count:,} candidates inside AOI | {field_count:,} field count | {ratio:.0%} recall",
        fontsize=13,
        fontweight="bold",
    )

    # Axis labels
    ax.set_xlabel(f"Easting (m) — EPSG:{epsg}", fontsize=11)
    ax.set_ylabel(f"Northing (m) — EPSG:{epsg}", fontsize=11)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3, linestyle="--")

    # Format axis ticks (no scientific notation)
    formatter = mticker.ScalarFormatter(useOffset=False)
    formatter.set_scientific(False)
    ax.xaxis.set_major_formatter(formatter)
    ax.yaxis.set_major_formatter(formatter)

    # Scale bar and north arrow
    x_range = float(xs.max() - xs.min())
    _add_scale_bar(ax, _nice_scale_length(x_range * 0.25))
    _add_north_arrow(ax)

    # Legend
    ax.legend(loc="lower left", fontsize=10)

    # Build metadata panel
    generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    metadata_lines = [
        "PROVENANCE",
        "─" * 42,
        f"Site: {display_name}",
        f"Region: Caleta (Argentina 2025)",
        f"CRS: EPSG:{epsg} (UTM 20S)",
        "",
        "DETECTION SUMMARY",
        "─" * 42,
        f"Total candidates: {n_total:,}",
        f"Inside AOI: {lidar_count:,}",
        f"Field count: {field_count:,}",
        f"Recall (field baseline): {ratio:.1%}",
        "Precision: not available",
        "",
        "AOI GEOMETRY",
        "─" * 42,
        f"Area: {area_ha:.2f} ha",
        f"Density: {density:.0f} candidates/ha",
        f"Method: LiDAR-derived (Otsu threshold)",
        "",
        "INTERPRETATION",
        "─" * 42,
        "Candidates filtered by AOI",
        "and colored by height (HAG).",
        "",
        "PROCESSING PARAMETERS",
        "─" * 42,
        f"Cell resolution: {cell_res} m",
        f"HAG range: {hag_min}–{hag_max} m",
        "",
        "SOURCE FILES",
        "─" * 42,
        f"Detections: {summary_path.name}",
        f"AOI: {aoi_path.name}",
        f"Eval: {eval_path.name}",
        "",
        "GENERATION",
        "─" * 42,
        f"Script: scripts/generate_caleta_maps.py",
        f"Generated: {generation_time}",
    ]

    metadata_text = "\n".join(metadata_lines)

    # Add metadata panel
    props_box = dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.95, edgecolor="gray")
    meta_ax.text(
        0.0, 1.0, metadata_text,
        transform=meta_ax.transAxes,
        fontsize=8,
        fontfamily="monospace",
        verticalalignment="top",
        bbox=props_box,
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

    # Disclaimer
    fig.text(
        0.36, 0.04,
        "NOTE: Detections are CANDIDATES (blob centroids). AOI is LiDAR-derived, so recall is provisional.",
        fontsize=9,
        ha="center",
        color="#666666",
        fontweight="bold",
    )

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(f"  Saved: {output_path}")
    print(f"    Candidates: {lidar_count:,} / {field_count:,} field ({ratio:.1%})")


def generate_caleta_overview(output_path: Path) -> None:
    """Generate an overview map showing both Caleta islands."""

    print("Generating Caleta overview map...")

    # Load both datasets
    tiny_summary = load_json(PROJECT_ROOT / "data/interim/tiny_best.json")
    small_summary = load_json(PROJECT_ROOT / "data/interim/caleta_small_island.json")

    tiny_aoi = load_json(PROJECT_ROOT / "data/processed/aoi_caleta_tiny_island_epsg32720.geojson")
    small_aoi = load_json(PROJECT_ROOT / "data/processed/aoi_caleta_small_island_epsg32720.geojson")

    tiny_eval = load_json(PROJECT_ROOT / "data/processed/caleta_tiny_island_aoi_eval.json")
    small_eval = load_json(PROJECT_ROOT / "data/processed/caleta_small_island_aoi_eval.json")

    # Extract all detections
    tiny_xs, tiny_ys, tiny_hags = extract_detection_coords(tiny_summary)
    small_xs, small_ys, small_hags = extract_detection_coords(small_summary)

    # Extract AOI polygons
    tiny_polys = extract_polygon_coords(tiny_aoi)
    small_polys = extract_polygon_coords(small_aoi)

    # Filter to only detections INSIDE their respective AOIs
    if tiny_polys:
        tiny_mask = np.zeros(len(tiny_xs), dtype=bool)
        for poly in tiny_polys:
            tiny_mask |= points_in_polygon(tiny_xs, tiny_ys, poly)
        tiny_xs = tiny_xs[tiny_mask]
        tiny_ys = tiny_ys[tiny_mask]
        tiny_hags = tiny_hags[tiny_mask]

    if small_polys:
        small_mask = np.zeros(len(small_xs), dtype=bool)
        for poly in small_polys:
            small_mask |= points_in_polygon(small_xs, small_ys, poly)
        small_xs = small_xs[small_mask]
        small_ys = small_ys[small_mask]
        small_hags = small_hags[small_mask]

    # Combine (now only land detections)
    all_xs = np.concatenate([tiny_xs, small_xs])
    all_ys = np.concatenate([tiny_ys, small_ys])
    all_hags = np.concatenate([tiny_hags, small_hags])

    # Get eval results
    tiny_result = tiny_eval.get("results", [{}])[0]
    small_result = small_eval.get("results", [{}])[0]

    tiny_count = tiny_result.get("count", len(tiny_xs))
    tiny_field = tiny_result.get("properties", {}).get("penguin_count", 321)
    small_count = small_result.get("count", len(small_xs))
    small_field = small_result.get("properties", {}).get("penguin_count", 1557)

    total_lidar = tiny_count + small_count
    total_field = tiny_field + small_field

    # Create figure (overview map: AOI only)
    fig = plt.figure(figsize=(16, 10))
    ax = fig.add_axes([0.06, 0.12, 0.55, 0.78])
    meta_ax = fig.add_axes([0.69, 0.12, 0.28, 0.78])
    meta_ax.axis("off")

    # Plot AOI boundaries only (summary map)
    colors = {"tiny": "#3498db", "small": "#2ecc71"}

    for poly in tiny_polys:
        if len(poly) > 0:
            poly_closed = np.vstack([poly, poly[0]])
            ax.plot(poly_closed[:, 0], poly_closed[:, 1],
                   color=colors["tiny"], linewidth=2.5)
            ax.fill(poly_closed[:, 0], poly_closed[:, 1],
                   color=colors["tiny"], alpha=0.15)

    for poly in small_polys:
        if len(poly) > 0:
            poly_closed = np.vstack([poly, poly[0]])
            ax.plot(poly_closed[:, 0], poly_closed[:, 1],
                   color=colors["small"], linewidth=2.5)
            ax.fill(poly_closed[:, 0], poly_closed[:, 1],
                   color=colors["small"], alpha=0.15)

    # Add labels for each island at polygon centroids
    if tiny_polys:
        tiny_centers = np.concatenate(tiny_polys).mean(axis=0)
        tiny_ratio = tiny_count / tiny_field if tiny_field > 0 else 0
        ax.annotate(
            f"Tiny Island\nField: {tiny_field}\nLiDAR: {tiny_count}\nRecall: {tiny_ratio:.0%}",
            xy=(tiny_centers[0], tiny_centers[1]),
            fontsize=10,
            fontweight="bold",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.9,
                     edgecolor=colors["tiny"], linewidth=2),
        )

    if small_polys:
        small_centers = np.concatenate(small_polys).mean(axis=0)
        small_ratio = small_count / small_field if small_field > 0 else 0
        ax.annotate(
            f"Small Island\nField: {small_field}\nLiDAR: {small_count}\nRecall: {small_ratio:.0%}",
            xy=(small_centers[0], small_centers[1]),
            fontsize=10,
            fontweight="bold",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.9,
                     edgecolor=colors["small"], linewidth=2),
        )

    # Title
    overall_ratio = total_lidar / total_field if total_field > 0 else 0
    ax.set_title(
        f"Caleta Islands Overview — AOI Summary\n"
        f"{total_lidar:,} total candidates | {total_field:,} total field count | {overall_ratio:.0%} overall recall",
        fontsize=13,
        fontweight="bold",
    )

    ax.set_xlabel("Easting (m) — EPSG:32720", fontsize=11)
    ax.set_ylabel("Northing (m) — EPSG:32720", fontsize=11)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3, linestyle="--")

    formatter = mticker.ScalarFormatter(useOffset=False)
    formatter.set_scientific(False)
    ax.xaxis.set_major_formatter(formatter)
    ax.yaxis.set_major_formatter(formatter)

    # Scale bar and north arrow
    x_range = float(all_xs.max() - all_xs.min())
    _add_scale_bar(ax, _nice_scale_length(x_range * 0.2))
    _add_north_arrow(ax)

    # Legend
    legend_patches = [
        mpatches.Patch(color=colors["tiny"], alpha=0.3, label="Tiny Island AOI"),
        mpatches.Patch(color=colors["small"], alpha=0.3, label="Small Island AOI"),
    ]
    ax.legend(handles=legend_patches, loc="lower left", fontsize=10)

    # Metadata panel
    generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    metadata_lines = [
        "PROVENANCE",
        "─" * 42,
        "Site: Caleta Islands (Argentina 2025)",
        "CRS: EPSG:32720 (UTM 20S)",
        "",
        "TINY ISLAND",
        "─" * 42,
        f"Field count: {tiny_field}",
        f"LiDAR candidates: {tiny_count}",
        f"Recall (field baseline): {tiny_count/tiny_field:.1%}" if tiny_field else "N/A",
        "Precision: not available",
        f"Area: {tiny_result.get('area_m2', 0)/10000:.2f} ha",
        "",
        "SMALL ISLAND",
        "─" * 42,
        f"Field count: {small_field}",
        f"LiDAR candidates: {small_count}",
        f"Recall (field baseline): {small_count/small_field:.1%}" if small_field else "N/A",
        "Precision: not available",
        f"Area: {small_result.get('area_m2', 0)/10000:.2f} ha",
        "",
        "COMBINED TOTALS",
        "─" * 42,
        f"Total field: {total_field:,}",
        f"Total LiDAR: {total_lidar:,}",
        f"Overall recall: {overall_ratio:.1%}",
        "",
        "AOI METHOD",
        "─" * 42,
        "LiDAR-derived footprints using",
        "Otsu threshold on point density",
        "",
        "INTERPRETATION",
        "─" * 42,
        "AOIs are LiDAR-derived;",
        "recall is provisional.",
        "",
        "GENERATION",
        "─" * 42,
        f"Script: scripts/generate_caleta_maps.py",
        f"Generated: {generation_time}",
    ]

    metadata_text = "\n".join(metadata_lines)

    props_box = dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.95, edgecolor="gray")
    meta_ax.text(
        0.0, 1.0, metadata_text,
        transform=meta_ax.transAxes,
        fontsize=8,
        fontfamily="monospace",
        verticalalignment="top",
        bbox=props_box,
    )

    # Disclaimer
    fig.text(
        0.34, 0.04,
        "NOTE: AOIs are LiDAR-derived (Otsu). Recall is provisional and not independent validation.",
        fontsize=9,
        ha="center",
        color="#666666",
        fontweight="bold",
    )

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(f"  Saved: {output_path}")
    print(f"    Total: {total_lidar:,} / {total_field:,} ({overall_ratio:.1%})")


def main():
    output_dir = PROJECT_ROOT / "qc" / "panels" / "static_maps"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("CALETA ISLANDS MAP GENERATION")
    print("=" * 60)
    print()

    # Generate Tiny Island map
    generate_island_map(
        site_name="caleta_tiny_island",
        display_name="Caleta Tiny Island",
        summary_path=PROJECT_ROOT / "data/interim/tiny_best.json",
        aoi_path=PROJECT_ROOT / "data/processed/aoi_caleta_tiny_island_epsg32720.geojson",
        eval_path=PROJECT_ROOT / "data/processed/caleta_tiny_island_aoi_eval.json",
        output_path=output_dir / "caleta_tiny_island_detections.png",
    )
    print()

    # Generate Small Island map
    generate_island_map(
        site_name="caleta_small_island",
        display_name="Caleta Small Island",
        summary_path=PROJECT_ROOT / "data/interim/caleta_small_island.json",
        aoi_path=PROJECT_ROOT / "data/processed/aoi_caleta_small_island_epsg32720.geojson",
        eval_path=PROJECT_ROOT / "data/processed/caleta_small_island_aoi_eval.json",
        output_path=output_dir / "caleta_small_island_detections.png",
    )
    print()

    # Generate overview map
    generate_caleta_overview(output_dir / "caleta_overview.png")

    print()
    print("=" * 60)
    print("COMPLETE")
    print(f"Maps saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
