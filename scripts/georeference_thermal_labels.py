#!/usr/bin/env python3
"""
Georeference thermal penguin labels using box corner GCPs and homography.

Each thermal image has 4 labeled "Box Corner" pixels corresponding to known GPS
positions. We use the camera model for corner correspondence, compute a per-image
homography (pixel→UTM), project all labels, then cluster across 4 views to get
unique physical locations.

Usage:
    python scripts/georeference_thermal_labels.py \
        --labels-csv data/2025/thermal-penguin-labels/labels_my-project-name_2025-12-03-04-07-18.csv \
        --image-dir data/2025/thermal-penguin-labels \
        --out-json data/processed/thermal_labels_georef.json
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
for p in [str(_ROOT / "src"), str(_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from pyproj import Transformer

# ── Known box corners (WGS84: lat, lon) ────────────────────────────
BUSHES_BOX_CORNERS_WGS84 = {
    "NW": (-42.085258, -63.867123),
    "NE": (-42.085273, -63.866958),
    "SE": (-42.085392, -63.866972),
    "SW": (-42.085381, -63.867161),
}
CORNER_ORDER = ["NW", "NE", "SE", "SW"]

# ── Corner matching (geometric heuristic for oblique views) ────────

def _order_corners_by_view(pixel_corners: List[Tuple[int, int]], yaw_deg: float) -> Dict[str, Tuple[int, int]]:
    """
    Match pixel corners to compass labels (NW/NE/SE/SW) using oblique view geometry.

    At -45° pitch:
    - Far objects (further from camera) appear HIGHER in image (smaller Y)
    - Near objects appear LOWER (larger Y)
    - Left/right depends on camera yaw

    Returns dict mapping corner name → pixel (x, y).
    """
    corners = np.array(pixel_corners)

    # Split into far (upper image, small Y) and near (lower image, large Y)
    y_order = np.argsort(corners[:, 1])
    far = corners[y_order[:2]]   # top 2 in image
    near = corners[y_order[2:]]  # bottom 2 in image

    # Sort each pair by X (left to right in image)
    far = far[np.argsort(far[:, 0])]
    near = near[np.argsort(near[:, 0])]

    yaw = yaw_deg % 360

    # Camera yaw determines which compass directions are far/near and left/right.
    # At yaw=0 (North): camera right = East.
    # At yaw=90 (East): camera right = South.
    # At yaw=-90/270 (West): camera right = North.
    # At yaw=180 (South): camera right = West.

    if 225 <= yaw < 315 or (yaw_deg < 0 and -135 <= yaw_deg < -45):
        # Facing West: far=West side, near=East side; left=South, right=North
        return {"SW": tuple(far[0]), "NW": tuple(far[1]),
                "SE": tuple(near[0]), "NE": tuple(near[1])}

    elif yaw < 45 or yaw >= 315 or (-45 <= yaw_deg < 45):
        # Facing North: far=North side, near=South side; left=West, right=East
        return {"NW": tuple(far[0]), "NE": tuple(far[1]),
                "SW": tuple(near[0]), "SE": tuple(near[1])}

    elif 45 <= yaw < 135:
        # Facing East: far=East side, near=West side; left=North, right=South
        return {"NE": tuple(far[0]), "SE": tuple(far[1]),
                "NW": tuple(near[0]), "SW": tuple(near[1])}

    else:
        # Facing South: far=South side, near=North side; left=East, right=West
        return {"SE": tuple(far[0]), "SW": tuple(far[1]),
                "NE": tuple(near[0]), "NW": tuple(near[1])}


# ── Homography (normalized DLT) ────────────────────────────────────

def _compute_homography(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """
    Compute homography H: dst ~ H @ src (homogeneous coords).

    Uses normalized DLT for numerical stability with large UTM coordinates.
    """
    N = src.shape[0]

    def _norm_matrix(pts):
        mu = pts.mean(axis=0)
        sd = pts.std(axis=0)
        sd = np.where(sd < 1e-10, 1.0, sd)
        return np.array([
            [1 / sd[0], 0, -mu[0] / sd[0]],
            [0, 1 / sd[1], -mu[1] / sd[1]],
            [0, 0, 1],
        ])

    Ts = _norm_matrix(src)
    Td = _norm_matrix(dst)

    src_h = np.column_stack([src, np.ones(N)])
    dst_h = np.column_stack([dst, np.ones(N)])
    sn = (Ts @ src_h.T).T
    dn = (Td @ dst_h.T).T

    A = []
    for i in range(N):
        x, y, w = sn[i]
        u, v, _ = dn[i]
        A.append([-x, -y, -w, 0, 0, 0, u * x, u * y, u * w])
        A.append([0, 0, 0, -x, -y, -w, v * x, v * y, v * w])
    _, _, Vt = np.linalg.svd(np.array(A))
    H_norm = Vt[-1].reshape(3, 3)

    # Denormalize
    H = np.linalg.inv(Td) @ H_norm @ Ts
    H /= H[2, 2]
    return H


def _apply_homography(H: np.ndarray, pixels: np.ndarray) -> np.ndarray:
    """Apply H to (N,2) pixel coords → (N,2) ground coords."""
    N = pixels.shape[0]
    ph = np.column_stack([pixels, np.ones(N)])
    rh = (H @ ph.T).T
    return rh[:, :2] / rh[:, 2:3]


# ── EXIF / Labels I/O ──────────────────────────────────────────────

def _extract_exif(img_path: Path) -> dict:
    """Extract GPS and gimbal from DJI thermal image via exiftool."""
    r = subprocess.run(
        ["exiftool", "-n", "-json", str(img_path)],
        capture_output=True, text=True, timeout=10,
    )
    d = json.loads(r.stdout)[0]
    return {
        "lat": float(d["GPSLatitude"]),
        "lon": float(d["GPSLongitude"]),
        "alt_abs": float(d["AbsoluteAltitude"]),
        "alt_rel": float(d["RelativeAltitude"]),
        "gimbal_yaw": float(d["GimbalYawDegree"]),
        "gimbal_pitch": float(d["GimbalPitchDegree"]),
        "gimbal_roll": float(d["GimbalRollDegree"]),
    }


def _parse_labels(csv_path: Path) -> Dict[str, List[dict]]:
    """Parse labels CSV, group by image filename."""
    by_image: Dict[str, List[dict]] = defaultdict(list)
    with open(csv_path) as f:
        for row in csv.reader(f):
            if len(row) < 6:
                continue
            by_image[row[3].strip()].append({
                "label": row[0].strip(),
                "px": int(row[1]),
                "py": int(row[2]),
            })
    return dict(by_image)


# ── Multi-view clustering ──────────────────────────────────────────

def _cluster_positions(positions: List[dict], radius_m: float) -> List[dict]:
    """Cluster projected positions from multiple views into unique locations."""
    if not positions:
        return []

    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import pdist

    coords = np.array([[p["easting"], p["northing"]] for p in positions])

    if len(coords) == 1:
        return [{
            "easting": coords[0, 0], "northing": coords[0, 1],
            "label": positions[0]["label"], "n_views": 1, "spread_m": 0.0,
        }]

    D = pdist(coords)
    if D.max() < 1e-6:
        return [{
            "easting": coords[0, 0], "northing": coords[0, 1],
            "label": positions[0]["label"], "n_views": len(positions), "spread_m": 0.0,
        }]

    Z = linkage(D, method="complete")
    cids = fcluster(Z, t=radius_m, criterion="distance")

    clusters = []
    for cid in sorted(set(cids)):
        mask = cids == cid
        members = [p for p, m in zip(positions, mask) if m]
        cc = coords[mask]
        centroid = cc.mean(axis=0)

        label_counts: Dict[str, int] = defaultdict(int)
        for m in members:
            label_counts[m["label"]] += 1
        best_label = max(label_counts, key=label_counts.get)

        spread = float(np.max(pdist(cc))) if len(cc) > 1 else 0.0

        clusters.append({
            "easting": float(centroid[0]),
            "northing": float(centroid[1]),
            "label": best_label,
            "n_views": int(mask.sum()),
            "spread_m": round(spread, 3),
            "label_breakdown": dict(label_counts),
        })

    return clusters


# ── Main ────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Georeference thermal penguin labels.")
    ap.add_argument("--labels-csv", required=True)
    ap.add_argument("--image-dir", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--cluster-radius", type=float, default=2.0)
    ap.add_argument("--crs-epsg", type=int, default=32720)
    args = ap.parse_args()

    labels_csv = Path(args.labels_csv)
    image_dir = Path(args.image_dir)
    out_json = Path(args.out_json)

    wgs84_to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{args.crs_epsg}", always_xy=True)
    utm_to_wgs84 = Transformer.from_crs(f"EPSG:{args.crs_epsg}", "EPSG:4326", always_xy=True)

    # Box corners → UTM
    corners_utm = {}
    for name, (lat, lon) in BUSHES_BOX_CORNERS_WGS84.items():
        e, n = wgs84_to_utm.transform(lon, lat)
        corners_utm[name] = (e, n)

    print("Box corners (UTM):")
    for name in CORNER_ORDER:
        e, n = corners_utm[name]
        print(f"  {name}: ({e:.2f}, {n:.2f})")

    labels_by_image = _parse_labels(labels_csv)
    print(f"\nLabels loaded: {sum(len(v) for v in labels_by_image.values())} across {len(labels_by_image)} images")

    all_projected = []
    image_results = []

    for filename in sorted(labels_by_image.keys()):
        labels = labels_by_image[filename]
        print(f"\n{'='*60}")
        print(f"Image: {filename}")

        img_path = image_dir / filename
        if not img_path.exists():
            print(f"  WARNING: not found, skipping")
            continue

        exif = _extract_exif(img_path)
        print(f"  GPS: ({exif['lat']:.7f}, {exif['lon']:.7f})  alt={exif['alt_abs']:.1f}m MSL ({exif['alt_rel']:.1f}m AGL)")
        print(f"  Gimbal: yaw={exif['gimbal_yaw']:.1f}° pitch={exif['gimbal_pitch']:.1f}° roll={exif['gimbal_roll']:.1f}°")

        # Labeled "Box Corner" pixels
        corner_labels = [l for l in labels if l["label"] == "Box Corner"]
        if len(corner_labels) != 4:
            print(f"  WARNING: expected 4 box corners, got {len(corner_labels)}, skipping")
            continue

        pixel_corners = [(l["px"], l["py"]) for l in corner_labels]

        # Match pixel corners to compass labels using oblique view geometry
        matched = _order_corners_by_view(pixel_corners, exif["gimbal_yaw"])
        print(f"  Corner matching (geometric heuristic, yaw={exif['gimbal_yaw']:.1f}°):")
        for name in CORNER_ORDER:
            print(f"    {name} → pixel {matched[name]}")

        # Compute homography: pixel → UTM
        src_pts = np.array([matched[c] for c in CORNER_ORDER], dtype=float)
        dst_pts = np.array([list(corners_utm[c]) for c in CORNER_ORDER], dtype=float)
        H = _compute_homography(src_pts, dst_pts)

        # Validate homography: reproject corners and check errors
        reproj = _apply_homography(H, src_pts)
        reproj_errors = np.sqrt(np.sum((reproj - dst_pts) ** 2, axis=1))
        print(f"  Homography reprojection errors:")
        for i, name in enumerate(CORNER_ORDER):
            print(f"    {name}: {reproj_errors[i]:.6f}m")
        print(f"  Max reproj error: {reproj_errors.max():.6f}m  (should be ≈0)")

        if reproj_errors.max() > 0.01:
            print(f"  WARNING: homography reprojection error unexpectedly large")

        # Project all non-corner labels through homography
        non_corners = [l for l in labels if l["label"] != "Box Corner"]
        if non_corners:
            nc_px = np.array([[l["px"], l["py"]] for l in non_corners], dtype=float)
            nc_utm = _apply_homography(H, nc_px)

            for i, l in enumerate(non_corners):
                lon_out, lat_out = utm_to_wgs84.transform(nc_utm[i, 0], nc_utm[i, 1])
                all_projected.append({
                    "label": l["label"],
                    "easting": float(nc_utm[i, 0]),
                    "northing": float(nc_utm[i, 1]),
                    "lat": float(lat_out),
                    "lon": float(lon_out),
                    "source_image": filename,
                    "pixel_x": l["px"],
                    "pixel_y": l["py"],
                })

            print(f"  Projected {len(non_corners)} labels to UTM")

        cam_e, cam_n = wgs84_to_utm.transform(exif["lon"], exif["lat"])
        image_results.append({
            "filename": filename,
            "exif": exif,
            "camera_utm": {"easting": cam_e, "northing": cam_n, "alt_msl": exif["alt_abs"]},
            "corner_matching": {name: [int(matched[name][0]), int(matched[name][1])] for name in CORNER_ORDER},
            "homography_reproj_error_m": round(float(reproj_errors.max()), 6),
            "n_labels_projected": len(non_corners),
        })

    # ── Multi-view clustering ───────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"MULTI-VIEW CLUSTERING")
    print(f"  {len(all_projected)} projections, cluster radius={args.cluster_radius}m")

    by_category: Dict[str, List[dict]] = defaultdict(list)
    for p in all_projected:
        by_category[p["label"]].append(p)

    all_clusters = []
    for cat in sorted(by_category.keys()):
        positions = by_category[cat]
        clusters = _cluster_positions(positions, radius_m=args.cluster_radius)
        for c in clusters:
            c["category"] = cat
        all_clusters.extend(clusters)
        print(f"  {cat}: {len(positions)} projections → {len(clusters)} unique locations")

    # ── Summary ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    cat_counts = defaultdict(int)
    for c in all_clusters:
        cat_counts[c["category"]] += 1
    total_penguins = cat_counts.get("Penguin in Burrow", 0) + cat_counts.get("Penguin Deep in Burrow", 0)
    for cat, count in sorted(cat_counts.items()):
        print(f"  {cat}: {count} unique locations")
    print(f"  Total penguins: {total_penguins}")
    print(f"  Total unique locations: {len(all_clusters)}")

    if all_clusters:
        spreads = [c["spread_m"] for c in all_clusters if c["n_views"] > 1]
        views = [c["n_views"] for c in all_clusters]
        print(f"  Mean views per location: {np.mean(views):.1f}")
        if spreads:
            print(f"  Multi-view spread: mean={np.mean(spreads):.2f}m  max={np.max(spreads):.2f}m  median={np.median(spreads):.2f}m")

    # ── Write output ────────────────────────────────────────────────
    output = {
        "source_csv": str(labels_csv),
        "crs_epsg": args.crs_epsg,
        "method": "homography_from_box_corner_GCPs",
        "cluster_radius_m": args.cluster_radius,
        "box_corners_utm": {k: list(v) for k, v in corners_utm.items()},
        "images": image_results,
        "all_projected": all_projected,
        "unique_locations": all_clusters,
        "summary": {
            "n_images": len(image_results),
            "n_projected": len(all_projected),
            "n_unique": len(all_clusters),
            "n_penguins": total_penguins,
            "by_category": dict(cat_counts),
        },
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(output, indent=2))
    print(f"\nOutput: {out_json}")


if __name__ == "__main__":
    main()
