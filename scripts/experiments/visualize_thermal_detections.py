#!/usr/bin/env python3
"""
Comprehensive thermal detection visualization script for penguin detection pipeline.
Reproduces the visualization style from the thermal findings summary.

Creates a multi-panel visualization showing:
1. Raw thermal image with temperature colormap
2. Ground truth positions overlay
3. Detection results vs ground truth comparison
4. Detection metrics summary

Author: Penguin Detection Pipeline Team
Date: 2025-10-17
"""

import sys
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from scipy import ndimage
from scipy.ndimage import binary_erosion, binary_dilation, gaussian_filter
import csv
import argparse


def extract_thermal_data(image_path):
    """Extract 16-bit radiometric thermal data from DJI H20T image."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = Path(tmpdir) / "thermal.raw"

        cmd = ["exiftool", "-b", "-ThermalData", str(image_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, check=True)
            raw_path.write_bytes(result.stdout)
        except FileNotFoundError:
            print("ERROR: exiftool not found. Please install it using: brew install exiftool")
            return None
        except subprocess.CalledProcessError as e:
            print(f"ERROR: exiftool failed: {e.stderr.decode()}")
            return None

        raw = np.fromfile(raw_path, dtype=np.uint16)

        if len(raw) != 640 * 512:
            print(f"ERROR: Wrong data size: {len(raw)} (expected {640 * 512})")
            return None

        img_raw = raw.reshape((512, 640))

        # DJI thermal conversion formula (validated from documentation)
        celsius = np.right_shift(img_raw, 2).astype(np.float32)
        celsius *= 0.0625
        celsius -= 273.15

        return celsius


def detect_blobs_baseline(temp_array, threshold_sigma=0.5, min_area=4, max_area=200):
    """Simple baseline blob detection using global threshold."""
    mean_temp = np.mean(temp_array)
    std_temp = np.std(temp_array)
    threshold = mean_temp + (threshold_sigma * std_temp)

    binary = temp_array > threshold
    labeled, num_features = ndimage.label(binary)

    detections = []
    for i in range(1, num_features + 1):
        blob = (labeled == i)
        area = np.sum(blob)

        if min_area <= area <= max_area:
            coords = np.argwhere(blob)
            centroid_y = np.mean(coords[:, 0])
            centroid_x = np.mean(coords[:, 1])

            # Get temperature stats for this blob
            blob_temps = temp_array[blob]
            max_temp = np.max(blob_temps)
            mean_temp = np.mean(blob_temps)

            detections.append({
                'centroid_x': centroid_x,
                'centroid_y': centroid_y,
                'area': area,
                'max_temp': max_temp,
                'mean_temp': mean_temp
            })

    return detections


def detect_blobs_enhanced(temp_array, threshold_sigma=1.5, min_area=4, max_area=200):
    """Enhanced blob detection with bilateral filtering."""
    # Apply bilateral filter to reduce noise while preserving edges
    filtered = gaussian_filter(temp_array, sigma=2.0)

    mean_temp = np.mean(filtered)
    std_temp = np.std(filtered)
    threshold = mean_temp + (threshold_sigma * std_temp)

    binary = filtered > threshold

    # Morphological operations to clean up detections
    binary = binary_erosion(binary, iterations=1)
    binary = binary_dilation(binary, iterations=1)

    labeled, num_features = ndimage.label(binary)

    detections = []
    for i in range(1, num_features + 1):
        blob = (labeled == i)
        area = np.sum(blob)

        if min_area <= area <= max_area:
            coords = np.argwhere(blob)
            centroid_y = np.mean(coords[:, 0])
            centroid_x = np.mean(coords[:, 1])

            # Get temperature stats from original image
            blob_temps = temp_array[blob]
            max_temp = np.max(blob_temps)
            mean_temp = np.mean(blob_temps)

            detections.append({
                'centroid_x': centroid_x,
                'centroid_y': centroid_y,
                'area': area,
                'max_temp': max_temp,
                'mean_temp': mean_temp
            })

    return detections


def detect_blobs_local_delta(temp_array, threshold_sigma=3.0, window_radius=10, min_area=4, max_area=200):
    """Local delta-T annulus method for detection."""
    height, width = temp_array.shape
    delta_t_map = np.zeros_like(temp_array)

    for y in range(window_radius, height - window_radius):
        for x in range(window_radius, width - window_radius):
            # Get center pixel temperature
            center_temp = temp_array[y, x]

            # Create annulus mask
            y_grid, x_grid = np.ogrid[-window_radius:window_radius+1, -window_radius:window_radius+1]
            inner_radius = window_radius // 2
            outer_radius = window_radius
            annulus_mask = ((x_grid**2 + y_grid**2 >= inner_radius**2) &
                           (x_grid**2 + y_grid**2 <= outer_radius**2))

            # Get surrounding region
            region = temp_array[y-window_radius:y+window_radius+1,
                               x-window_radius:x+window_radius+1]

            # Calculate local statistics from annulus
            annulus_temps = region[annulus_mask]
            local_mean = np.mean(annulus_temps)
            local_std = np.std(annulus_temps)

            # Store normalized delta-T
            if local_std > 0:
                delta_t_map[y, x] = (center_temp - local_mean) / local_std

    # Threshold on local delta-T
    binary = delta_t_map > threshold_sigma
    labeled, num_features = ndimage.label(binary)

    detections = []
    for i in range(1, num_features + 1):
        blob = (labeled == i)
        area = np.sum(blob)

        if min_area <= area <= max_area:
            coords = np.argwhere(blob)
            centroid_y = np.mean(coords[:, 0])
            centroid_x = np.mean(coords[:, 1])

            blob_temps = temp_array[blob]
            max_temp = np.max(blob_temps)
            mean_temp = np.mean(blob_temps)

            detections.append({
                'centroid_x': centroid_x,
                'centroid_y': centroid_y,
                'area': area,
                'max_temp': max_temp,
                'mean_temp': mean_temp,
                'delta_t': np.max(delta_t_map[blob])
            })

    return detections, delta_t_map


def load_ground_truth_from_csv(csv_path):
    """Load ground truth positions from CSV file."""
    coords = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            x = float(row['pixel_x'])
            y = float(row['pixel_y'])
            coords.append([x, y])
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


def create_comprehensive_visualization(temp_array, ground_truth, detections, metrics,
                                      threshold, image_name, output_path,
                                      delta_t_map=None, method_name="baseline"):
    """Create a comprehensive multi-panel visualization matching the style from the image."""

    # Create figure with custom layout
    fig = plt.figure(figsize=(20, 12))

    # Define grid for subplots
    gs = fig.add_gridspec(2, 3, width_ratios=[1, 1, 0.8], height_ratios=[1, 1],
                         hspace=0.15, wspace=0.15)

    # Panel 1: Raw thermal image
    ax1 = fig.add_subplot(gs[0, 0])
    im1 = ax1.imshow(temp_array, cmap='hot', origin='upper')
    ax1.set_title('Thermal Image (Raw Temperature)', fontsize=14, fontweight='bold', pad=10)
    cbar1 = plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
    cbar1.set_label('Temperature (°C)', fontsize=10)
    ax1.axis('off')

    # Add temperature statistics as text overlay
    temp_stats = f"Range: {temp_array.min():.1f} to {temp_array.max():.1f}°C\nMean: {temp_array.mean():.1f}°C\nStd: {temp_array.std():.1f}°C"
    ax1.text(0.02, 0.98, temp_stats, transform=ax1.transAxes,
             fontsize=9, verticalalignment='top', bbox=dict(boxstyle='round',
             facecolor='white', alpha=0.8))

    # Panel 2: Ground truth overlay
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.imshow(temp_array, cmap='gray', origin='upper', alpha=0.9)

    # Plot ground truth points with green circles
    for i, (x, y) in enumerate(ground_truth):
        circle = Circle((x, y), radius=8, fill=False, edgecolor='lime',
                       linewidth=2.5, alpha=0.9)
        ax2.add_patch(circle)
        # Add a center dot for better visibility
        ax2.plot(x, y, 'o', color='lime', markersize=3)

    ax2.set_title('Ground Truth Positions', fontsize=14, fontweight='bold', pad=10)
    ax2.text(0.98, 0.02, f'Ground truth (n={len(ground_truth)})',
             transform=ax2.transAxes, fontsize=10, ha='right',
             bbox=dict(boxstyle='round', facecolor='lime', alpha=0.3))
    ax2.axis('off')

    # Panel 3: Detection metrics (text panel)
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.axis('off')

    # Format metrics text
    metrics_text = f"""DETECTION METRICS (σ={threshold})

