#!/usr/bin/env python3
"""
Optimize thermal detection parameters using ground truth data.

This script performs a parameter sweep across different detection methods
and thresholds to find optimal settings for penguin detection in thermal imagery.
"""

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
from scipy import ndimage
from scipy.spatial.distance import cdist
import sys

# Add parent directory to path for pipeline imports
sys.path.append(str(Path(__file__).parent.parent))
from pipelines.thermal import extract_thermal_data


def load_ground_truth(csv_path: Path) -> List[Tuple[int, int]]:
    """Load ground truth penguin locations from CSV."""
    locations = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            x = int(row['x'])
            y = int(row['y'])
            locations.append((x, y))
    return locations


def detect_hotspots_baseline(temps: np.ndarray, threshold_sigma: float) -> np.ndarray:
    """Baseline hotspot detection using global threshold."""
    mean = np.mean(temps)
    std = np.std(temps)
    threshold = mean + (threshold_sigma * std)
    return temps > threshold


def detect_hotspots_bilateral(temps: np.ndarray, threshold_sigma: float,
                             d: int = 9, sigma_color: float = 75,
                             sigma_space: float = 75) -> np.ndarray:
    """Enhanced detection with bilateral filtering for noise reduction."""
    # Import cv2 only if available
    try:
        import cv2
        # Normalize to 0-255 for bilateral filter
        norm_temps = ((temps - temps.min()) / (temps.max() - temps.min()) * 255).astype(np.uint8)
        filtered = cv2.bilateralFilter(norm_temps, d, sigma_color, sigma_space)
        # Convert back to temperature scale
        filtered_temps = filtered.astype(np.float32) / 255 * (temps.max() - temps.min()) + temps.min()
    except ImportError:
        print("OpenCV not available, using Gaussian filter instead")
        filtered_temps = ndimage.gaussian_filter(temps, sigma=1.5)

    mean = np.mean(filtered_temps)
    std = np.std(filtered_temps)
    threshold = mean + (threshold_sigma * std)
    return filtered_temps > threshold


def detect_hotspots_local_delta(temps: np.ndarray, threshold_sigma: float,
                                window_size: int = 7) -> np.ndarray:
    """Local delta-T detection using annulus comparison."""
    h, w = temps.shape
    detections = np.zeros_like(temps, dtype=bool)

    half = window_size // 2

    for y in range(half, h - half):
        for x in range(half, w - half):
            # Center pixel
            center_temp = temps[y, x]

            # Create annulus mask (ring around center)
            y_grid, x_grid = np.ogrid[-half:half+1, -half:half+1]
            inner_radius = half // 2
            outer_radius = half
            annulus_mask = ((x_grid**2 + y_grid**2) >= inner_radius**2) & \
                          ((x_grid**2 + y_grid**2) <= outer_radius**2)

            # Get annulus temperatures
            annulus_temps = temps[y-half:y+half+1, x-half:x+half+1][annulus_mask]

            if len(annulus_temps) > 0:
                local_mean = np.mean(annulus_temps)
                local_std = np.std(annulus_temps)

                # Detect if center is significantly warmer than annulus
                if local_std > 0:
                    z_score = (center_temp - local_mean) / local_std
                    if z_score > threshold_sigma:
                        detections[y, x] = True

    return detections


def apply_morphology(mask: np.ndarray, operation: str) -> np.ndarray:
    """Apply morphological operations to reduce noise."""
    if operation == 'open':
        # Remove small false positives
        mask = ndimage.binary_opening(mask, structure=np.ones((3, 3)))
    elif operation == 'close':
        # Fill small gaps
        mask = ndimage.binary_closing(mask, structure=np.ones((3, 3)))
    elif operation == 'both':
        mask = ndimage.binary_opening(mask, structure=np.ones((3, 3)))
        mask = ndimage.binary_closing(mask, structure=np.ones((3, 3)))

    return mask


def cluster_detections(mask: np.ndarray, min_size: int = 2) -> List[Tuple[int, int]]:
    """Extract detection centroids from binary mask, filtering by cluster size."""
    # Label connected components
    labeled, num_features = ndimage.label(mask)

    detections = []
    for i in range(1, num_features + 1):
        component = (labeled == i)
        size = np.sum(component)

        if size >= min_size:
            # Get centroid
            y_coords, x_coords = np.where(component)
            centroid_x = int(np.mean(x_coords))
            centroid_y = int(np.mean(y_coords))
            detections.append((centroid_x, centroid_y))

    return detections


def match_detections(detections: List[Tuple[int, int]],
                    ground_truth: List[Tuple[int, int]],
                    match_radius: float = 5.0) -> Tuple[int, int, int]:
    """Match detections to ground truth within radius."""
    if not detections or not ground_truth:
        return 0, len(detections), len(ground_truth)

    det_array = np.array(detections)
    gt_array = np.array(ground_truth)

    # Calculate pairwise distances
    distances = cdist(det_array, gt_array)

    # Find matches within radius
    matched_detections = set()
    matched_ground_truth = set()

    for i in range(len(detections)):
        for j in range(len(ground_truth)):
            if distances[i, j] <= match_radius:
                matched_detections.add(i)
                matched_ground_truth.add(j)

    true_positives = len(matched_ground_truth)
    false_positives = len(detections) - len(matched_detections)
    false_negatives = len(ground_truth) - len(matched_ground_truth)

    return true_positives, false_positives, false_negatives


