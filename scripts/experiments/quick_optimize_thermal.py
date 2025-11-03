#!/usr/bin/env python3
"""
Quick thermal optimization - tests fewer parameters for faster results.
Based on known thermal characteristics from the investigation.
"""

import json
import sys
from pathlib import Path
import numpy as np
from scipy import ndimage
import csv

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))
from pipelines.thermal import extract_thermal_data

def detect_hotspots_simple(temps: np.ndarray, threshold_sigma: float) -> np.ndarray:
    """Simple threshold-based detection."""
    mean = np.mean(temps)
    std = np.std(temps)
    threshold = mean + (threshold_sigma * std)
    return temps > threshold

def cluster_detections(mask: np.ndarray, min_size: int = 2):
    """Extract centroids from binary mask."""
    labeled, num_features = ndimage.label(mask)
    detections = []
    for i in range(1, num_features + 1):
        component = (labeled == i)
        size = np.sum(component)
        if size >= min_size:
            y_coords, x_coords = np.where(component)
            detections.append((int(np.mean(x_coords)), int(np.mean(y_coords))))
    return detections

def load_ground_truth(csv_path):
    """Load ground truth locations."""
    locations = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            locations.append((int(row['x']), int(row['y'])))
    return locations

def calculate_f1(detections, ground_truth, radius=5):
    """Calculate F1 score for detections."""
    if not detections or not ground_truth:
        return 0.0, 0.0, 0.0

    # Simple matching within radius
    tp = 0
    for gt in ground_truth:
        for det in detections:
            dist = np.sqrt((gt[0]-det[0])**2 + (gt[1]-det[1])**2)
            if dist <= radius:
                tp += 1
                break

    fp = len(detections) - tp
    fn = len(ground_truth) - tp

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return precision, recall, f1

def main():
    print("Quick Thermal Optimization")
    print("=" * 50)

    # Paths
    thermal_dir = Path("data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5")
    gt_dir = Path("verification_images")

    # Test frames with known characteristics
    frames = [
        ("0353", "high contrast (10.5°C)"),
        ("0355", "moderate contrast (8.5°C)"),
        ("0356", "low contrast (0.14°C)")
    ]

    # Reduced parameter space - test what matters most
    thresholds = [1.0, 1.5, 2.0, 2.5, 3.0]  # Reduced from 8
    morphology_ops = ['none', 'open']  # Just test basic noise reduction
    min_clusters = [1, 2, 3]  # Pixel cluster sizes

    best_overall = {'f1': 0, 'params': None}
    results = []

    for frame_id, description in frames:
        print(f"\nProcessing frame {frame_id} - {description}")

        # Load data
        thermal_path = list(thermal_dir.glob(f"*_{frame_id}_T.JPG"))[0]
        gt_path = gt_dir / f"frame_{frame_id}_locations.csv"

        if not gt_path.exists():
            print(f"  Skipping - no ground truth")
            continue

        temps = extract_thermal_data(str(thermal_path))
        ground_truth = load_ground_truth(gt_path)

        best_frame = {'f1': 0, 'params': None}

        # Test parameters
        for threshold in thresholds:
            for morph in morphology_ops:
                for min_cluster in min_clusters:
                    # Detect
                    mask = detect_hotspots_simple(temps, threshold)

                    # Apply morphology
                    if morph == 'open':
                        mask = ndimage.binary_opening(mask, structure=np.ones((3,3)))

                    # Get detections
                    detections = cluster_detections(mask, min_cluster)

                    # Score
                    prec, rec, f1 = calculate_f1(detections, ground_truth)

                    if f1 > best_frame['f1']:
                        best_frame = {
                            'f1': f1,
                            'params': {
                                'threshold_sigma': threshold,
                                'morphology': morph,
                                'min_cluster_size': min_cluster
                            },
                            'precision': prec,
                            'recall': rec,
                            'detections': len(detections)
                        }

        results.append({
            'frame': frame_id,
            'description': description,
            'ground_truth': len(ground_truth),
            **best_frame
        })

        print(f"  Best: F1={best_frame['f1']:.3f}, "
              f"Precision={best_frame.get('precision', 0):.1%}, "
              f"Recall={best_frame.get('recall', 0):.1%}")

        if best_frame['f1'] > best_overall['f1']:
            best_overall = best_frame

    print("\n" + "=" * 50)
    print("OPTIMIZATION COMPLETE")
    print("=" * 50)

    # Save optimal parameters
    optimal_params = {
        'method': 'baseline',  # Simple threshold
        'threshold_sigma': best_overall['params']['threshold_sigma'],
        'morphology': best_overall['params']['morphology'],
        'min_cluster_size': best_overall['params']['min_cluster_size'],
        'avg_f1': best_overall['f1']
    }

    output_path = Path("data/interim/optimal_thermal_params.json")
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(optimal_params, f, indent=2)

    print(f"\nBest Parameters (F1={best_overall['f1']:.3f}):")
    print(f"  Threshold: {optimal_params['threshold_sigma']}σ")
    print(f"  Morphology: {optimal_params['morphology']}")
    print(f"  Min Cluster: {optimal_params['min_cluster_size']} pixels")
    print(f"\nSaved to: {output_path}")

    # Save summary
    summary_path = Path("data/interim/quick_optimization_summary.csv")
    with open(summary_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['frame', 'description', 'ground_truth',
                                               'f1', 'precision', 'recall', 'detections'])
        writer.writeheader()
        writer.writerows(results)

    print(f"Summary saved to: {summary_path}")

    print("\nNext step: Run batch detection with these parameters")
    print("python scripts/run_thermal_detection_batch.py \\")
    print("  --input data/legacy_ro/penguin-2.0/data/raw/thermal-images/ \\")
    print("  --params data/interim/optimal_thermal_params.json \\")
    print("  --output data/processed/thermal_detections/ \\")
    print("  --limit 100 --verbose  # Test first")

if __name__ == '__main__':
    main()