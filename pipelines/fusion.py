"""
Fusion stage (thermal + LiDAR reconciliation).

This module performs a spatial join between LiDAR and thermal detections once
both are expressed in the same projected CRS (meters).  It deliberately does
not attempt to georeference thermal pixel detections; upstream code should
produce thermal detections with ``x``/``y`` coordinates in the target CRS.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.spatial import cKDTree


@dataclass
class FusionParams:
    """Inputs and outputs required to produce the fusion rollup."""

    lidar_summary: Path
    thermal_summary: Path
    out_path: Path
    match_radius_m: float = 0.5
    qc_panel: Optional[Path] = None


def run(params: FusionParams) -> Path:
    """Fuse detections from LiDAR and thermal summaries and write a rollup JSON."""

    lidar_obj = _load_json(params.lidar_summary)
    thermal_obj = _load_json(params.thermal_summary)

    lidar_dets = _extract_detections(lidar_obj, source="lidar")
    thermal_dets = _extract_detections(thermal_obj, source="thermal")

    out = _join_detections(
        lidar_dets=lidar_dets,
        thermal_dets=thermal_dets,
        match_radius_m=float(params.match_radius_m),
    )

    params.out_path.parent.mkdir(parents=True, exist_ok=True)
    params.out_path.write_text(json.dumps(out, indent=2))
    return params.out_path


def _load_json(path: Path) -> Dict[str, Any]:
    if not Path(path).exists():
        raise FileNotFoundError(f"Missing summary JSON: {path}")
    return json.loads(Path(path).read_text())


def _extract_detections(summary: Dict[str, Any], source: str) -> List[Dict[str, Any]]:
    dets: List[Dict[str, Any]] = []

    if isinstance(summary.get("detections"), list):
        for det in summary["detections"]:
            dets.append({**det, "_source": source})
        return dets

    files = summary.get("files")
    if not isinstance(files, list):
        raise ValueError(f"Unsupported {source} summary format (missing detections/files)")

    for file_entry in files:
        file_path = file_entry.get("path") or file_entry.get("file") or file_entry.get("source")
        for det in file_entry.get("detections", []) or []:
            dets.append({**det, "_source": source, "_file": file_path})

    return dets


def _xy_from_dets(dets: List[Dict[str, Any]]) -> Tuple[np.ndarray, List[int]]:
    coords: List[Tuple[float, float]] = []
    idxs: List[int] = []
    for i, det in enumerate(dets):
        if "x" not in det or "y" not in det:
            continue
        coords.append((float(det["x"]), float(det["y"])))
        idxs.append(i)
    if not coords:
        return np.zeros((0, 2), dtype=np.float64), []
    return np.asarray(coords, dtype=np.float64), idxs


def _join_detections(
    *,
    lidar_dets: List[Dict[str, Any]],
    thermal_dets: List[Dict[str, Any]],
    match_radius_m: float,
) -> Dict[str, Any]:
    lidar_xy, lidar_idxs = _xy_from_dets(lidar_dets)
    thermal_xy, thermal_idxs = _xy_from_dets(thermal_dets)

    lidar_matches: List[Optional[int]] = [None] * len(lidar_dets)
    lidar_match_dist_m: List[Optional[float]] = [None] * len(lidar_dets)
    thermal_matched: List[bool] = [False] * len(thermal_dets)

    if lidar_xy.size and thermal_xy.size:
        tree = cKDTree(thermal_xy)
        dists, nn = tree.query(lidar_xy, k=1, distance_upper_bound=float(match_radius_m))
        for local_i, (dist, nn_local) in enumerate(zip(dists, nn)):
            global_lidar_i = lidar_idxs[local_i]
            if not np.isfinite(dist):
                continue
            if nn_local >= len(thermal_idxs):
                continue
            global_thermal_i = thermal_idxs[int(nn_local)]
            lidar_matches[global_lidar_i] = global_thermal_i
            lidar_match_dist_m[global_lidar_i] = float(dist)
            thermal_matched[global_thermal_i] = True

    lidar_matched_count = sum(1 for m in lidar_matches if m is not None)
    thermal_matched_count = sum(1 for m in thermal_matched if m)

    return {
        "match_radius_m": float(match_radius_m),
        "lidar_count": len(lidar_dets),
        "thermal_count": len(thermal_dets),
        "lidar_matched_count": int(lidar_matched_count),
        "thermal_matched_count": int(thermal_matched_count),
        "lidar_only_count": int(len(lidar_dets) - lidar_matched_count),
        "thermal_only_count": int(len(thermal_dets) - thermal_matched_count),
        "lidar": [
            {
                **det,
                "match_thermal_index": lidar_matches[i],
                "match_dist_m": lidar_match_dist_m[i],
                "label": "both" if lidar_matches[i] is not None else "lidar_only",
            }
            for i, det in enumerate(lidar_dets)
        ],
        "thermal": [
            {
                **det,
                "matched_by_lidar": bool(thermal_matched[i]),
                "label": "both" if thermal_matched[i] else "thermal_only",
            }
            for i, det in enumerate(thermal_dets)
        ],
    }

    raise NotImplementedError(
        "Fusion stage not yet modularised. Use `make fusion` while the pipeline "
        "implementation is migrated into pipelines/fusion.py."
    )
