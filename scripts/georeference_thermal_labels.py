#!/usr/bin/env python3
"""
Georeference thermal penguin labels using homography from box corner correspondences.

Each thermal image has 4 labeled box corners (pixels) that correspond to the same
4 GPS box corners. We compute a homography to transform pixel coordinates to UTM.

The challenge: matching which pixel corner corresponds to which GPS corner.
We use camera orientation (yaw) and oblique geometry to determine correspondence.

Usage:
    python scripts/georeference_thermal_labels.py

Output:
    data/processed/labels_penguins_georef.csv
    data/processed/labels_penguins_georef.geojson
"""

import csv
import json
from pathlib import Path
from dataclasses import dataclass
import numpy as np
from pyproj import Transformer

PROJECT_ROOT = Path(__file__).parent.parent

# Box corners from GPS (WGS84) - these define the ground truth box
# Order: NW, SW, SE, NE (counter-clockwise from top-left)
BOX_CORNERS_WGS84 = [
    (-42.085258, -63.867123, 'NW'),
    (-42.085381, -63.867161, 'SW'),
    (-42.085392, -63.866972, 'SE'),
    (-42.085273, -63.866958, 'NE'),
]

# Image metadata (from EXIF)
IMAGE_METADATA = {
    'DJI_20251109011148_0076_T.JPG': {
        'camera_lat': -42.085278,
        'camera_lon': -63.866494,
        'yaw': -88.4,  # Facing West
        'pitch': -45.0,
    },
    'DJI_20251109011246_0116_T.JPG': {
        'camera_lat': -42.085725,
        'camera_lon': -63.867011,
        'yaw': 1.4,  # Facing North
        'pitch': -45.0,
    },
    'DJI_20251109011345_0158_T.JPG': {
        'camera_lat': -42.085361,
        'camera_lon': -63.867550,
        'yaw': 89.5,  # Facing East
        'pitch': -45.0,
    },
    'DJI_20251109011445_0197_T.JPG': {
        'camera_lat': -42.084906,
        'camera_lon': -63.867094,
        'yaw': -179.3,  # Facing South
        'pitch': -45.0,
    },
}


def load_labels(csv_path: Path) -> dict:
    """Load labels from CSV, grouped by image."""
    by_image = {}

    with open(csv_path) as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) < 5:
                continue

            label_type = parts[0].strip()
            x, y = int(parts[1]), int(parts[2])
            image = parts[3]

            if image not in by_image:
                by_image[image] = {'box_corners': [], 'labels': []}

            if 'Box Corner' in label_type:
                by_image[image]['box_corners'].append((x, y))
            else:
                by_image[image]['labels'].append({
                    'type': label_type,
                    'x': x,
                    'y': y,
                })

    return by_image


def corners_wgs84_to_utm(corners_wgs84: list) -> dict:
    """Convert GPS corners to UTM, returning dict by label."""
    transformer = Transformer.from_crs('EPSG:4326', 'EPSG:32720', always_xy=True)

    corners_utm = {}
    for lat, lon, label in corners_wgs84:
        x, y = transformer.transform(lon, lat)
        corners_utm[label] = (x, y)

    return corners_utm


