#!/usr/bin/env python3
"""
Validate LiDAR detections against a labeled subset (point labels).

Capabilities:
- Score an existing LiDAR summary JSON against labeled points using one-to-one
  within-radius matching (TP/FP/FN, precision/recall/F1).
- Optionally run a bounded parameter sweep by re-running scripts/run_lidar_hag.py
  and scoring each run on the same labeled subset.

This script is intentionally explicit about uncertainty:
- By default it uses only labels whose category contains "penguin".
- If labels are sparse or class-biased (for example, burrow-only labels), the
  metrics should be treated as subset QA, not colony-wide accuracy.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import itertools
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.spatial import cKDTree

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[1]
for _p in [str(_ROOT / "src"), str(_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pipelines.aoi_eval import _extract_aois, _extract_crs_code, _points_in_geometry  # noqa: E402


@dataclass(frozen=True)
class XYPoint:
    x: float
    y: float
    point_id: str
    category: str = ""


def _parse_float_list(raw: str) -> List[float]:
    vals: List[float] = []
    for token in (raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        vals.append(float(token))
    if not vals:
        raise ValueError(f"Expected comma-separated floats, got: {raw!r}")
    return vals


def _parse_int_list(raw: str) -> List[int]:
    vals: List[int] = []
    for token in (raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        vals.append(int(token))
    if not vals:
        raise ValueError(f"Expected comma-separated ints, got: {raw!r}")
    return vals


def _normalize_epsg(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if value.upper().startswith("EPSG:"):
        tail = value.split(":", 1)[1].strip()
        if tail.isdigit():
            return f"EPSG:{int(tail)}"
    if value.isdigit():
        return f"EPSG:{int(value)}"
    return value


def _extract_summary_crs(obj: Dict[str, Any]) -> Optional[str]:
    crs = _extract_crs_code(obj)
    return _normalize_epsg(crs) if crs else None


def _extract_lidar_detections(summary_obj: Dict[str, Any]) -> List[XYPoint]:
    detections: List[XYPoint] = []
    if isinstance(summary_obj.get("detections"), list):
        rows = summary_obj["detections"]
        for idx, det in enumerate(rows):
            if not isinstance(det, dict):
                continue
            if "x" not in det or "y" not in det:
                continue
            det_id = str(det.get("id") or det.get("tile_id") or f"det:{idx:06d}")
            detections.append(XYPoint(float(det["x"]), float(det["y"]), det_id))
        return detections

    files = summary_obj.get("files")
    if not isinstance(files, list):
        raise ValueError("Unsupported LiDAR summary format: expected detections[] or files[].")
    running_idx = 0
    for fi in files:
        if not isinstance(fi, dict):
            continue
        file_path = str(fi.get("path") or fi.get("file") or "")
        tile = Path(file_path).stem if file_path else "tile"
        for det in fi.get("detections", []) or []:
            if not isinstance(det, dict):
                continue
            if "x" not in det or "y" not in det:
                continue
            det_id = str(det.get("id") or f"{tile}:{running_idx:06d}")
            detections.append(XYPoint(float(det["x"]), float(det["y"]), det_id))
            running_idx += 1
    return detections


def _load_labels(path: Path) -> Tuple[List[XYPoint], Optional[str]]:
    suffix = path.suffix.lower()
    if suffix in {".geojson", ".json"}:
        obj = json.loads(path.read_text())
        crs = _extract_summary_crs(obj)
        feats = obj.get("features")
        if not isinstance(feats, list):
            raise ValueError(f"GeoJSON missing features list: {path}")
        labels: List[XYPoint] = []
        for i, feat in enumerate(feats):
            if not isinstance(feat, dict):
                continue
            geom = feat.get("geometry") if isinstance(feat.get("geometry"), dict) else {}
            if geom.get("type") != "Point":
                continue
            coords = geom.get("coordinates")
            if not isinstance(coords, list) or len(coords) < 2:
                continue
            props = feat.get("properties") if isinstance(feat.get("properties"), dict) else {}
            category = str(
                props.get("type")
                or props.get("category")
                or props.get("label")
                or ""
            )
            point_id = str(props.get("id") or props.get("point_id") or f"label:{i:06d}")
            labels.append(XYPoint(float(coords[0]), float(coords[1]), point_id, category))
        return labels, crs

    if suffix != ".csv":
        raise ValueError(f"Unsupported label format: {path}")

    labels = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        x_key = None
        y_key = None
        for cand in ("utm_x", "easting", "x"):
            if cand in fields:
                x_key = cand
                break
        for cand in ("utm_y", "northing", "y"):
            if cand in fields:
                y_key = cand
                break
        if x_key is None or y_key is None:
            raise ValueError(
                f"CSV labels require x/y columns. Found: {sorted(fields)}"
            )
        for i, row in enumerate(reader):
            try:
                x = float(row[x_key])
                y = float(row[y_key])
            except (TypeError, ValueError):
                continue
            category = str(
                row.get("type")
                or row.get("category")
                or row.get("label")
                or ""
            )
            point_id = str(
                row.get("id")
                or row.get("point_id")
                or row.get("image")
                or f"label:{i:06d}"
            )
            labels.append(XYPoint(x=x, y=y, point_id=point_id, category=category))
    # CSV has no standard CRS object; caller should pass --labels-crs-epsg if needed.
    return labels, None


def _filter_penguin_labels(labels: Sequence[XYPoint], include_non_penguin: bool) -> List[XYPoint]:
    if include_non_penguin:
        return list(labels)
    out: List[XYPoint] = []
    for pt in labels:
        if "penguin" in (pt.category or "").lower():
            out.append(pt)
    return out


def _transform_points(points: Sequence[XYPoint], src_crs: str, dst_crs: str) -> List[XYPoint]:
    src = _normalize_epsg(src_crs)
    dst = _normalize_epsg(dst_crs)
    if src is None or dst is None:
        raise ValueError(f"Cannot transform without CRS: src={src_crs!r} dst={dst_crs!r}")
    if src == dst:
        return list(points)
    try:
        import pyproj
    except ImportError as exc:
        raise RuntimeError("pyproj is required for CRS transformation") from exc

    transformer = pyproj.Transformer.from_crs(src, dst, always_xy=True)
    transformed: List[XYPoint] = []
    for pt in points:
        x, y = transformer.transform(pt.x, pt.y)
        transformed.append(XYPoint(float(x), float(y), pt.point_id, pt.category))
    return transformed


def _transform_geojson_xy(obj: Dict[str, Any], src_crs: str, dst_crs: str) -> Dict[str, Any]:
    src = _normalize_epsg(src_crs)
    dst = _normalize_epsg(dst_crs)
    if src is None or dst is None:
        raise ValueError(f"Cannot transform AOI without CRS: src={src_crs!r} dst={dst_crs!r}")
    if src == dst:
        return obj
    try:
        import pyproj
    except ImportError as exc:
        raise RuntimeError("pyproj is required for AOI CRS transformation") from exc

    transformer = pyproj.Transformer.from_crs(src, dst, always_xy=True)

    def tx_ring(ring: Sequence[Sequence[float]]) -> List[List[float]]:
        out: List[List[float]] = []
        for xy in ring:
            if not isinstance(xy, (list, tuple)) or len(xy) < 2:
                continue
            x, y = transformer.transform(float(xy[0]), float(xy[1]))
            out.append([float(x), float(y)])
        return out

    cloned = json.loads(json.dumps(obj))
    if cloned.get("type") != "FeatureCollection":
        raise ValueError("AOI input must be a FeatureCollection")
    for feat in cloned.get("features", []) or []:
        if not isinstance(feat, dict):
            continue
        geom = feat.get("geometry") if isinstance(feat.get("geometry"), dict) else {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype == "Polygon" and isinstance(coords, list):
            geom["coordinates"] = [tx_ring(r) for r in coords]
        elif gtype == "MultiPolygon" and isinstance(coords, list):
            geom["coordinates"] = [[tx_ring(r) for r in poly] for poly in coords]
    cloned["crs"] = {"type": "name", "properties": {"name": dst}}
    return cloned


def _filter_points_to_aoi(points: Sequence[XYPoint], aoi_obj: Dict[str, Any]) -> List[XYPoint]:
    if not points:
        return []
    aois = _extract_aois(aoi_obj)
    coords = np.asarray([[p.x, p.y] for p in points], dtype=np.float64)
    inside = np.zeros((coords.shape[0],), dtype=bool)
    for aoi in aois:
        inside |= _points_in_geometry(coords, aoi["geometry"])
    return [pt for pt, keep in zip(points, inside) if bool(keep)]


def _match_one_to_one(
    detections: Sequence[XYPoint],
    labels: Sequence[XYPoint],
    radius_m: float,
) -> List[Tuple[int, int, float]]:
    """Return matched (label_index, detection_index, distance_m) tuples."""
    if not detections or not labels:
        return []
    det_xy = np.asarray([[d.x, d.y] for d in detections], dtype=np.float64)
    lbl_xy = np.asarray([[lp.x, lp.y] for lp in labels], dtype=np.float64)
    tree = cKDTree(det_xy)

    pairs: List[Tuple[float, int, int]] = []
    for li, xy in enumerate(lbl_xy):
        candidate_idxs = tree.query_ball_point(xy, r=float(radius_m))
        for di in candidate_idxs:
            dist = float(np.hypot(*(xy - det_xy[di])))
            pairs.append((dist, li, int(di)))
    pairs.sort(key=lambda t: t[0])

    matched_labels: set[int] = set()
    matched_dets: set[int] = set()
    matches: List[Tuple[int, int, float]] = []
    for dist, li, di in pairs:
        if li in matched_labels or di in matched_dets:
            continue
        matched_labels.add(li)
        matched_dets.add(di)
        matches.append((li, di, dist))
    return matches


def _metrics_from_matches(
    detections: Sequence[XYPoint],
    labels: Sequence[XYPoint],
    matches: Sequence[Tuple[int, int, float]],
    radius_m: float,
) -> Dict[str, Any]:
    tp = int(len(matches))
    fp = int(len(detections) - tp)
    fn = int(len(labels) - tp)
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else None
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else None
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2.0 * precision * recall / (precision + recall)
    dists = [m[2] for m in matches]
    return {
        "radius_m": float(radius_m),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "match_dist_median": float(np.median(dists)) if dists else None,
        "match_dist_max": float(np.max(dists)) if dists else None,
    }


def _evaluate(
    *,
    detections: Sequence[XYPoint],
    labels: Sequence[XYPoint],
    radii_m: Sequence[float],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for radius_m in radii_m:
        matches = _match_one_to_one(detections, labels, radius_m=float(radius_m))
        rows.append(
            _metrics_from_matches(
                detections=detections, labels=labels, matches=matches, radius_m=float(radius_m)
            )
        )
    return rows


def _metrics_summary_table(metrics_by_radius: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for m in metrics_by_radius:
        rows.append(
            {
                "radius_m": float(m["radius_m"]),
                "tp": int(m["tp"]),
                "fp": int(m["fp"]),
                "fn": int(m["fn"]),
                "precision": m["precision"],
                "recall": m["recall"],
                "f1": m["f1"],
            }
        )
    return rows


def _radius_sensitivity_note(metrics_by_radius: Sequence[Dict[str, Any]]) -> str:
    if not metrics_by_radius:
        return "No metrics available."
    f1_rows = [m for m in metrics_by_radius if m.get("f1") is not None]
    if len(f1_rows) < 2:
        return "Insufficient radii with valid F1 to assess radius sensitivity."
    f1_values = [float(m["f1"]) for m in f1_rows]
    min_f1 = min(f1_values)
    max_f1 = max(f1_values)
    radius_min = float(min(float(m["radius_m"]) for m in f1_rows))
    radius_max = float(max(float(m["radius_m"]) for m in f1_rows))
    return (
        f"Matching radius sensitivity (subset QA): F1 ranges from {min_f1:.3f} to {max_f1:.3f} "
        f"across {radius_min:.2f}m-{radius_max:.2f}m."
    )


def _run_lidar_once(
    *,
    data_root: Path,
    out_path: Path,
    cell_res: float,
    hag_min: float,
    hag_max: float,
    min_area_cells: int,
    max_area_cells: int,
    ground_method: str,
    top_method: str,
    crs_epsg: Optional[int],
    dedupe_radius_m: Optional[float],
    skip_copc: bool,
    extra_args: Sequence[str],
) -> Tuple[int, str, str]:
    cmd = [
        sys.executable,
        str(_ROOT / "scripts" / "run_lidar_hag.py"),
        "--data-root",
        str(data_root),
        "--out",
        str(out_path),
        "--cell-res",
        str(cell_res),
        "--hag-min",
        str(hag_min),
        "--hag-max",
        str(hag_max),
        "--min-area-cells",
        str(min_area_cells),
        "--max-area-cells",
        str(max_area_cells),
        "--ground-method",
        str(ground_method),
        "--top-method",
        str(top_method),
        "--strict-outputs",
    ]
    if crs_epsg is not None:
        cmd.extend(["--crs-epsg", str(int(crs_epsg))])
    if dedupe_radius_m is not None:
        cmd.extend(["--dedupe-radius-m", str(float(dedupe_radius_m))])
    if skip_copc:
        cmd.append("--skip-copc")
    cmd.extend(list(extra_args))

    run = subprocess.run(cmd, capture_output=True, text=True)
    return run.returncode, run.stdout.strip(), run.stderr.strip()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Validate LiDAR detections against labeled point subset."
    )
    ap.add_argument("--lidar-summary", type=Path, default=None, help="Existing LiDAR summary JSON to score.")
    ap.add_argument("--labels", type=Path, required=True, help="Label points (.geojson/.json/.csv).")
    ap.add_argument("--labels-crs-epsg", type=int, default=None, help="CRS EPSG for CSV labels (if absent in file).")
    ap.add_argument("--target-crs-epsg", type=int, default=None, help="Force both detections and labels into this CRS before matching.")
    ap.add_argument("--aoi-geojson", type=Path, default=None, help="Optional AOI polygon(s) to clip detections+labels before scoring.")
    ap.add_argument("--aoi-crs-epsg", type=int, default=None, help="Optional AOI CRS EPSG override (used before clipping).")
    ap.add_argument("--radii-m", default="1.0,1.5,2.0", help="Comma-separated match radii in meters.")
    ap.add_argument("--include-non-penguin-labels", action="store_true", help="Include labels not containing 'penguin' in category/type.")
    ap.add_argument("--out", type=Path, required=True, help="Output JSON report path.")

    # Optional sweep mode
    ap.add_argument("--sweep-data-root", type=Path, default=None, help="If set, run LiDAR sweep on this data root and score each run.")
    ap.add_argument("--sweep-out-dir", type=Path, default=None, help="Directory for sweep run outputs.")
    ap.add_argument("--cell-res", type=float, default=0.25, help="Sweep: cell resolution.")
    ap.add_argument("--sweep-hag-mins", default="0.20,0.24,0.28", help="Sweep: comma-separated hag_min values.")
    ap.add_argument("--sweep-hag-maxs", default="0.48,0.56", help="Sweep: comma-separated hag_max values.")
    ap.add_argument("--sweep-min-areas", default="2,3", help="Sweep: comma-separated min_area_cells values.")
    ap.add_argument("--sweep-max-areas", default="50,80", help="Sweep: comma-separated max_area_cells values.")
    ap.add_argument("--sweep-ground-method", default="p05", choices=["min", "p05", "csf"], help="Sweep: ground method.")
    ap.add_argument("--sweep-top-method", default="max", choices=["max", "p95", "p95-online", "p95-exact"], help="Sweep: top method.")
    ap.add_argument("--sweep-crs-epsg", type=int, default=None, help="Sweep: pass through to LiDAR CLI for output CRS metadata.")
    ap.add_argument("--sweep-dedupe-radius-m", type=float, default=None, help="Sweep: optional dedupe radius passed to LiDAR CLI.")
    ap.add_argument("--sweep-skip-copc", action="store_true", help="Sweep: pass --skip-copc to LiDAR CLI.")
    ap.add_argument("--primary-radius-m", type=float, default=2.0, help="Sweep ranking radius (must be in --radii-m).")
    ap.add_argument("--sweep-extra-arg", action="append", default=[], help="Sweep: extra raw CLI args forwarded to run_lidar_hag.py.")

    args = ap.parse_args()
    radii_m = _parse_float_list(args.radii_m)
    if float(args.primary_radius_m) not in radii_m:
        raise SystemExit(
            f"--primary-radius-m={args.primary_radius_m} must be included in --radii-m={radii_m}"
        )

    labels_raw, labels_crs_from_file = _load_labels(args.labels)
    labels_filtered = _filter_penguin_labels(
        labels_raw, include_non_penguin=bool(args.include_non_penguin_labels)
    )

    labels_crs = (
        f"EPSG:{int(args.labels_crs_epsg)}"
        if args.labels_crs_epsg is not None
        else labels_crs_from_file
    )
    if labels_crs is None and args.target_crs_epsg is None:
        raise SystemExit(
            "Label CRS is unknown. Provide --labels-crs-epsg for CSV labels or --target-crs-epsg."
        )

    report: Dict[str, Any] = {
        "schema_version": "1",
        "purpose": "lidar_labeled_subset_validation",
        "generated_at_utc": dt.datetime.utcnow().isoformat() + "Z",
        "inputs": {
            "labels": str(args.labels),
            "lidar_summary": str(args.lidar_summary) if args.lidar_summary else None,
            "aoi_geojson": str(args.aoi_geojson) if args.aoi_geojson else None,
        },
        "labels": {
            "total_points": len(labels_raw),
            "points_used": len(labels_filtered),
            "filter": "category contains 'penguin'" if not args.include_non_penguin_labels else "all labels",
            "crs": labels_crs,
        },
        "radii_m": radii_m,
        "notes": [
            "Subset QA only: this is not site-wide accuracy and not a full census.",
            "Metrics are subset QA unless labels represent exhaustive ground truth.",
            "Default filter excludes non-penguin labels (for example Empty Burrow).",
            "Review matching radius sensitivity before comparing parameter sets.",
        ],
    }

    target_crs = (
        f"EPSG:{int(args.target_crs_epsg)}"
        if args.target_crs_epsg is not None
        else labels_crs
    )
    assert target_crs is not None
    aoi_obj_transformed: Optional[Dict[str, Any]] = None
    if args.aoi_geojson is not None:
        raw = json.loads(args.aoi_geojson.read_text())
        aoi_crs = (
            f"EPSG:{int(args.aoi_crs_epsg)}"
            if args.aoi_crs_epsg is not None
            else _extract_summary_crs(raw)
        )
        if aoi_crs is not None and aoi_crs != target_crs:
            raw = _transform_geojson_xy(raw, aoi_crs, target_crs)
        aoi_obj_transformed = raw

    def evaluate_summary(summary_path: Path) -> Dict[str, Any]:
        summary_obj = json.loads(summary_path.read_text())
        summary_crs = _extract_summary_crs(summary_obj)
        dets = _extract_lidar_detections(summary_obj)
        labels_eval = list(labels_filtered)

        if summary_crs and target_crs and summary_crs != target_crs:
            dets = _transform_points(dets, summary_crs, target_crs)
        if labels_crs and target_crs and labels_crs != target_crs:
            labels_eval = _transform_points(labels_eval, labels_crs, target_crs)

        if aoi_obj_transformed is not None:
            dets = _filter_points_to_aoi(dets, aoi_obj_transformed)
            labels_eval = _filter_points_to_aoi(labels_eval, aoi_obj_transformed)

        rows = _evaluate(detections=dets, labels=labels_eval, radii_m=radii_m)
        return {
            "summary_path": str(summary_path),
            "summary_crs": summary_crs,
            "target_crs": target_crs,
            "detections_used": len(dets),
            "labels_used": len(labels_eval),
            "metrics_by_radius": rows,
            "metrics_summary_table": _metrics_summary_table(rows),
            "radius_sensitivity_note": _radius_sensitivity_note(rows),
        }

    if args.lidar_summary is not None:
        report["evaluation"] = evaluate_summary(args.lidar_summary)

    if args.sweep_data_root is not None:
        if args.sweep_out_dir is None:
            raise SystemExit("--sweep-out-dir is required when --sweep-data-root is provided.")
        sweep_dir = args.sweep_out_dir
        run_dir = sweep_dir / "runs"
        run_dir.mkdir(parents=True, exist_ok=True)

        combos: List[Tuple[float, float, int, int]] = []
        for hag_min, hag_max, min_area, max_area in itertools.product(
            _parse_float_list(args.sweep_hag_mins),
            _parse_float_list(args.sweep_hag_maxs),
            _parse_int_list(args.sweep_min_areas),
            _parse_int_list(args.sweep_max_areas),
        ):
            if hag_min >= hag_max:
                continue
            if min_area >= max_area:
                continue
            combos.append((hag_min, hag_max, min_area, max_area))

        sweep_rows: List[Dict[str, Any]] = []
        for idx, (hag_min, hag_max, min_area, max_area) in enumerate(combos):
            out_json = run_dir / f"run_{idx:03d}.json"
            rc, stdout, stderr = _run_lidar_once(
                data_root=args.sweep_data_root,
                out_path=out_json,
                cell_res=float(args.cell_res),
                hag_min=float(hag_min),
                hag_max=float(hag_max),
                min_area_cells=int(min_area),
                max_area_cells=int(max_area),
                ground_method=str(args.sweep_ground_method),
                top_method=str(args.sweep_top_method),
                crs_epsg=args.sweep_crs_epsg,
                dedupe_radius_m=args.sweep_dedupe_radius_m,
                skip_copc=bool(args.sweep_skip_copc),
                extra_args=args.sweep_extra_arg,
            )
            row: Dict[str, Any] = {
                "run_id": idx,
                "hag_min": float(hag_min),
                "hag_max": float(hag_max),
                "min_area_cells": int(min_area),
                "max_area_cells": int(max_area),
                "summary_path": str(out_json),
                "return_code": int(rc),
            }
            if rc != 0:
                row["error"] = stderr or stdout or "unknown LiDAR CLI failure"
                sweep_rows.append(row)
                continue

            eval_obj = evaluate_summary(out_json)
            by_radius = {
                float(m["radius_m"]): m for m in eval_obj["metrics_by_radius"]
            }
            primary = by_radius.get(float(args.primary_radius_m))
            if primary is None:
                row["error"] = "primary radius metrics missing"
                sweep_rows.append(row)
                continue

            row.update(
                {
                    "detections_used": int(eval_obj["detections_used"]),
                    "labels_used": int(eval_obj["labels_used"]),
                    "tp": int(primary["tp"]),
                    "fp": int(primary["fp"]),
                    "fn": int(primary["fn"]),
                    "precision": primary["precision"],
                    "recall": primary["recall"],
                    "f1": primary["f1"],
                    "metrics_by_radius": eval_obj["metrics_by_radius"],
                }
            )
            sweep_rows.append(row)

        # Rank successful runs by F1 (desc), then recall, then precision.
        successful = [r for r in sweep_rows if "error" not in r]
        successful.sort(
            key=lambda r: (
                -float(r.get("f1") or -1),
                -float(r.get("recall") or -1),
                -float(r.get("precision") or -1),
            )
        )

        csv_path = sweep_dir / "sweep_metrics.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "run_id",
                "hag_min",
                "hag_max",
                "min_area_cells",
                "max_area_cells",
                "summary_path",
                "return_code",
                "detections_used",
                "labels_used",
                "tp",
                "fp",
                "fn",
                "precision",
                "recall",
                "f1",
                "error",
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for row in sweep_rows:
                w.writerow({k: row.get(k) for k in fieldnames})

        report["sweep"] = {
            "data_root": str(args.sweep_data_root),
            "sweep_out_dir": str(sweep_dir),
            "n_runs": len(sweep_rows),
            "n_success": len(successful),
            "primary_radius_m": float(args.primary_radius_m),
            "csv": str(csv_path),
            "top_runs": successful[:10],
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(str(args.out))


if __name__ == "__main__":
    main()
