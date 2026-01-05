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

    args = p.parse_args()
    lidar_path = Path(args.lidar_summary)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lidar = json.loads(lidar_path.read_text())
    dets = _extract_detections(lidar)
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
        "area_m2",
        "area_cells",
        "circularity",
        "solidity",
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
                    "area_m2": d.get("area_m2", ""),
                    "area_cells": d.get("area_cells", ""),
                    "circularity": d.get("circularity", ""),
                    "solidity": d.get("solidity", ""),
                    "stratum": d.get("stratum", ""),
                    "crop_png": crop_paths.get(det_id, ""),
                }
            )

    manifest_obj: Dict[str, Any] = {
        "schema_version": "1",
        "purpose": "lidar_label_sample",
        "lidar_summary": str(lidar_path),
        "out_dir": str(out_dir),
        "n": int(args.n),
        "seed": str(args.seed),
        "crop": {
            "enabled": (not bool(args.no_crops)),
            "radius_m": float(args.crop_radius_m),
            "cell_res": float(crop_cell_res),
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

    # Plot a small panel with the detection marker.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    im = ax.imshow(hag, origin="lower", cmap="Greys", interpolation="none")
    # detection marker in local grid coordinates
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


