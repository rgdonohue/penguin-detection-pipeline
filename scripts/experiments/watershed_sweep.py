#!/usr/bin/env python3
"""Watershed parameter sweep experiment.

Systematically evaluate watershed splitting against a baseline (no watershed),
using AOI-clipped counts for comparability with field counts.

Parameter grid:
- Watershed: off (baseline), on
- h_maxima: [0.02, 0.03, 0.05, 0.07, 0.10] m (when on)
- min_split_area_cells: [4, 8, 12, 20] (when on)
- Total: 1 baseline + 20 watershed configs = 21 runs

Usage:
    python scripts/experiments/watershed_sweep.py \
        --data-root "data/2025/Caleta Tiny Island" \
        --aoi data/processed/aoi_caleta_tiny_island_epsg32720.geojson \
        --out data/interim/watershed_sweep.json \
        --crs-epsg 32720
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT / "scripts"), str(ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import run_lidar_hag as lidar
from pipelines.aoi_eval import AoiEvalParams, run as aoi_eval_run


H_MAXIMA_VALUES = [0.02, 0.03, 0.05, 0.07, 0.10]
MIN_SPLIT_AREA_VALUES = [4, 8, 12, 20]


def _run_pipeline(
    data_root: Path,
    out_json: Path,
    cell_res: float,
    hag_min: float,
    hag_max: float,
    min_area_cells: int,
    max_area_cells: int,
    chunk_size: int,
    crs_epsg: int,
    dedupe_radius_m: float,
    apply_watershed: bool,
    h_maxima_h: float,
    min_split_area_cells: int,
) -> dict:
    """Run the full LiDAR pipeline and return the summary dict."""
    files = lidar.find_lidar_files(data_root)
    if not files:
        raise RuntimeError(f"No LAS/LAZ files found under {data_root}")

    crs_meta = {"epsg": crs_epsg}
    all_detections = []
    total_count = 0

    for f in files:
        info = lidar.process_file(
            f,
            cell_res=cell_res,
            hag_min=hag_min,
            hag_max=hag_max,
            min_area_cells=min_area_cells,
            max_area_cells=max_area_cells,
            chunk_size=chunk_size,
            verbose=False,
            plots_dir=None,
            ground_method="min",
            top_method="max",
            connectivity=2,
            apply_watershed=apply_watershed,
            h_maxima_h=h_maxima_h,
            min_split_area_cells=min_split_area_cells,
        )
        total_count += info.get("count", 0)
        for d in info.get("detections", []) or []:
            if "x" in d and "y" in d and d.get("id"):
                all_detections.append(d)

    # Dedup
    if dedupe_radius_m > 0 and all_detections:
        deduped, _ = lidar._dedupe_detections(all_detections, radius_m=dedupe_radius_m)
    else:
        deduped = all_detections

    summary = {
        "crs": crs_meta,
        "files": [{"detections": deduped}],
        "total_count": len(deduped),
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2))
    return summary


def _get_aoi_count(lidar_summary_path: Path, aoi_path: Path, crs_epsg: int) -> int:
    """Run AOI eval and return the inside-AOI count."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        eval_out = Path(f.name)

    params = AoiEvalParams(
        lidar_summary=lidar_summary_path,
        aoi_geojson=aoi_path,
        out_path=eval_out,
        aoi_crs_epsg=crs_epsg,
    )
    aoi_eval_run(params)
    result = json.loads(eval_out.read_text())
    total_inside = sum(r.get("count", 0) for r in result.get("results", []))
    eval_out.unlink(missing_ok=True)
    return total_inside


def main():
    parser = argparse.ArgumentParser(description="Watershed parameter sweep")
    parser.add_argument("--data-root", required=True, help="Folder with LAS/LAZ files")
    parser.add_argument("--aoi", required=True, help="AOI GeoJSON for clipping")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--crs-epsg", type=int, default=32720)
    parser.add_argument("--field-count", type=int, default=None, help="Field count for delta comparison")
    parser.add_argument("--cell-res", type=float, default=0.25)
    parser.add_argument("--hag-min", type=float, default=0.28)
    parser.add_argument("--hag-max", type=float, default=0.48)
    parser.add_argument("--min-area-cells", type=int, default=3)
    parser.add_argument("--max-area-cells", type=int, default=60)
    parser.add_argument("--dedupe-radius-m", type=float, default=0.5)
    parser.add_argument("--chunk-size", type=int, default=1_000_000)
    args = parser.parse_args()

    data_root = Path(args.data_root).resolve()
    aoi_path = Path(args.aoi).resolve()

    if not data_root.exists():
        raise SystemExit(f"Data root not found: {data_root}")
    if not aoi_path.exists():
        raise SystemExit(f"AOI not found: {aoi_path}")

    # Build parameter grid
    configs = []
    # Baseline (no watershed)
    configs.append({
        "name": "baseline",
        "apply_watershed": False,
        "h_maxima_h": 0.05,
        "min_split_area_cells": 12,
    })
    # Watershed configs
    for h in H_MAXIMA_VALUES:
        for msa in MIN_SPLIT_AREA_VALUES:
            configs.append({
                "name": f"ws_h{h:.2f}_msa{msa}",
                "apply_watershed": True,
                "h_maxima_h": h,
                "min_split_area_cells": msa,
            })

    print(f"Running {len(configs)} configurations ...", flush=True)

    results = []
    baseline_count = None

    for i, cfg in enumerate(configs):
        t0 = time.time()
        print(f"  [{i+1}/{len(configs)}] {cfg['name']} ...", end=" ", flush=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_json = Path(tmpdir) / "lidar_summary.json"

            _run_pipeline(
                data_root, tmp_json,
                cell_res=args.cell_res,
                hag_min=args.hag_min,
                hag_max=args.hag_max,
                min_area_cells=args.min_area_cells,
                max_area_cells=args.max_area_cells,
                chunk_size=args.chunk_size,
                crs_epsg=args.crs_epsg,
                dedupe_radius_m=args.dedupe_radius_m,
                apply_watershed=cfg["apply_watershed"],
                h_maxima_h=cfg["h_maxima_h"],
                min_split_area_cells=cfg["min_split_area_cells"],
            )

            summary = json.loads(tmp_json.read_text())
            total_count = summary.get("total_count", 0)
            aoi_count = _get_aoi_count(tmp_json, aoi_path, args.crs_epsg)

        dt = time.time() - t0

        if baseline_count is None:
            baseline_count = aoi_count

        row = {
            **cfg,
            "total_count": total_count,
            "aoi_count": aoi_count,
            "delta_vs_baseline": aoi_count - baseline_count if baseline_count is not None else None,
            "runtime_s": round(dt, 2),
        }
        if args.field_count is not None:
            row["delta_vs_field"] = aoi_count - args.field_count

        print(f"AOI={aoi_count}, total={total_count}, delta_baseline={row['delta_vs_baseline']}, "
              f"{dt:.1f}s", flush=True)
        results.append(row)

    output = {
        "data_root": str(data_root),
        "aoi": str(aoi_path),
        "crs_epsg": args.crs_epsg,
        "field_count": args.field_count,
        "cell_res": args.cell_res,
        "hag_range": [args.hag_min, args.hag_max],
        "area_range": [args.min_area_cells, args.max_area_cells],
        "dedupe_radius_m": args.dedupe_radius_m,
        "n_configs": len(configs),
        "results": results,
    }

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