True Positives:  {metrics['true_positives']:2d}
False Positives: {metrics['false_positives']:2d}
False Negatives: {metrics['false_negatives']:2d}

Precision: {metrics['precision']*100:5.1f}%
Recall:    {metrics['recall']*100:5.1f}%
F1 Score:  {metrics['f1_score']:.3f}

IMAGE: {image_name}
Ground Truth Penguins: {len(ground_truth)}
Method: {method_name}"""

    ax3.text(0.1, 0.5, metrics_text, fontsize=12, family='monospace',
            verticalalignment='center', transform=ax3.transAxes,
            bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.2))

    # Panel 4: Detections vs Ground Truth comparison
    ax4 = fig.add_subplot(gs[1, :2])
    ax4.imshow(temp_array, cmap='gray', origin='upper', alpha=0.9)

    # Plot ground truth with green circles
    for x, y in ground_truth:
        circle = Circle((x, y), radius=8, fill=False, edgecolor='lime',
                       linewidth=2, alpha=0.8)
        ax4.add_patch(circle)

    # Plot detections with red X markers
    if len(detections) > 0:
        det_coords = np.array([[d['centroid_x'], d['centroid_y']] for d in detections])
        ax4.scatter(det_coords[:, 0], det_coords[:, 1],
                   c='red', s=150, marker='x', linewidths=2.5,
                   alpha=0.9)

        # Add detection boxes for better visibility
        for det in detections:
            # Create a box around each detection
            box_size = max(10, np.sqrt(det['area']) * 2)
            rect = plt.Rectangle((det['centroid_x'] - box_size/2,
                                 det['centroid_y'] - box_size/2),
                                box_size, box_size, fill=False,
                                edgecolor='red', linewidth=1, alpha=0.5)
            ax4.add_patch(rect)

    ax4.set_title(f'Detections vs Ground Truth (σ={threshold})',
                 fontsize=14, fontweight='bold', pad=10)

    # Create custom legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='none',
               markeredgecolor='lime', markersize=10, markeredgewidth=2,
               label=f'Ground Truth (n={len(ground_truth)})'),
        Line2D([0], [0], marker='x', color='red', linestyle='none',
               markersize=10, markeredgewidth=2.5,
               label=f'Detections (n={len(detections)})')
    ]
    ax4.legend(handles=legend_elements, loc='upper right', fontsize=10,
              framealpha=0.9, edgecolor='black')
    ax4.axis('off')

    # Panel 5: Delta-T map (if available) or temperature histogram
    ax5 = fig.add_subplot(gs[1, 2])

    if delta_t_map is not None:
        im5 = ax5.imshow(delta_t_map, cmap='coolwarm', origin='upper', vmin=-3, vmax=3)
        ax5.set_title('Local ΔT Map (σ)', fontsize=10, fontweight='bold')
        cbar5 = plt.colorbar(im5, ax=ax5, fraction=0.046, pad=0.04)
        cbar5.set_label('ΔT (σ)', fontsize=8)
        ax5.axis('off')
    else:
        # Show temperature histogram
        ax5.hist(temp_array.flatten(), bins=50, color='orange', alpha=0.7, edgecolor='black')
        ax5.axvline(temp_array.mean(), color='red', linestyle='--', linewidth=2, label='Mean')
        ax5.axvline(temp_array.mean() + threshold * temp_array.std(),
                   color='green', linestyle='--', linewidth=2, label=f'Threshold ({threshold}σ)')
        ax5.set_xlabel('Temperature (°C)', fontsize=10)
        ax5.set_ylabel('Pixel Count', fontsize=10)
        ax5.set_title('Temperature Distribution', fontsize=10, fontweight='bold')
        ax5.legend(fontsize=8)
        ax5.grid(True, alpha=0.3)

    # Add overall title
    fig.suptitle(f'Thermal Detection Analysis - {image_name}',
                fontsize=16, fontweight='bold', y=0.98)

    # Save figure
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"Visualization saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Visualize thermal detections for penguin detection')
    parser.add_argument('--image', type=str, required=True, help='Path to thermal image')
    parser.add_argument('--ground-truth', type=str, help='Path to ground truth CSV file')
    parser.add_argument('--method', type=str, default='baseline',
                       choices=['baseline', 'enhanced', 'local_delta', 'all'],
                       help='Detection method to use')
    parser.add_argument('--threshold', type=float, default=3.0, help='Detection threshold in sigma')
    parser.add_argument('--output-dir', type=str, default='data/interim/thermal_validation',
                       help='Output directory for visualizations')
    parser.add_argument('--distance-threshold', type=float, default=15.0,
                       help='Distance threshold for matching detections to ground truth')

    args = parser.parse_args()

    # Setup paths
    image_path = Path(args.image)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not image_path.exists():
        print(f"ERROR: Image not found: {image_path}")
        return 1

    print("=" * 80)
    print("THERMAL DETECTION VISUALIZATION")
    print("=" * 80)
    print(f"Image: {image_path.name}")

    # Extract thermal data
    print("\nExtracting thermal data...")
    temp_array = extract_thermal_data(image_path)

    if temp_array is None:
        return 1

    print(f"Temperature range: {temp_array.min():.2f}°C to {temp_array.max():.2f}°C")
    print(f"Temperature mean: {temp_array.mean():.2f}°C ± {temp_array.std():.2f}°C")
    print(f"Image shape: {temp_array.shape}")

    # Load ground truth if provided
    ground_truth = None
    if args.ground_truth:
        gt_path = Path(args.ground_truth)
        if gt_path.exists():
            ground_truth = load_ground_truth_from_csv(gt_path)
            print(f"\nLoaded {len(ground_truth)} ground truth positions")
        else:
            print(f"WARNING: Ground truth file not found: {gt_path}")

    # If no ground truth file provided, check for default location
    if ground_truth is None:
        default_gt_path = output_dir / f"{image_path.stem}_penguin_pixels.csv"
        if default_gt_path.exists():
            ground_truth = load_ground_truth_from_csv(default_gt_path)
            print(f"\nLoaded {len(ground_truth)} ground truth positions from default location")
        else:
            print("\nNo ground truth data available - will show detections only")
            ground_truth = np.array([])  # Empty array for no ground truth

    # Run detection methods
    methods_to_run = []
    if args.method == 'all':
        methods_to_run = ['baseline', 'enhanced', 'local_delta']
    else:
        methods_to_run = [args.method]

    for method_name in methods_to_run:
        print(f"\n{'-' * 40}")
        print(f"Running {method_name.upper()} detection...")
        print(f"{'-' * 40}")

        delta_t_map = None

        if method_name == 'baseline':
            detections = detect_blobs_baseline(temp_array, threshold_sigma=args.threshold)
        elif method_name == 'enhanced':
            detections = detect_blobs_enhanced(temp_array, threshold_sigma=args.threshold)
        elif method_name == 'local_delta':
            detections, delta_t_map = detect_blobs_local_delta(temp_array, threshold_sigma=args.threshold)

        print(f"Found {len(detections)} detections")

        # Calculate metrics if ground truth is available
        if len(ground_truth) > 0:
            det_coords = np.array([[d['centroid_x'], d['centroid_y']] for d in detections]) if detections else np.array([]).reshape(0, 2)
            metrics = calculate_metrics(ground_truth, det_coords, distance_threshold=args.distance_threshold)

            print(f"True Positives:  {metrics['true_positives']}")
            print(f"False Positives: {metrics['false_positives']}")
            print(f"False Negatives: {metrics['false_negatives']}")
            print(f"Precision: {metrics['precision']:.1%}")
            print(f"Recall:    {metrics['recall']:.1%}")
            print(f"F1 Score:  {metrics['f1_score']:.3f}")
        else:
            # Create dummy metrics if no ground truth
            metrics = {
                'true_positives': 0,
                'false_positives': len(detections),
                'false_negatives': 0,
                'precision': 0.0,
                'recall': 0.0,
                'f1_score': 0.0
            }

        # Create visualization
        output_path = output_dir / f"thermal_detection_{image_path.stem}_{method_name}_sigma{args.threshold}.png"
        create_comprehensive_visualization(
            temp_array, ground_truth, detections, metrics,
            args.threshold, image_path.stem, output_path,
            delta_t_map=delta_t_map, method_name=method_name
        )

    print("\n" + "=" * 80)
    print("VISUALIZATION COMPLETE")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())