def calculate_metrics(tp: int, fp: int, fn: int) -> Dict[str, float]:
    """Calculate precision, recall, and F1 score."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'tp': tp,
        'fp': fp,
        'fn': fn
    }


def run_parameter_sweep(thermal_path: Path, ground_truth_path: Path,
                       output_dir: Path, verbose: bool = False) -> Dict:
    """Run parameter sweep on a single frame."""

    # Extract frame ID from filename
    frame_id = thermal_path.stem.split('_')[2]  # e.g., "0356" from "DJI_20241106194542_0356_T"

    # Load thermal data
    if verbose:
        print(f"\nProcessing frame {frame_id}...")

    temps = extract_thermal_data(str(thermal_path))
    if temps is None:
        raise ValueError(f"Failed to extract thermal data from {thermal_path}")

    # Load ground truth
    ground_truth = load_ground_truth(ground_truth_path)

    # Calculate thermal contrast for this frame
    mean_temp = np.mean(temps)
    std_temp = np.std(temps)

    # Get penguin temperatures (approximate using hottest pixels)
    hotspot_mask = temps > (mean_temp + 2 * std_temp)
    if np.any(hotspot_mask):
        penguin_temps = temps[hotspot_mask]
        contrast = np.mean(penguin_temps) - mean_temp
    else:
        contrast = 0.0

    results = {
        'frame_id': frame_id,
        'ground_truth_count': len(ground_truth),
        'thermal_contrast': contrast,
        'scene_std': std_temp,
        'methods': []
    }

    # Test parameters
    threshold_sigmas = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    window_sizes = [5, 7, 9, 11]
    min_cluster_sizes = [1, 2, 3, 5]
    morphology_ops = ['none', 'open', 'close', 'both']

    best_f1 = 0.0
    best_config = None

    # Method 1: Baseline hotspot detection
    for threshold in threshold_sigmas:
        for morph in morphology_ops:
            for min_cluster in min_cluster_sizes:
                mask = detect_hotspots_baseline(temps, threshold)
                if morph != 'none':
                    mask = apply_morphology(mask, morph)
                detections = cluster_detections(mask, min_cluster)

                tp, fp, fn = match_detections(detections, ground_truth)
                metrics = calculate_metrics(tp, fp, fn)

                config = {
                    'method': 'baseline',
                    'threshold_sigma': threshold,
                    'morphology': morph,
                    'min_cluster_size': min_cluster,
                    **metrics
                }
                results['methods'].append(config)

                if metrics['f1'] > best_f1:
                    best_f1 = metrics['f1']
                    best_config = config

    # Method 2: Bilateral filter + hotspot
    for threshold in threshold_sigmas:
        for morph in morphology_ops:
            for min_cluster in min_cluster_sizes:
                mask = detect_hotspots_bilateral(temps, threshold)
                if morph != 'none':
                    mask = apply_morphology(mask, morph)
                detections = cluster_detections(mask, min_cluster)

                tp, fp, fn = match_detections(detections, ground_truth)
                metrics = calculate_metrics(tp, fp, fn)

                config = {
                    'method': 'bilateral',
                    'threshold_sigma': threshold,
                    'morphology': morph,
                    'min_cluster_size': min_cluster,
                    **metrics
                }
                results['methods'].append(config)

                if metrics['f1'] > best_f1:
                    best_f1 = metrics['f1']
                    best_config = config

    # Method 3: Local delta-T with annulus
    for threshold in threshold_sigmas:
        for window in window_sizes:
            for morph in morphology_ops:
                for min_cluster in min_cluster_sizes:
                    mask = detect_hotspots_local_delta(temps, threshold, window)
                    if morph != 'none':
                        mask = apply_morphology(mask, morph)
                    detections = cluster_detections(mask, min_cluster)

                    tp, fp, fn = match_detections(detections, ground_truth)
                    metrics = calculate_metrics(tp, fp, fn)

                    config = {
                        'method': 'local_delta',
                        'threshold_sigma': threshold,
                        'window_size': window,
                        'morphology': morph,
                        'min_cluster_size': min_cluster,
                        **metrics
                    }
                    results['methods'].append(config)

                    if metrics['f1'] > best_f1:
                        best_f1 = metrics['f1']
                        best_config = config

    results['best_config'] = best_config
    results['best_f1'] = best_f1

    if verbose:
        print(f"  Frame {frame_id}: Best F1 = {best_f1:.3f}")
        print(f"    Method: {best_config['method']}")
        print(f"    Threshold: {best_config['threshold_sigma']}σ")
        print(f"    Precision: {best_config['precision']:.1%}, Recall: {best_config['recall']:.1%}")

    return results


def main():
    parser = argparse.ArgumentParser(description='Optimize thermal detection parameters')
    parser.add_argument('--ground-truth-dir', type=Path, required=True,
                       help='Directory containing ground truth CSV files')
    parser.add_argument('--thermal-dir', type=Path, required=True,
                       help='Directory containing thermal images')
    parser.add_argument('--output', type=Path, default='data/interim/optimization_results.json',
                       help='Output JSON file for results')
    parser.add_argument('--csv-output', type=Path, help='Optional CSV output for summary')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    # Find matching thermal and ground truth files
    ground_truth_files = sorted(args.ground_truth_dir.glob('frame_*_locations.csv'))

    if not ground_truth_files:
        print(f"No ground truth files found in {args.ground_truth_dir}")
        sys.exit(1)

    print(f"Found {len(ground_truth_files)} ground truth files")

    all_results = []
    summary = []

    for gt_file in ground_truth_files:
        # Extract frame ID
        frame_id = gt_file.stem.split('_')[1]  # e.g., "0356" from "frame_0356_locations"

        # Find corresponding thermal image
        thermal_pattern = f"*_{frame_id}_T.JPG"
        thermal_files = list(args.thermal_dir.glob(f"**/{thermal_pattern}"))

        if not thermal_files:
            print(f"Warning: No thermal image found for frame {frame_id}")
            continue

        thermal_file = thermal_files[0]

        # Run parameter sweep
        try:
            results = run_parameter_sweep(thermal_file, gt_file,
                                        args.output.parent, args.verbose)
            all_results.append(results)

            # Add to summary
            best = results['best_config']
            summary.append({
                'frame_id': frame_id,
                'contrast_C': f"{results['thermal_contrast']:.1f}",
                'ground_truth': results['ground_truth_count'],
                'best_method': best['method'],
                'threshold_sigma': best['threshold_sigma'],
                'precision': f"{best['precision']:.1%}",
                'recall': f"{best['recall']:.1%}",
                'f1': f"{best['f1']:.3f}"
            })

        except Exception as e:
            print(f"Error processing frame {frame_id}: {e}")
            continue

    # Save detailed results as JSON
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\nDetailed results saved to {args.output}")

    # Save summary as CSV if requested
    if args.csv_output:
        with open(args.csv_output, 'w', newline='') as f:
            if summary:
                writer = csv.DictWriter(f, fieldnames=summary[0].keys())
                writer.writeheader()
                writer.writerows(summary)
        print(f"Summary saved to {args.csv_output}")

    # Print summary
    print("\nOptimization Summary:")
    print("-" * 80)
    print(f"{'Frame':<8} {'Contrast':<10} {'GT':<5} {'Method':<12} {'Thresh':<8} {'Prec':<8} {'Recall':<8} {'F1':<8}")
    print("-" * 80)

    for s in summary:
        print(f"{s['frame_id']:<8} {s['contrast_C']:<10} {s['ground_truth']:<5} "
              f"{s['best_method']:<12} {s['threshold_sigma']:<8} "
              f"{s['precision']:<8} {s['recall']:<8} {s['f1']:<8}")

    # Calculate average performance
    if summary:
        avg_f1 = np.mean([float(s['f1']) for s in summary])
        print("-" * 80)
        print(f"Average F1 Score: {avg_f1:.3f}")

    # Find globally best parameters across all frames
    all_methods = []
    for result in all_results:
        all_methods.extend(result['methods'])

    # Group by method and parameters
    from collections import defaultdict
    param_groups = defaultdict(list)

    for method in all_methods:
        key = (method['method'], method['threshold_sigma'],
               method.get('window_size', 'N/A'), method['morphology'],
               method['min_cluster_size'])
        param_groups[key].append(method['f1'])

    # Find parameters with best average F1
    best_avg_f1 = 0
    best_params = None
    for params, f1_scores in param_groups.items():
        avg = np.mean(f1_scores)
        if avg > best_avg_f1:
            best_avg_f1 = avg
            best_params = params

    if best_params:
        print(f"\nBest Parameters (Average F1 = {best_avg_f1:.3f}):")
        print(f"  Method: {best_params[0]}")
        print(f"  Threshold: {best_params[1]}σ")
        if best_params[2] != 'N/A':
            print(f"  Window Size: {best_params[2]}")
        print(f"  Morphology: {best_params[3]}")
        print(f"  Min Cluster Size: {best_params[4]}")

        # Save optimal parameters
        optimal_params = {
            'method': best_params[0],
            'threshold_sigma': best_params[1],
            'window_size': best_params[2] if best_params[2] != 'N/A' else None,
            'morphology': best_params[3],
            'min_cluster_size': best_params[4],
            'avg_f1': best_avg_f1
        }

        optimal_path = args.output.parent / 'optimal_thermal_params.json'
        with open(optimal_path, 'w') as f:
            json.dump(optimal_params, f, indent=2)
        print(f"\nOptimal parameters saved to {optimal_path}")


if __name__ == '__main__':
    main()