def order_pixel_corners_by_camera_view(pixel_corners: list, camera_yaw: float) -> list:
    """
    Order pixel corners to match NW, SW, SE, NE based on camera viewing direction.

    For oblique imagery at -45° pitch:
    - Corners farther from camera appear higher in image (smaller Y)
    - Corners closer to camera appear lower in image (larger Y)
    - Left/right in image depends on camera yaw

    Returns corners ordered as [NW, SW, SE, NE].
    """
    corners = np.array(pixel_corners)

    # Normalize yaw to [0, 360)
    yaw = camera_yaw % 360

    # Sort by Y coordinate (top to bottom)
    y_sorted_idx = np.argsort(corners[:, 1])

    # Top 2 corners (far from camera) and bottom 2 (near camera)
    far_corners = corners[y_sorted_idx[:2]]
    near_corners = corners[y_sorted_idx[2:]]

    # Sort each pair by X (left to right in image)
    far_corners = far_corners[np.argsort(far_corners[:, 0])]
    near_corners = near_corners[np.argsort(near_corners[:, 0])]

    # Map image left/right to world NW/SW/SE/NE based on camera direction
    # Camera facing West (yaw ~ -90 or 270): far = West corners, image left = South
    # Camera facing North (yaw ~ 0): far = North corners, image left = West
    # Camera facing East (yaw ~ 90): far = East corners, image left = North
    # Camera facing South (yaw ~ 180): far = South corners, image left = East

    if 225 <= yaw < 315 or -135 <= camera_yaw < -45:  # Facing West
        # Far corners are West (NW, SW), near are East (NE, SE)
        # Image left = South, image right = North
        # far_corners sorted by X: [SW, NW] (South is left/lower X in image when facing West)
        # Actually need to think about this more carefully...
        # When facing West, South is to the left in the image
        nw = tuple(far_corners[1])   # far, right in image
        sw = tuple(far_corners[0])   # far, left in image
        ne = tuple(near_corners[1])  # near, right in image
        se = tuple(near_corners[0])  # near, left in image

    elif 315 <= yaw < 360 or 0 <= yaw < 45 or -45 <= camera_yaw < 45:  # Facing North
        # Far corners are North (NW, NE), near are South (SW, SE)
        # Image left = West, image right = East
        nw = tuple(far_corners[0])   # far, left
        ne = tuple(far_corners[1])   # far, right
        sw = tuple(near_corners[0])  # near, left
        se = tuple(near_corners[1])  # near, right

    elif 45 <= yaw < 135:  # Facing East
        # Far corners are East (NE, SE), near are West (NW, SW)
        # Image left = North, image right = South
        ne = tuple(far_corners[0])   # far, left
        se = tuple(far_corners[1])   # far, right
        nw = tuple(near_corners[0])  # near, left
        sw = tuple(near_corners[1])  # near, right

    else:  # 135 <= yaw < 225: Facing South
        # Far corners are South (SW, SE), near are North (NW, NE)
        # Image left = East, image right = West
        se = tuple(far_corners[0])   # far, left
        sw = tuple(far_corners[1])   # far, right
        ne = tuple(near_corners[0])  # near, left
        nw = tuple(near_corners[1])  # near, right

    return [nw, sw, se, ne]


def compute_homography(src_points: np.ndarray, dst_points: np.ndarray) -> np.ndarray:
    """
    Compute homography matrix from source to destination points.

    Uses Direct Linear Transform (DLT) algorithm.
    """
    assert src_points.shape == dst_points.shape == (4, 2)

    # Build the DLT matrix
    A = []
    for i in range(4):
        x, y = src_points[i]
        u, v = dst_points[i]
        A.append([-x, -y, -1, 0, 0, 0, x*u, y*u, u])
        A.append([0, 0, 0, -x, -y, -1, x*v, y*v, v])

    A = np.array(A)

    # Solve using SVD
    _, _, Vt = np.linalg.svd(A)
    H = Vt[-1].reshape(3, 3)

    return H / H[2, 2]  # Normalize


