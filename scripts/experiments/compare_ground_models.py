#!/usr/bin/env python3
"""Compare ground DEM estimation methods: min, p05, and CSF.

For a given tile, runs detection 3x (or 2x without CSF) and collects:
- DEM surface stats (mean, std, range)
- Detection count
- Mean HAG of detections
- DEM difference grids
- Runtime and memory peak

Outputs JSON + multi-panel comparison plot.

Usage:
    python scripts/experiments/compare_ground_models.py \
        --tile "data/2025/Caleta Tiny Island/cloud0.las" \
        --out data/interim/ground_model_comparison.json \
        --crs-epsg 32720
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT / "scripts"), str(ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import run_lidar_hag as lidar


def _run_one_method(
    las_path: Path,
    ground_method: str,
    cell_res: float,
    hag_min: float,
    hag_max: float,
    min_area_cells: int,
    max_area_cells: int,
    chunk_size: int,
    **csf_kwargs,
) -> dict:
    """Run the pipeline for one ground method and return stats."""
    t0 = time.time()

    mins, maxs, npts = lidar.read_bounds_and_counts(las_path, chunk_size)
    ny, nx = lidar._grid_shape(mins, maxs, cell_res)

    csf_meta = None
    actual_method = ground_method
    if ground_method == "csf":
        if not lidar.HAS_CSF:
            return {"method": "csf", "error": "CSF not installed", "skipped": True}
        dem, csf_meta = lidar._build_ground_csf(
            las_path, cell_res, ny, nx, mins, **csf_kwargs,
        )
        if dem.size == 0:
            return {"method": "csf", "error": "CSF fallback triggered", "skipped": True}
        meta = {"mins": mins.tolist(), "maxs": maxs.tolist(), "cell_res": cell_res, "shape": [int(ny), int(nx)]}
    else:
        dem, meta = lidar.build_ground_dem(
            las_path, cell_res, chunk_size, verbose=False,
            ground_method=ground_method, bounds=(mins, maxs),
        )

    hag = lidar.build_hag_grid(las_path, dem, meta, chunk_size, top_method="max")
    count, labeled, dets, _ = lidar.detect_penguins_from_hag(
        hag, hag_min, hag_max, min_area_cells, max_area_cells,
        connectivity=2, cell_res=cell_res, mins=np.array(meta["mins"]),
    )
    dt = time.time() - t0

    hag_means = [d["hag_mean"] for d in dets if "hag_mean" in d]
    result = {
        "method": ground_method,
        "detection_count": count,
        "runtime_s": round(dt, 2),
        "dem_stats": {
            "mean": round(float(np.mean(dem)), 4),
            "std": round(float(np.std(dem)), 4),
            "min": round(float(np.min(dem)), 4),
            "max": round(float(np.max(dem)), 4),
        },
        "hag_stats": {
            "mean": round(float(np.mean(hag)), 4),
            "max": round(float(np.max(hag)), 4),
        },
        "mean_det_hag": round(float(np.mean(hag_means)), 4) if hag_means else None,
        "grid_shape": [int(ny), int(nx)],
    }
    if csf_meta is not None:
        result["csf_info"] = csf_meta
    # Store raw grids for difference computation (not serialized to JSON)
    result["_dem"] = dem
    result["_hag"] = hag
    result["_labeled"] = labeled
    return result


def _save_comparison_plot(results: list[dict], out_png: Path) -> None:
    """Save a multi-panel comparison plot."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("WARNING: matplotlib not available; skipping plot", file=sys.stderr)
        return

    methods = [r for r in results if not r.get("skipped")]
    n = len(methods)
    if n == 0:
        return

    fig, axes = plt.subplots(2, max(n, 2), figsize=(6 * max(n, 2), 10))
    if n == 1:
        axes = axes.reshape(2, -1)

    for i, r in enumerate(methods):
        dem = r.get("_dem")
        hag = r.get("_hag")
        labeled = r.get("_labeled")
        if dem is None:
            continue

        ax_dem = axes[0, i]
        ax_dem.imshow(dem, origin="lower", cmap="terrain")
        ax_dem.set_title(f"{r['method']} DEM\n{r['detection_count']} detections")
        ax_dem.set_xticks([])
        ax_dem.set_yticks([])

        ax_det = axes[1, i]
        ax_det.imshow(hag, origin="lower", cmap="Greys", vmin=0, vmax=1.0)
        if labeled is not None and labeled.max() > 0:
            import numpy.ma as ma
            overlay = ma.masked_where(labeled == 0, labeled)
            ax_det.imshow(overlay, origin="lower", cmap="autumn", alpha=0.4)
        ax_det.set_title(f"{r['method']} HAG + detections")
        ax_det.set_xticks([])
        ax_det.set_yticks([])

    # Hide extra axes
    for j in range(n, axes.shape[1]):
        axes[0, j].set_visible(False)
        axes[1, j].set_visible(False)

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Compare ground DEM estimation methods")
    parser.add_argument("--tile", required=True, help="Path to LAS/LAZ tile")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--plot", default=None, help="Output PNG path for comparison plot")
    parser.add_argument("--crs-epsg", type=int, default=32720)
    parser.add_argument("--cell-res", type=float, default=0.25)
    parser.add_argument("--hag-min", type=float, default=0.28)
    parser.add_argument("--hag-max", type=float, default=0.48)
    parser.add_argument("--min-area-cells", type=int, default=3)
    parser.add_argument("--max-area-cells", type=int, default=60)
    parser.add_argument("--chunk-size", type=int, default=1_000_000)
    parser.add_argument("--csf-cloth-resolution", type=float, default=0.5)
    parser.add_argument("--csf-class-threshold", type=float, default=0.3)
    args = parser.parse_args()

    tile_path = Path(args.tile).resolve()
    if not tile_path.exists():
        raise SystemExit(f"Tile not found: {tile_path}")

    methods = ["min", "p05", "csf"]
    results = []
    for method in methods:
        print(f"Running ground method: {method} ...", flush=True)
        r = _run_one_method(
            tile_path,
            ground_method=method,
            cell_res=args.cell_res,
            hag_min=args.hag_min,
            hag_max=args.hag_max,
            min_area_cells=args.min_area_cells,
            max_area_cells=args.max_area_cells,
            chunk_size=args.chunk_size,
            csf_cloth_resolution=args.csf_cloth_resolution,
            csf_class_threshold=args.csf_class_threshold,
        )
        print(f"  {method}: {r.get('detection_count', 'N/A')} detections, "
              f"{r.get('runtime_s', 'N/A')}s", flush=True)
        results.append(r)

    # Compute DEM differences between methods
    diffs = {}
    valid = {r["method"]: r for r in results if "_dem" in r and not r.get("skipped")}
    for a_name, a_result in valid.items():
        for b_name, b_result in valid.items():
            if a_name >= b_name:
                continue
            diff = a_result["_dem"] - b_result["_dem"]
            diffs[f"{a_name}_minus_{b_name}"] = {
                "mean": round(float(np.mean(diff)), 4),
                "std": round(float(np.std(diff)), 4),
                "min": round(float(np.min(diff)), 4),
                "max": round(float(np.max(diff)), 4),
            }

    # Save plot
    if args.plot:
        plot_path = Path(args.plot).resolve()
        _save_comparison_plot(results, plot_path)
        print(f"Plot saved: {plot_path}")
    elif args.out:
        plot_path = Path(args.out).with_suffix(".png")
        _save_comparison_plot(results, plot_path)

    # Serialize (strip numpy arrays)
    serializable = []
    for r in results:
        sr = {k: v for k, v in r.items() if not k.startswith("_")}
        serializable.append(sr)

    output = {
        "tile": str(tile_path),
        "crs_epsg": args.crs_epsg,
        "cell_res": args.cell_res,
        "hag_range": [args.hag_min, args.hag_max],
        "area_range": [args.min_area_cells, args.max_area_cells],
        "methods": serializable,
        "dem_differences": diffs,
    }

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Results saved: {out_path}")


if __name__ == "__main__":
    main()
