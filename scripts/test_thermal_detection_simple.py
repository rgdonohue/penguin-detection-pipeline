#!/usr/bin/env python3
"""
Test thermal detection algorithm against known penguin positions.
Uses simple threshold-based blob detection on radiometric thermal data.
"""

import sys
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from scipy import ndimage


def extract_thermal_data(image_path):
    """Extract 16-bit radiometric thermal data from DJI H20T image."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = Path(tmpdir) / "thermal.raw"

        # Extract ThermalData blob using exiftool
        cmd = ["exiftool", "-b", "-ThermalData", str(image_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, check=True)
            raw_path.write_bytes(result.stdout)
        except FileNotFoundError:
            print("ERROR: exiftool not found")
            print("Install via: brew install exiftool")
            return None
        except subprocess.CalledProcessError as e:
            print(f"ERROR: exiftool failed: {e.stderr.decode()}")
            return None

        # Load as 16-bit unsigned integers
        raw = np.fromfile(raw_path, dtype=np.uint16)

        expected_size = 640 * 512
        if len(raw) != expected_size:
            print(f"ERROR: Wrong data size: {len(raw)} (expected {expected_size})")
            return None

        # Reshape to image dimensions (height, width)
        img_raw = raw.reshape((512, 640))

        # DJI thermal conversion formula
        celsius = np.right_shift(img_raw, 2).astype(np.float32)
        celsius *= 0.0625  # = 1/16
        celsius -= 273.15   # Kelvin to Celsius

        return celsius


def detect_blobs(temp_array, threshold_sigma=0.5, min_area=4, max_area=200):
    """
    Simple blob detection using threshold + connected components.

    Args:
        temp_array: 2D array of temperatures
        threshold_sigma: Threshold in standard deviations above mean
        min_area: Minimum blob area in pixels
        max_area: Maximum blob area in pixels

    Returns:
        List of detections with centroids and areas
    """
    # Compute threshold
    mean_temp = np.mean(temp_array)
    std_temp = np.std(temp_array)
    threshold = mean_temp + (threshold_sigma * std_temp)

    # Create binary mask
    binary = temp_array > threshold

    # Label connected components
    labeled, num_features = ndimage.label(binary)

    # Extract blob properties
    detections = []
    for i in range(1, num_features + 1):
        blob = (labeled == i)
        area = np.sum(blob)

        if min_area <= area <= max_area:
            # Compute centroid
            coords = np.argwhere(blob)
            centroid_y = np.mean(coords[:, 0])
            centroid_x = np.mean(coords[:, 1])

            detections.append({
                'centroid_x': centroid_x,
                'centroid_y': centroid_y,
                'area': area
            })

    return detections


def load_ground_truth(pixel_coords):
    """Convert pixel coordinates to numpy array."""
    coords = []
    for line in pixel_coords.strip().split('\n'):
        x, y = map(float, line.split(','))
        # Convert y from negative (from top) to positive (from bottom)
        coords.append([x, abs(y)])
    return np.array(coords)


def calculate_metrics(ground_truth, detections, distance_threshold=15.0):
    """Calculate precision, recall, and F1 score."""
    if len(detections) == 0:
        return {
            'true_positives': 0,
            'false_positives': 0,
            'false_negatives': len(ground_truth),
            'precision': 0.0,
            'recall': 0.0,
            'f1_score': 0.0
        }

    # Find matches
    matched_gt = set()
    matched_det = set()

    for i, gt_pos in enumerate(ground_truth):
        for j, det_pos in enumerate(detections):
            if j in matched_det:
                continue
            dist = np.linalg.norm(gt_pos - det_pos)
            if dist <= distance_threshold:
                matched_gt.add(i)
                matched_det.add(j)
                break

    tp = len(matched_gt)
    fp = len(detections) - len(matched_det)
    fn = len(ground_truth) - len(matched_gt)

    precision = tp / len(detections) if len(detections) > 0 else 0.0
    recall = tp / len(ground_truth) if len(ground_truth) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        'true_positives': tp,
        'false_positives': fp,
        'false_negatives': fn,
        'precision': precision,
        'recall': recall,
        'f1_score': f1
    }


def visualize_results(temp_array, ground_truth, detections, metrics, threshold, output_path):
    """Create visualization."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # Temperature image
    ax = axes[0, 0]
    im = ax.imshow(temp_array, cmap='hot', origin='upper')
    ax.set_title('Thermal Image (Raw Temperature)', fontsize=12, fontweight='bold')
    plt.colorbar(im, ax=ax, label='Temperature (°C)')
    ax.axis('off')

    # Ground truth overlay
    ax = axes[0, 1]
    ax.imshow(temp_array, cmap='gray', origin='upper')
    ax.scatter(ground_truth[:, 0], ground_truth[:, 1],
              c='lime', s=120, marker='o', edgecolors='black', linewidths=2,
              label=f'Ground Truth (n={len(ground_truth)})', alpha=0.8)
    ax.set_title('Ground Truth Positions', fontsize=12, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.axis('off')

    # Detections vs ground truth
    ax = axes[1, 0]
    ax.imshow(temp_array, cmap='gray', origin='upper')
    ax.scatter(ground_truth[:, 0], ground_truth[:, 1],
              c='lime', s=120, marker='o', edgecolors='black', linewidths=2,
              label=f'Ground Truth (n={len(ground_truth)})', alpha=0.7)
    if len(detections) > 0:
        det_coords = np.array([[d['centroid_x'], d['centroid_y']] for d in detections])
        ax.scatter(det_coords[:, 0], det_coords[:, 1],
                  c='red', s=100, marker='x', linewidths=3,
                  label=f'Detections (n={len(detections)})')
    ax.set_title(f'Detections vs Ground Truth (σ={threshold})', fontsize=12, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.axis('off')

    # Metrics table
    ax = axes[1, 1]
    ax.axis('off')

    # Create metrics text
    metrics_text = f"""
DETECTION METRICS (σ={threshold})

True Positives:  {metrics['true_positives']}
False Positives: {metrics['false_positives']}
False Negatives: {metrics['false_negatives']}

Precision: {metrics['precision']:.1%}
Recall:    {metrics['recall']:.1%}
F1 Score:  {metrics['f1_score']:.3f}

DOCUMENTED VALUES:
F1 Score: 0.043 (at 0.5σ)
Precision: 2.2% at 80% recall
"""

    ax.text(0.1, 0.5, metrics_text, fontsize=14, family='monospace',
            verticalalignment='center', transform=ax.transAxes)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\nVisualization saved to: {output_path}")


def main():
    # Image path
    image_path = Path("data/legacy_ro/penguin-2.0/data/raw/thermal-images/"
                     "DJI_202411061712_006_Create-Area-Route5/"
                     "DJI_20241106194539_0355_T.JPG")

    # Ground truth positions
    gt_coords = """119.3, -402.3
199.4, -435.4
132.5, -323.6
176.6, -322.9
193.4, -161.9
289.1, -256.7
313.4, -257.6
317.1, -234.7
304.6, -223.6
339.9, -220.7
384.7, -287.6
567.0, -358.9
608.2, -279.5
592.0, -199.4
611.2, -188.4
539.8, -184.7
598.7, -156.7
617.8, -150.1
568.5, -92.8
546.5, -62.6
802.3, -101.6"""

    ground_truth = load_ground_truth(gt_coords)

    print("=" * 80)
    print("THERMAL DETECTION VALIDATION TEST")
    print("=" * 80)
    print(f"\nImage: {image_path.name}")
    print(f"Ground truth penguins: {len(ground_truth)}")

    # Extract thermal data
    print("\nExtracting thermal data...")
    temp_array = extract_thermal_data(image_path)

    if temp_array is None:
        return 1

    print(f"Temperature range: {temp_array.min():.2f}°C to {temp_array.max():.2f}°C")
    print(f"Temperature mean: {temp_array.mean():.2f}°C")
    print(f"Temperature std dev: {temp_array.std():.2f}°C")
    print(f"Image shape: {temp_array.shape}")

    # Test multiple threshold levels
    thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

    print("\n" + "=" * 80)
    print("TESTING DETECTION AT DIFFERENT THRESHOLDS")
    print("=" * 80)

    best_f1 = 0
    best_threshold = None
    best_detections = None
    best_metrics = None

    for threshold_sigma in thresholds:
        detections = detect_blobs(
            temp_array,
            threshold_sigma=threshold_sigma,
            min_area=4,
            max_area=200
        )

        # Convert to coordinate array
        if len(detections) > 0:
            det_coords = np.array([[d['centroid_x'], d['centroid_y']] for d in detections])
        else:
            det_coords = np.array([]).reshape(0, 2)

        # Calculate metrics
        metrics = calculate_metrics(ground_truth, det_coords, distance_threshold=15.0)

        print(f"\nThreshold: {threshold_sigma:.1f}σ")
        print(f"  Detections: {len(detections)}")
        print(f"  True Positives:  {metrics['true_positives']}")
        print(f"  False Positives: {metrics['false_positives']}")
        print(f"  False Negatives: {metrics['false_negatives']}")
        print(f"  Precision: {metrics['precision']:.1%}")
        print(f"  Recall:    {metrics['recall']:.1%}")
        print(f"  F1 Score:  {metrics['f1_score']:.3f}")

        if metrics['f1_score'] > best_f1:
            best_f1 = metrics['f1_score']
            best_threshold = threshold_sigma
            best_detections = detections
            best_metrics = metrics

    print("\n" + "=" * 80)
    print("BEST RESULT")
    print("=" * 80)
    print(f"Threshold: {best_threshold:.1f}σ")
    print(f"F1 Score: {best_f1:.3f}")
    print(f"Precision: {best_metrics['precision']:.1%}")
    print(f"Recall: {best_metrics['recall']:.1%}")

    print("\n" + "=" * 80)
    print("COMPARISON TO DOCUMENTATION")
    print("=" * 80)
    print(f"Documented F1 Score (0.5σ):     0.043")
    print(f"Measured F1 Score (best):        {best_f1:.3f}")
    print(f"Documented precision at 80%:     2.2%")

    # Test specifically at 0.5σ
    detections_05 = detect_blobs(temp_array, threshold_sigma=0.5, min_area=4, max_area=200)
    if len(detections_05) > 0:
        det_coords_05 = np.array([[d['centroid_x'], d['centroid_y']] for d in detections_05])
    else:
        det_coords_05 = np.array([]).reshape(0, 2)

    metrics_05 = calculate_metrics(ground_truth, det_coords_05, distance_threshold=15.0)

    print(f"Measured at 0.5σ:                {metrics_05['precision']:.1%} precision at {metrics_05['recall']:.1%} recall")
    print(f"Measured F1 at 0.5σ:             {metrics_05['f1_score']:.3f}")

    # Create visualization
    output_dir = Path("data/interim/thermal_validation")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "thermal_detection_validation.png"
    visualize_results(temp_array, ground_truth, best_detections, best_metrics, best_threshold, output_path)

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    if metrics_05['f1_score'] < 0.05:
        print("✓ Thermal detection performs VERY POORLY (F1 < 0.05)")
        print("✓ This confirms the documented findings")
        print("✓ 0.14°C contrast is insufficient for reliable detection")
        print("\nRECOMMENDATION: Use thermal for documentation only, not individual counting")
    else:
        print(f"? Thermal detection F1 score ({metrics_05['f1_score']:.3f}) differs from documentation")
        print("  This may indicate detection parameter differences")

    return 0


if __name__ == "__main__":
    sys.exit(main())