def apply_homography(H: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Apply homography to transform points."""
    if points.ndim == 1:
        points = points.reshape(1, -1)

    # Convert to homogeneous coordinates
    ones = np.ones((points.shape[0], 1))
    points_h = np.hstack([points, ones])

    # Apply homography
    transformed_h = (H @ points_h.T).T

    # Convert back from homogeneous
    transformed = transformed_h[:, :2] / transformed_h[:, 2:3]

    return transformed


def main():
    print("=" * 70)
    print("GEOREFERENCING THERMAL PENGUIN LABELS")
    print("=" * 70)

    # Load labels
    labels_path = PROJECT_ROOT / "data/2025/labels_penguins_2025-12-03-04-07-18.csv"
    labels_by_image = load_labels(labels_path)

    print(f"\nLoaded labels from {labels_path.name}")
    for img, data in labels_by_image.items():
        print(f"  {img}: {len(data['box_corners'])} corners, {len(data['labels'])} labels")

    # Convert box corners to UTM
    corners_utm = corners_wgs84_to_utm(BOX_CORNERS_WGS84)
    print(f"\nBox corners (UTM EPSG:32720):")
    for label, (x, y) in corners_utm.items():
        print(f"  {label}: ({x:.2f}, {y:.2f})")

    # Process each image
    all_georef_labels = []

    for image_name, data in labels_by_image.items():
        print(f"\n{'='*60}")
        print(f"Processing {image_name}")
        print(f"{'='*60}")

        if image_name not in IMAGE_METADATA:
            print(f"  WARNING: No metadata for {image_name}, skipping")
            continue

        meta = IMAGE_METADATA[image_name]
        pixel_corners = data['box_corners']

        if len(pixel_corners) != 4:
            print(f"  WARNING: Expected 4 corners, got {len(pixel_corners)}, skipping")
            continue

        print(f"  Camera yaw: {meta['yaw']:.1f}°")
        print(f"  Pixel corners (raw): {pixel_corners}")

        # Order pixel corners to match NW, SW, SE, NE
        ordered_pixels = order_pixel_corners_by_camera_view(pixel_corners, meta['yaw'])
        print(f"  Ordered pixels [NW, SW, SE, NE]: {ordered_pixels}")

        # Build source (pixel) and destination (UTM) point arrays
        src_points = np.array(ordered_pixels, dtype=float)
        dst_points = np.array([
            corners_utm['NW'],
            corners_utm['SW'],
            corners_utm['SE'],
            corners_utm['NE'],
        ], dtype=float)

        # Compute homography
        H = compute_homography(src_points, dst_points)

        # Verify by transforming corners back
        transformed_corners = apply_homography(H, src_points)
        errors = np.linalg.norm(transformed_corners - dst_points, axis=1)
        print(f"  Homography corner errors: {errors.round(2)} m (should be ~0)")

        if np.max(errors) > 1.0:
            print(f"  WARNING: Large homography error, corner ordering may be wrong")

        # Transform all labels
        for label in data['labels']:
            pixel = np.array([[label['x'], label['y']]], dtype=float)
            utm = apply_homography(H, pixel)[0]

            georef_label = {
                'image': image_name,
                'type': label['type'],
                'pixel_x': label['x'],
                'pixel_y': label['y'],
                'utm_x': float(utm[0]),
                'utm_y': float(utm[1]),
                'crs': 'EPSG:32720',
            }
            all_georef_labels.append(georef_label)

        print(f"  Georeferenced {len(data['labels'])} labels")

    # Save results
    output_dir = PROJECT_ROOT / "data/processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    # CSV output
    csv_path = output_dir / "labels_penguins_georef.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['image', 'type', 'pixel_x', 'pixel_y', 'utm_x', 'utm_y', 'crs'])
        writer.writeheader()
        writer.writerows(all_georef_labels)
    print(f"\nSaved CSV: {csv_path}")

    # GeoJSON output
    features = []
    for label in all_georef_labels:
        feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [label['utm_x'], label['utm_y']],
            },
            'properties': {
                'image': label['image'],
                'type': label['type'],
                'pixel_x': label['pixel_x'],
                'pixel_y': label['pixel_y'],
            },
        }
        features.append(feature)

    geojson = {
        'type': 'FeatureCollection',
        'crs': {
            'type': 'name',
            'properties': {'name': 'EPSG:32720'},
        },
        'features': features,
    }

    geojson_path = output_dir / "labels_penguins_georef.geojson"
    with open(geojson_path, 'w') as f:
        json.dump(geojson, f, indent=2)
    print(f"Saved GeoJSON: {geojson_path}")

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total labels georeferenced: {len(all_georef_labels)}")

    # Count by type
    by_type = {}
    for label in all_georef_labels:
        t = label['type']
        by_type[t] = by_type.get(t, 0) + 1

    for t, count in sorted(by_type.items()):
        print(f"  {t}: {count}")

    # Bounding box
    xs = [l['utm_x'] for l in all_georef_labels]
    ys = [l['utm_y'] for l in all_georef_labels]
    print(f"\nBounding box (UTM):")
    print(f"  X: [{min(xs):.2f}, {max(xs):.2f}] ({max(xs)-min(xs):.1f} m)")
    print(f"  Y: [{min(ys):.2f}, {max(ys):.2f}] ({max(ys)-min(ys):.1f} m)")


if __name__ == "__main__":
    main()
