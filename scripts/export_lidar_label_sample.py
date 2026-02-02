#!/usr/bin/env python3
"""
Export a deterministic label-sample bundle for LiDAR detections.

Outputs:
- sample.csv: rows for manual labeling (TP/FP/uncertain + notes)
- sample_manifest.json: reproducible record of selection + parameters
- crops/*.png: small HAG crops around each detection (optional)

This is intended to bootstrap a precision / FP-rate estimate without full GT.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np

from pipelines.label_sample import select_label_sample


def main() -> None:
    p = argparse.ArgumentParser(description="Export a label-sample bundle for LiDAR detections.")
    p.add_argument("--lidar-summary", required=True, help="Path to LiDAR summary JSON (lidar_candidates).")
    p.add_argument("--out-dir", required=True, help="Output directory for the label bundle.")
    p.add_argument("--n", type=int, default=80, help="Total detections to sample across strata.")
    p.add_argument("--seed", default="0", help="Deterministic sampling seed.")
    p.add_argument("--no-crops", action="store_true", help="Skip generating PNG crops (fast).")
    p.add_argument("--crop-radius-m", type=float, default=1.5, help="Half-width of crop window in meters.")
    p.add_argument(
        "--crop-cell-res",
        type=float,
        default=None,
        help="Crop grid resolution (meters). Defaults to lidar summary params cell_res (fallback 0.25).",
    )
    p.add_argument(
        "--crop-chunk-size",
        type=int,
        default=1_000_000,
        help="LAS streaming chunk size used for crop extraction.",
    )
    p.add_argument(
        "--ground-method",
        default=None,
        choices=[None, "min", "p05"],
        help="Override ground method for crop HAG visualization (defaults to summary params).",
    )
    p.add_argument(
        "--top-method",
        default=None,
        choices=[None, "max", "p95"],
        help="Override top method for crop HAG visualization (defaults to summary params).",
    )
    p.add_argument(
        "--top-zscore-cap",
        type=float,
        default=None,
        help="Override top outlier z-score cap for crop HAG visualization (defaults to summary params).",
    )
    p.add_argument(
        "--top-quantile-lr",
        type=float,
        default=None,
        help="Override online p95 learning rate for crop HAG visualization (defaults to summary params).",
    )
    p.add_argument(
        "--aoi-geojson",
        type=Path,
        default=None,
        help="AOI polygon GeoJSON; only detections inside AOI will be sampled.",
    )
    p.add_argument(
        "--rgb-crops",
        action="store_true",
        help="Include RGB point-cloud crops alongside HAG crops (requires RGB in LAS).",
    )

    args = p.parse_args()
    lidar_path = Path(args.lidar_summary)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lidar = json.loads(lidar_path.read_text())
    dets = _extract_detections(lidar)
    if args.aoi_geojson is not None:
        pre_count = len(dets)
        dets = _filter_to_aoi(dets, Path(args.aoi_geojson))
        print(f"AOI filter: {len(dets)}/{pre_count} detections inside AOI", flush=True)
    sample = select_label_sample(dets, n_total=int(args.n), seed=str(args.seed))
    if len(sample) < int(args.n) and len(dets) >= int(args.n):
        print(
            f"WARNING: Requested n={int(args.n)} but produced sample_count={len(sample)}. "
            "This indicates sparse strata behavior; sample selection should normally backfill.",
            flush=True,
        )
    if len(sample) < int(args.n) and len(dets) < int(args.n):
        print(
            f"WARNING: Requested n={int(args.n)} but only {len(dets)} detections available; "
            f"exporting sample_count={len(sample)}.",
            flush=True,
        )

    # Normalize + enrich fields for output
    for d in sample:
        # Ensure stable accessors for downstream scripts/reviewers
        d.setdefault("file", d.get("_file") or d.get("path") or "")
        d.setdefault("tile", d.get("tile") or "")

    sample_csv = out_dir / "label_sample.csv"
    manifest = out_dir / "label_sample_manifest.json"
    crops_dir = out_dir / "crops"
    if not args.no_crops:
        crops_dir.mkdir(parents=True, exist_ok=True)

    crop_cell_res = _infer_cell_res(lidar, override=args.crop_cell_res)
    ground_method = _infer_param(lidar, "ground_method", override=args.ground_method) or "min"
    top_method = _infer_param(lidar, "top_method", override=args.top_method) or "p95"
    top_zscore_cap = _infer_float(lidar, "top_zscore_cap", override=args.top_zscore_cap)
    top_quantile_lr = _infer_float(lidar, "top_quantile_lr", override=args.top_quantile_lr)

    crop_paths: Dict[str, str] = {}
    if not args.no_crops and sample:
        for d in sample:
            det_id = str(d.get("id", ""))
            las_path = Path(str(d.get("file", "")))
            if not las_path.exists():
                continue
            png = crops_dir / f"{_safe_filename(det_id)}.png"
            try:
                _write_crop_png(
                    las_path=las_path,
                    x=float(d["x"]),
                    y=float(d["y"]),
                    out_png=png,
                    radius_m=float(args.crop_radius_m),
                    cell_res=float(crop_cell_res),
                    chunk_size=int(args.crop_chunk_size),
                    ground_method=str(ground_method),
                    top_method=str(top_method),
                    top_zscore_cap=top_zscore_cap,
                    top_quantile_lr=top_quantile_lr,
                    title=str(det_id),
                    rgb=bool(args.rgb_crops),
                )
                crop_paths[det_id] = str(png)
            except Exception:
                # Crop generation is best-effort; the CSV/manifest are the critical artifacts.
                continue

    fieldnames = [
        "label",  # human-filled: tp/fp/uncertain
        "notes",
        "id",
        "file",
        "tile",
        "x",
        "y",
        "hag_mean",
        "hag_max",
        "hag_std",
        "area_m2",
        "area_cells",
        "circularity",
        "solidity",
        "intensity_mean",
        "rgb_r_mean",
        "rgb_g_mean",
        "rgb_b_mean",
        "stratum",
        "crop_png",
    ]
    with open(sample_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for d in sample:
            det_id = str(d.get("id", ""))
            w.writerow(
                {
                    "label": "",
                    "notes": "",
                    "id": det_id,
                    "file": d.get("file", ""),
                    "tile": d.get("tile", ""),
                    "x": d.get("x", ""),
                    "y": d.get("y", ""),
                    "hag_mean": d.get("hag_mean", ""),
                    "hag_max": d.get("hag_max", ""),
                    "hag_std": d.get("hag_std", ""),
                    "area_m2": d.get("area_m2", ""),
                    "area_cells": d.get("area_cells", ""),
                    "circularity": d.get("circularity", ""),
                    "solidity": d.get("solidity", ""),
                    "intensity_mean": d.get("intensity_mean", ""),
                    "rgb_r_mean": d.get("rgb_r_mean", ""),
                    "rgb_g_mean": d.get("rgb_g_mean", ""),
                    "rgb_b_mean": d.get("rgb_b_mean", ""),
                    "stratum": d.get("stratum", ""),
                    "crop_png": crop_paths.get(det_id, ""),
                }
            )

    manifest_obj: Dict[str, Any] = {
        "schema_version": "2",
        "purpose": "lidar_label_sample",
        "lidar_summary": str(lidar_path),
        "aoi_geojson": str(args.aoi_geojson) if args.aoi_geojson else None,
        "out_dir": str(out_dir),
        "n": int(args.n),
        "seed": str(args.seed),
        "crop": {
            "enabled": (not bool(args.no_crops)),
            "rgb": bool(args.rgb_crops),
            "radius_m": float(args.crop_radius_m),
            "cell_res": float(crop_cell_res),
            "rgb_cell_res": 0.10 if args.rgb_crops else None,
            "chunk_size": int(args.crop_chunk_size),
            "ground_method": str(ground_method),
            "top_method": str(top_method),
            "top_zscore_cap": top_zscore_cap,
            "top_quantile_lr": top_quantile_lr,
        },
        "crs": lidar.get("crs"),
        "contract": lidar.get("contract"),
        "sample_count": int(len(sample)),
        "sample_csv": str(sample_csv),
        "sample": [
            {
                "id": d.get("id"),
                "file": d.get("file"),
                "tile": d.get("tile"),
                "x": d.get("x"),
                "y": d.get("y"),
                "stratum": d.get("stratum"),
                "crop_png": crop_paths.get(str(d.get("id", ""))),
            }
            for d in sample
        ],
    }
    manifest.write_text(json.dumps(manifest_obj, indent=2))

    print(str(out_dir))


def _infer_cell_res(lidar: Mapping[str, Any], *, override: Optional[float]) -> float:
    if override is not None:
        return float(override)
    params = lidar.get("params")
    if isinstance(params, dict) and "cell_res" in params:
        try:
            return float(params["cell_res"])
        except Exception:
            pass
    return 0.25


def _infer_param(lidar: Mapping[str, Any], key: str, *, override: Optional[str]) -> Optional[str]:
    if override is not None:
        return str(override)
    params = lidar.get("params")
    if isinstance(params, dict) and key in params and params[key] is not None:
        return str(params[key])
    return None


def _infer_float(lidar: Mapping[str, Any], key: str, *, override: Optional[float]) -> Optional[float]:
    if override is not None:
        return float(override)
    params = lidar.get("params")
    if isinstance(params, dict) and key in params and params[key] is not None:
        try:
            return float(params[key])
        except Exception:
            return None
    return None


def _filter_to_aoi(dets: List[Dict[str, Any]], aoi_path: Path) -> List[Dict[str, Any]]:
    """Filter detections to those inside AOI polygon(s)."""
    from pipelines.aoi_eval import _extract_aois, _points_in_geometry

    aoi_obj = json.loads(aoi_path.read_text())
    aois = _extract_aois(aoi_obj)

    # Build XY array (only for dets with coordinates)
    valid = [(i, d) for i, d in enumerate(dets) if "x" in d and "y" in d]
    if not valid:
        return []
    indices, valid_dets = zip(*valid)
    coords = np.array([[float(d["x"]), float(d["y"])] for d in valid_dets], dtype=np.float64)

    # Union of all AOI polygons
    mask = np.zeros(len(coords), dtype=bool)
    for aoi in aois:
        mask |= _points_in_geometry(coords, aoi["geometry"])

    return [d for d, m in zip(valid_dets, mask) if m]


def _extract_detections(summary: Mapping[str, Any]) -> List[Dict[str, Any]]:
    dets: List[Dict[str, Any]] = []
    if isinstance(summary.get("detections"), list):
        for det in summary["detections"]:
            if isinstance(det, dict):
                dets.append(det)
        return dets
    files = summary.get("files")
    if not isinstance(files, list):
        return []
    for file_entry in files:
        if not isinstance(file_entry, dict):
            continue
        file_path = file_entry.get("path")
        for det in file_entry.get("detections", []) or []:
            if not isinstance(det, dict):
                continue
            d = dict(det)
            if file_path:
                d.setdefault("file", str(file_path))
            dets.append(d)
    return dets


def _safe_filename(s: str) -> str:
    keep = []
    for ch in s:
        if ch.isalnum() or ch in ("_", "-", "."):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep)[:180] or "det"


def _build_rgb_grid(
    las_path: Path,
    *,
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
    cell_res: float = 0.10,
    chunk_size: int = 1_000_000,
) -> Optional[np.ndarray]:
    """Read RGB from LAS within bounds and rasterize to (H, W, 3) uint8 grid.

    Returns None if the LAS file has no RGB fields.
    """
    import laspy

    nx = max(1, int(np.ceil((x_max - x_min) / cell_res)))
    ny = max(1, int(np.ceil((y_max - y_min) / cell_res)))

    r_sum = np.zeros((ny, nx), dtype=np.float64)
    g_sum = np.zeros((ny, nx), dtype=np.float64)
    b_sum = np.zeros((ny, nx), dtype=np.float64)
    count = np.zeros((ny, nx), dtype=np.int32)

    has_rgb = False
    max_val = 0.0

    with laspy.open(str(las_path)) as reader:
        for chunk in reader.chunk_iterator(chunk_size):
            pts_x = np.asarray(chunk.x, dtype=np.float64)
            pts_y = np.asarray(chunk.y, dtype=np.float64)

            mask = (
                (pts_x >= x_min) & (pts_x < x_max)
                & (pts_y >= y_min) & (pts_y < y_max)
            )
            if not mask.any():
                continue

            try:
                r = np.asarray(chunk.red, dtype=np.float64)[mask]
                g = np.asarray(chunk.green, dtype=np.float64)[mask]
                b = np.asarray(chunk.blue, dtype=np.float64)[mask]
                has_rgb = True
            except (AttributeError, Exception):
                continue

            xi = np.clip(((pts_x[mask] - x_min) / cell_res).astype(int), 0, nx - 1)
            yi = np.clip(((pts_y[mask] - y_min) / cell_res).astype(int), 0, ny - 1)

            np.add.at(r_sum, (yi, xi), r)
            np.add.at(g_sum, (yi, xi), g)
            np.add.at(b_sum, (yi, xi), b)
            np.add.at(count, (yi, xi), 1)

            max_val = max(max_val, float(r.max()), float(g.max()), float(b.max()))

    if not has_rgb or count.max() == 0:
        return None

    valid = count > 0
    r_avg = np.zeros_like(r_sum)
    g_avg = np.zeros_like(g_sum)
    b_avg = np.zeros_like(b_sum)
    r_avg[valid] = r_sum[valid] / count[valid]
    g_avg[valid] = g_sum[valid] / count[valid]
    b_avg[valid] = b_sum[valid] / count[valid]

    # 16-bit LAS RGB → 8-bit display: divide by 256 (standard convention).
    # If max ≤ 255, values are already 8-bit stored in 16-bit fields.
    if max_val > 255:
        r_avg = r_avg / 256.0
        g_avg = g_avg / 256.0
        b_avg = b_avg / 256.0

    rgb = np.stack([
        np.clip(r_avg, 0, 255).astype(np.uint8),
        np.clip(g_avg, 0, 255).astype(np.uint8),
        np.clip(b_avg, 0, 255).astype(np.uint8),
    ], axis=-1)

    return rgb


def _write_crop_png(
    *,
    las_path: Path,
    x: float,
    y: float,
    out_png: Path,
    radius_m: float,
    cell_res: float,
    chunk_size: int,
    ground_method: str,
    top_method: str,
    top_zscore_cap: Optional[float],
    top_quantile_lr: Optional[float],
    title: str,
    rgb: bool = False,
) -> None:
    # Import the existing implementation helpers to avoid duplicating HAG math.
    from scripts.run_lidar_hag import build_ground_dem, build_hag_grid  # type: ignore

    mins = np.array([x - radius_m, y - radius_m, 0.0], dtype=float)
    maxs = np.array([x + radius_m, y + radius_m, 0.0], dtype=float)
    dem, meta = build_ground_dem(
        las_path,
        cell_res=float(cell_res),
        chunk_size=int(chunk_size),
        verbose=False,
        ground_method=str(ground_method),
        bounds=(mins, maxs),
    )
    hag = build_hag_grid(
        las_path,
        dem,
        meta,
        int(chunk_size),
        top_method=str(top_method),
        top_zscore_cap=top_zscore_cap,
        top_quantile_lr=float(top_quantile_lr) if top_quantile_lr is not None else 0.05,
    )

    # Attempt RGB grid at finer resolution for visual detail.
    rgb_grid = None
    if rgb:
        rgb_cell_res = 0.10
        rgb_grid = _build_rgb_grid(
            las_path,
            x_min=float(mins[0]),
            y_min=float(mins[1]),
            x_max=float(maxs[0]),
            y_max=float(maxs[1]),
            cell_res=rgb_cell_res,
            chunk_size=chunk_size,
        )

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_png.parent.mkdir(parents=True, exist_ok=True)

    if rgb_grid is not None:
        # Side-by-side: RGB (left) + HAG (right)
        fig, (ax_rgb, ax_hag) = plt.subplots(1, 2, figsize=(8.4, 4.2))

        ax_rgb.imshow(rgb_grid, origin="lower", interpolation="none")
        gx_r = (x - float(mins[0])) / rgb_cell_res
        gy_r = (y - float(mins[1])) / rgb_cell_res
        ax_rgb.plot(gx_r, gy_r, marker="x", color="cyan", markersize=8, mew=2)
        ax_rgb.set_xticks([])
        ax_rgb.set_yticks([])
        ax_rgb.set_title("RGB", fontsize=8)

        ax_hag.imshow(hag, origin="lower", cmap="Greys", interpolation="none")
        gx_h = (x - float(meta["mins"][0])) / float(meta["cell_res"])
        gy_h = (y - float(meta["mins"][1])) / float(meta["cell_res"])
        ax_hag.plot(gx_h, gy_h, marker="x", color="cyan", markersize=8, mew=2)
        ax_hag.set_xticks([])
        ax_hag.set_yticks([])
        ax_hag.set_title("HAG", fontsize=8)

        fig.suptitle(title, fontsize=8)
    else:
        # HAG only (original behavior)
        fig, ax = plt.subplots(figsize=(4.2, 4.2))
        ax.imshow(hag, origin="lower", cmap="Greys", interpolation="none")
        gx = (x - float(meta["mins"][0])) / float(meta["cell_res"])
        gy = (y - float(meta["mins"][1])) / float(meta["cell_res"])
        ax.plot(gx, gy, marker="x", color="cyan", markersize=8, mew=2)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(title, fontsize=8)

    fig.tight_layout()
    fig.savefig(out_png, dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    main()


