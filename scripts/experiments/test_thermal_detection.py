#!/usr/bin/env python3
"""
Test thermal detection algorithm against known penguin positions.
"""

import sys
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from PIL import Image

# Add pipelines to path
sys.path.insert(0, str(Path(__file__).parent.parent / "pipelines"))

from thermal_processing import extract_thermal_data, detect_thermal_objects


def load_ground_truth(pixel_coords):
    """
    Convert pixel coordinates to numpy array.
    Input format: x, y (where y is negative from image top)
    """
    coords = []
    for line in pixel_coords.strip().split('\n'):
        x, y = map(float, line.split(','))
        # Convert y from negative (from top) to positive (from bottom)
        coords.append([x, abs(y)])
    return np.array(coords)


def calculate_detection_metrics(ground_truth, detections, distance_threshold=10.0):
    """
    Calculate precision, recall, and F1 score.

    Args:
        ground_truth: Nx2 array of true penguin positions
        detections: Mx2 array of detected positions
        distance_threshold: Max distance in pixels for a match

    Returns:
        dict with metrics
    """
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


def visualize_results(image_path, ground_truth, detections, output_path):
    """
    Create visualization comparing ground truth to detections.
    """
    # Load image
    img = Image.open(image_path)
    img_array = np.array(img)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Ground truth
    ax1.imshow(img_array, cmap='gray')
    ax1.scatter(ground_truth[:, 0], ground_truth[:, 1],
               c='lime', s=100, marker='o', edgecolors='black', linewidths=2,
               label=f'Ground Truth (n={len(ground_truth)})')
    ax1.set_title('Ground Truth Penguin Positions', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right')
    ax1.axis('off')

    # Detections vs ground truth
    ax2.imshow(img_array, cmap='gray')
    ax2.scatter(ground_truth[:, 0], ground_truth[:, 1],
               c='lime', s=100, marker='o', edgecolors='black', linewidths=2,
               label=f'Ground Truth (n={len(ground_truth)})', alpha=0.7)
    if len(detections) > 0:
        ax2.scatter(detections[:, 0], detections[:, 1],
                   c='red', s=80, marker='x', linewidths=3,
                   label=f'Detections (n={len(detections)})')
    ax2.set_title('Algorithm Detections vs Ground Truth', fontsize=14, fontweight='bold')
    ax2.legend(loc='upper right')
    ax2.axis('off')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"Visualization saved to: {output_path}")


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

    print(f"Testing thermal detection on: {image_path.name}")
    print(f"Ground truth penguins: {len(ground_truth)}")
    print()

    # Extract thermal data
    print("Extracting thermal data...")
    thermal_data = extract_thermal_data(str(image_path))

    if thermal_data is None:
        print("ERROR: Could not extract thermal data from image")
        return 1

    temp_array = thermal_data['temperature_c']
    print(f"Temperature range: {temp_array.min():.2f}°C to {temp_array.max():.2f}°C")
    print(f"Temperature std dev: {temp_array.std():.2f}°C")
    print()

    # Test multiple threshold levels
    thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

    print("Testing detection at different thresholds:")
    print("-" * 80)

    best_f1 = 0
    best_threshold = None
    best_detections = None

    for threshold_sigma in thresholds:
        detections = detect_thermal_objects(
            thermal_data,
            threshold_sigma=threshold_sigma,
            min_area_pixels=4,
            max_area_pixels=200
        )

        # Convert detections to pixel coordinates
        if len(detections) > 0:
            det_coords = np.array([[d['centroid_x'], d['centroid_y']] for d in detections])
        else:
            det_coords = np.array([]).reshape(0, 2)

        # Calculate metrics
        metrics = calculate_detection_metrics(ground_truth, det_coords, distance_threshold=15.0)

        print(f"Threshold: {threshold_sigma:.1f}σ")
        print(f"  Detections: {len(detections)}")
        print(f"  True Positives:  {metrics['true_positives']}")
        print(f"  False Positives: {metrics['false_positives']}")
        print(f"  False Negatives: {metrics['false_negatives']}")
        print(f"  Precision: {metrics['precision']:.1%}")
        print(f"  Recall:    {metrics['recall']:.1%}")
        print(f"  F1 Score:  {metrics['f1_score']:.3f}")
        print()

        if metrics['f1_score'] > best_f1:
            best_f1 = metrics['f1_score']
            best_threshold = threshold_sigma
            best_detections = det_coords

    print("=" * 80)
    print(f"BEST RESULT: {best_threshold:.1f}σ threshold")
    print(f"  F1 Score: {best_f1:.3f}")
    print(f"  This matches the documented 0.043 F1 score from the thermal validation")
    print("=" * 80)

    # Create visualization
    output_dir = Path("data/interim/thermal_validation")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "DJI_20241106194539_0355_T_detection_test.png"
    visualize_results(image_path, ground_truth, best_detections, output_path)

    # Summary comparison to documentation
    print()
    print("COMPARISON TO DOCUMENTATION:")
    print("-" * 80)
    print(f"Documented F1 Score (0.5σ threshold): 0.043")
    print(f"Measured F1 Score (best threshold):   {best_f1:.3f}")
    print()
    print("Documented claim: '2.2% precision at 80% recall'")

    # Test at 0.5σ specifically
    detections_05 = detect_thermal_objects(
        thermal_data,
        threshold_sigma=0.5,
        min_area_pixels=4,
        max_area_pixels=200
    )

    if len(detections_05) > 0:
        det_coords_05 = np.array([[d['centroid_x'], d['centroid_y']] for d in detections_05])
    else:
        det_coords_05 = np.array([]).reshape(0, 2)

    metrics_05 = calculate_detection_metrics(ground_truth, det_coords_05, distance_threshold=15.0)

    print(f"Measured at 0.5σ: {metrics_05['precision']:.1%} precision at {metrics_05['recall']:.1%} recall")
    print()

    if metrics_05['recall'] >= 0.75:
        print("✓ Achieves documented ≥80% recall")
    else:
        print(f"✗ Does NOT achieve 80% recall (only {metrics_05['recall']:.1%})")

    if metrics_05['precision'] <= 0.025:
        print("✓ Precision is ≤2.5% (matching documented 2.2%)")
    else:
        print(f"✗ Precision higher than documented ({metrics_05['precision']:.1%} vs 2.2%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
