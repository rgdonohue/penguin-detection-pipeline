#!/usr/bin/env python3
"""
Cross-reference Lydia Box2 client labels to LiDAR detections.

This script does two things:
1) Diagnose screenshot-to-raw mapping confidence (image-based, non-destructive).
2) Run a coarse spatial cross-reference using RTK frame centers and estimated
   nadir thermal footprints.

Why coarse? The current package does not include the exact raw frame IDs cited
in the PDF annotation pages (for example *_0064_T). Without a trustworthy
pixel-to-raw transform for the labeled screenshot, per-label georeferencing is
not reliable. We therefore report center/footprint-level spatial overlap as a
defensible interim metric.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from pyproj import Transformer
from skimage.metrics import structural_similarity as ssim


@dataclass(frozen=True)
class FrameMeta:
    path: Path
    width: int
    height: int
    gps_lat: float
    gps_lon: float
    rel_alt_m: float
    gimbal_yaw_deg: float
    fov_deg: float


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_label_counts(labels_meta_csv: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    with labels_meta_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = (row.get("label") or "").strip()
            if label:
                counts[label] += 1
    return dict(counts)


def _extract_exif_frame_meta(image_path: Path) -> FrameMeta:
    out = subprocess.check_output(
        ["exiftool", "-n", "-json", str(image_path)],
        text=True,
    )
    d = json.loads(out)[0]
    return FrameMeta(
        path=image_path,
        width=int(d["ImageWidth"]),
        height=int(d["ImageHeight"]),
        gps_lat=float(d["GPSLatitude"]),
        gps_lon=float(d["GPSLongitude"]),
        rel_alt_m=float(d.get("RelativeAltitude", 0.0)),
        gimbal_yaw_deg=float(d.get("GimbalYawDegree", 0.0)),
        fov_deg=float(d.get("FOV", 38.19)),
    )


def _infer_detection_crs(dets_xy: np.ndarray) -> str:
    # Heuristic: POSGAR-style eastings are in the millions, UTM are ~hundreds of thousands.
    x_med = float(np.median(dets_xy[:, 0]))
    if x_med > 1_000_000:
        return "EPSG:5345"
    return "EPSG:32720"


def _frame_footprint_dims_m(width_px: int, height_px: int, rel_alt_m: float, fov_h_deg: float) -> tuple[float, float]:
    fov_v_deg = math.degrees(2.0 * math.atan(math.tan(math.radians(fov_h_deg / 2.0)) * (height_px / width_px)))
    fw = 2.0 * rel_alt_m * math.tan(math.radians(fov_h_deg / 2.0))
    fh = 2.0 * rel_alt_m * math.tan(math.radians(fov_v_deg / 2.0))
    return fw, fh


def _count_in_rotated_rect(
    points_xy: np.ndarray,
    center_x: float,
    center_y: float,
    width_m: float,
    height_m: float,
    yaw_deg: float,
) -> int:
    dx = points_xy[:, 0] - center_x
    dy = points_xy[:, 1] - center_y
    th = math.radians(yaw_deg)
    # Rotate into camera-aligned local frame.
    u = dx * math.cos(th) + dy * math.sin(th)
    v = -dx * math.sin(th) + dy * math.cos(th)
    inside = (np.abs(u) <= (width_m / 2.0)) & (np.abs(v) <= (height_m / 2.0))
    return int(np.count_nonzero(inside))


def _pair_embedded_to_raw_by_ssim(embedded: dict[str, Path], raw: dict[str, Path]) -> list[dict[str, Any]]:
    emb_img = {k: np.array(Image.open(p).convert("L"), dtype=np.float32) for k, p in embedded.items()}
    raw_img = {k: np.array(Image.open(p).convert("L"), dtype=np.float32) for k, p in raw.items()}

    rows: list[dict[str, Any]] = []
    for ek, ei in emb_img.items():
        scores: list[dict[str, Any]] = []
        eiz = (ei - ei.mean()) / (ei.std() + 1e-6)
        for rk, ri in raw_img.items():
            riz = (ri - ri.mean()) / (ri.std() + 1e-6)
            val = float(ssim(eiz, riz, data_range=8.0))
            scores.append({"raw_key": rk, "score_ssim": val})
        scores.sort(key=lambda x: x["score_ssim"], reverse=True)
        rows.append(
            {
                "embedded_key": ek,
                "best_raw_key": scores[0]["raw_key"],
                "best_score_ssim": scores[0]["score_ssim"],
                "all_scores_desc": scores,
            }
        )
    return rows


def _ensure_embedded_frames(pdf_path: Path, embedded_dir: Path) -> dict[str, Path]:
    embedded_dir.mkdir(parents=True, exist_ok=True)
    expected = {
        "out000": embedded_dir / "out-000.jpg",
        "out001": embedded_dir / "out-001.jpg",
        "out002": embedded_dir / "out-002.jpg",
        "out003": embedded_dir / "out-003.jpg",
        "out008": embedded_dir / "out-008.jpg",
    }
    if all(p.exists() for p in expected.values()):
        return expected

    # Extract all embedded image objects from PDF (jpg/png, ordered by object index).
    prefix = embedded_dir / "out"
    subprocess.check_call(["pdfimages", "-all", str(pdf_path), str(prefix)])
    if not all(p.exists() for p in expected.values()):
        missing = [str(p) for p in expected.values() if not p.exists()]
        raise RuntimeError(
            "Failed to extract expected embedded frames from PDF. Missing: "
            + ", ".join(missing)
        )
    return expected


def run(args: argparse.Namespace) -> dict[str, Any]:
    labels_counts = _load_label_counts(args.labels_meta_csv)

    # LiDAR detections
    lidar_obj = _read_json(args.lidar_summary_json)
    dets = lidar_obj.get("detections")
    if not isinstance(dets, list) or not dets:
        raise RuntimeError(f"No detections[] found in {args.lidar_summary_json}")
    det_xy = np.asarray([[float(d["x"]), float(d["y"])] for d in dets], dtype=np.float64)
    det_crs = _infer_detection_crs(det_xy)

    # Frame metadata
    frames = [_extract_exif_frame_meta(Path(p)) for p in args.raw_thermal_images]
    ll_to_det = Transformer.from_crs("EPSG:4326", det_crs, always_xy=True)

    frame_rows: list[dict[str, Any]] = []
    centers_det_xy: list[tuple[float, float]] = []
    for fm in frames:
        cx, cy = ll_to_det.transform(fm.gps_lon, fm.gps_lat)
        centers_det_xy.append((float(cx), float(cy)))
        fw, fh = _frame_footprint_dims_m(
            width_px=fm.width,
            height_px=fm.height,
            rel_alt_m=fm.rel_alt_m,
            fov_h_deg=fm.fov_deg,
        )
        n_inside = _count_in_rotated_rect(
            points_xy=det_xy,
            center_x=float(cx),
            center_y=float(cy),
            width_m=float(fw),
            height_m=float(fh),
            yaw_deg=float(fm.gimbal_yaw_deg),
        )

        d = np.hypot(det_xy[:, 0] - float(cx), det_xy[:, 1] - float(cy))
        frame_rows.append(
            {
                "image": str(fm.path),
                "center_detection_crs_xy": [float(cx), float(cy)],
                "relative_altitude_m": float(fm.rel_alt_m),
                "gimbal_yaw_deg": float(fm.gimbal_yaw_deg),
                "fov_horizontal_deg": float(fm.fov_deg),
                "estimated_footprint_m": {"width": float(fw), "height": float(fh)},
                "detections_in_estimated_footprint": int(n_inside),
                "nearest_detection_m": float(np.min(d)),
                "nearest_5_detections_m": [float(x) for x in np.sort(d)[:5]],
            }
        )

    # Union distance diagnostics
    centers = np.asarray(centers_det_xy, dtype=np.float64)
    min_dist_any = np.min(
        np.hypot(det_xy[:, None, 0] - centers[None, :, 0], det_xy[:, None, 1] - centers[None, :, 1]),
        axis=1,
    )
    radius_counts = {str(r): int(np.count_nonzero(min_dist_any <= float(r))) for r in args.center_radii_m}

    # Screenshot/raw mapping diagnostics
    embedded = _ensure_embedded_frames(pdf_path=args.pdf, embedded_dir=args.embedded_dir)
    raw_map = {
        "t0028": Path(args.raw_thermal_images[0]),
        "t0047": Path(args.raw_thermal_images[1]),
        "t0063": Path(args.raw_thermal_images[2]),
    }
    mapping_diag = _pair_embedded_to_raw_by_ssim(embedded=embedded, raw=raw_map)

    return {
        "schema_version": 1,
        "method": "coarse_spatial_cross_reference",
        "notes": [
            "Per-label georeferencing is unresolved because screenshot->raw frame registration is low-confidence.",
            "PDF references raw IDs not present in folder (e.g., *_0064_T); only embedded JPGs are available from PDF.",
            "Spatial results below are center/footprint-level diagnostics using RTK frame centers and estimated nadir footprints.",
        ],
        "inputs": {
            "labels_meta_csv": str(args.labels_meta_csv),
            "lidar_summary_json": str(args.lidar_summary_json),
            "raw_thermal_images": list(args.raw_thermal_images),
        },
        "labels": {
            "class_counts": labels_counts,
            "total_points": int(sum(labels_counts.values())),
        },
        "lidar": {
            "detections_total": int(det_xy.shape[0]),
            "inferred_crs": det_crs,
        },
        "mapping_diagnostics": mapping_diag,
        "frame_center_crossref": frame_rows,
        "detections_within_radius_of_any_frame_center": {
            "counts": radius_counts,
            "min_distance_any_detection_to_any_center_m": float(np.min(min_dist_any)),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--labels-meta-csv",
        type=Path,
        default=Path("data/interim/lydia_box2/labels_extracted_meta.csv"),
    )
    ap.add_argument(
        "--pdf",
        type=Path,
        default=Path("new-to-process/images_box2/lydia_drawing.pdf"),
    )
    ap.add_argument(
        "--embedded-dir",
        type=Path,
        default=Path("data/interim/lydia_box2/pdf_embedded_frames"),
        help="Directory where embedded PDF frames (out-000...out-008) are stored.",
    )
    ap.add_argument(
        "--lidar-summary-json",
        type=Path,
        default=Path("data/interim/san_lorenzo_box_enriched.json"),
    )
    ap.add_argument(
        "--raw-thermal-images",
        nargs=3,
        default=[
            "new-to-process/images_box2/DJI_20251111001840_0028_T.JPG",
            "new-to-process/images_box2/DJI_20251111001903_0047_T.JPG",
            "new-to-process/images_box2/DJI_20251111001922_0063_T.JPG",
        ],
        help="Three delivered raw thermal images from images_box2.",
    )
    ap.add_argument(
        "--center-radii-m",
        nargs="+",
        type=float,
        default=[20, 30, 40, 50, 75, 100],
    )
    ap.add_argument(
        "--out-json",
        type=Path,
        default=Path("data/interim/lydia_box2/spatial_crossref_report.json"),
    )
    args = ap.parse_args()

    report = run(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    with args.out_json.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote: {args.out_json}")
    print(f"Labels total: {report['labels']['total_points']}")
    print(f"LiDAR detections: {report['lidar']['detections_total']} ({report['lidar']['inferred_crs']})")


if __name__ == "__main__":
    main()
