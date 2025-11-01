#!/usr/bin/env python3
"""
Batch thermal detection across all thermal images.

This script processes a large dataset of thermal images using optimized
parameters from the optimization phase.
"""

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
from scipy import ndimage
from datetime import datetime

# Add parent directory to path for pipeline imports
sys.path.append(str(Path(__file__).parent.parent))
from pipelines.thermal import extract_thermal_data


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
    try:
        import cv2
        norm_temps = ((temps - temps.min()) / (temps.max() - temps.min()) * 255).astype(np.uint8)
        filtered = cv2.bilateralFilter(norm_temps, d, sigma_color, sigma_space)
        filtered_temps = filtered.astype(np.float32) / 255 * (temps.max() - temps.min()) + temps.min()
    except ImportError:
        # Fallback to Gaussian filter if OpenCV not available
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
            center_temp = temps[y, x]

            # Create annulus mask
            y_grid, x_grid = np.ogrid[-half:half+1, -half:half+1]
            inner_radius = half // 2
            outer_radius = half
            annulus_mask = ((x_grid**2 + y_grid**2) >= inner_radius**2) & \
                          ((x_grid**2 + y_grid**2) <= outer_radius**2)

            annulus_temps = temps[y-half:y+half+1, x-half:x+half+1][annulus_mask]

            if len(annulus_temps) > 0:
                local_mean = np.mean(annulus_temps)
                local_std = np.std(annulus_temps)

                if local_std > 0:
                    z_score = (center_temp - local_mean) / local_std
                    if z_score > threshold_sigma:
                        detections[y, x] = True

    return detections


def apply_morphology(mask: np.ndarray, operation: str) -> np.ndarray:
    """Apply morphological operations to reduce noise."""
    if operation == 'open':
        mask = ndimage.binary_opening(mask, structure=np.ones((3, 3)))
    elif operation == 'close':
        mask = ndimage.binary_closing(mask, structure=np.ones((3, 3)))
    elif operation == 'both':
        mask = ndimage.binary_opening(mask, structure=np.ones((3, 3)))
        mask = ndimage.binary_closing(mask, structure=np.ones((3, 3)))
    return mask


def cluster_detections(mask: np.ndarray, min_size: int = 2) -> List[Dict]:
    """Extract detection centroids and properties from binary mask."""
    labeled, num_features = ndimage.label(mask)
    detections = []

    for i in range(1, num_features + 1):
        component = (labeled == i)
        size = np.sum(component)

        if size >= min_size:
            y_coords, x_coords = np.where(component)
            centroid_x = int(np.mean(x_coords))
            centroid_y = int(np.mean(y_coords))

            # Calculate bounding box
            min_x, max_x = np.min(x_coords), np.max(x_coords)
            min_y, max_y = np.min(y_coords), np.max(y_coords)

            detections.append({
                'x': centroid_x,
                'y': centroid_y,
                'size': size,
                'bbox': [min_x, min_y, max_x, max_y]
            })

    return detections


def process_single_frame(thermal_path: Path, params: Dict,
                        checkpoint_dir: Optional[Path] = None,
                        save_checkpoint: bool = True) -> Dict:
    """Process a single thermal frame with given parameters."""

    frame_id = thermal_path.stem

    # Check if already processed (checkpoint)
    if checkpoint_dir:
        result_file = checkpoint_dir / f"{frame_id}_detections.json"
        if result_file.exists():
            with open(result_file, 'r') as f:
                return json.load(f)

    start_time = time.time()

    # Extract thermal data
    temps = extract_thermal_data(str(thermal_path))
    if temps is None:
        return {
            'frame_id': frame_id,
            'status': 'error',
            'error': 'Failed to extract thermal data',
            'detections': [],
            'count': 0
        }

    # Apply detection method based on parameters
    method = params['method']

    if method == 'baseline':
        mask = detect_hotspots_baseline(temps, params['threshold_sigma'])
    elif method == 'bilateral':
        mask = detect_hotspots_bilateral(temps, params['threshold_sigma'])
    elif method == 'local_delta':
        mask = detect_hotspots_local_delta(
            temps, params['threshold_sigma'], params.get('window_size', 7))
    else:
        return {
            'frame_id': frame_id,
            'status': 'error',
            'error': f'Unknown method: {method}',
            'detections': [],
            'count': 0
        }

    # Apply morphology if specified
    if params.get('morphology', 'none') != 'none':
        mask = apply_morphology(mask, params['morphology'])

    # Extract detections
    detections = cluster_detections(mask, params.get('min_cluster_size', 2))

    # Get temperature statistics for each detection
    for det in detections:
        x, y = det['x'], det['y']
        # Get temperature at detection center (3x3 window)
        y_min = max(0, y - 1)
        y_max = min(temps.shape[0], y + 2)
        x_min = max(0, x - 1)
        x_max = min(temps.shape[1], x + 2)
        window = temps[y_min:y_max, x_min:x_max]
        det['temperature'] = float(np.mean(window))
        det['max_temperature'] = float(np.max(window))

    # Calculate scene statistics
    scene_mean = float(np.mean(temps))
    scene_std = float(np.std(temps))
    scene_min = float(np.min(temps))
    scene_max = float(np.max(temps))

    result = {
        'frame_id': frame_id,
        'status': 'success',
        'detections': detections,
        'count': len(detections),
        'scene_stats': {
            'mean': scene_mean,
            'std': scene_std,
            'min': scene_min,
            'max': scene_max
        },
        'processing_time': time.time() - start_time,
        'timestamp': datetime.now().isoformat()
    }

    # Save checkpoint if directory provided and enabled
    if checkpoint_dir and save_checkpoint:
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        result_file = checkpoint_dir / f"{frame_id}_detections.json"
        with open(result_file, 'w') as f:
            json.dump(result, f)

    return result


def main():
    parser = argparse.ArgumentParser(description='Batch thermal detection')
    parser.add_argument('--input', type=Path, required=True,
                       help='Directory containing thermal images')
    parser.add_argument('--params', type=Path, required=True,
                       help='JSON file with detection parameters')
    parser.add_argument('--output', type=Path, required=True,
                       help='Output directory for results')
    parser.add_argument('--parallel', type=int, default=1,
                       help='Number of parallel processes')
    parser.add_argument('--checkpoint-every', type=int, default=100,
                       help='Save checkpoint every N frames')
    parser.add_argument('--resume', action='store_true',
                       help='Resume from checkpoint')
    parser.add_argument('--pattern', default='*_T.JPG',
                       help='File pattern for thermal images')
    parser.add_argument('--limit', type=int,
                       help='Process only first N images (for testing)')
    parser.add_argument('--verbose', action='store_true',
                       help='Verbose output')

    args = parser.parse_args()

    # Load parameters
    with open(args.params, 'r') as f:
        params = json.load(f)

    print(f"Detection parameters:")
    print(f"  Method: {params['method']}")
    print(f"  Threshold: {params['threshold_sigma']}σ")
    if 'window_size' in params:
        print(f"  Window size: {params['window_size']}")
    print(f"  Morphology: {params.get('morphology', 'none')}")
    print(f"  Min cluster size: {params.get('min_cluster_size', 2)}")

    # Find thermal images
    thermal_files = sorted(args.input.glob(f"**/{args.pattern}"))

    if args.limit:
        thermal_files = thermal_files[:args.limit]

    print(f"\nFound {len(thermal_files)} thermal images to process")

    if not thermal_files:
        print("No images found!")
        sys.exit(1)

    # Setup output directory
    args.output.mkdir(parents=True, exist_ok=True)
    # Only create checkpoint dir if checkpointing is enabled
    checkpoint_dir = args.output / 'checkpoints' if args.checkpoint_every > 0 else None

    # Filter out already processed files if resuming
    if args.resume and checkpoint_dir and checkpoint_dir.exists():
        processed = set()
        for ckpt in checkpoint_dir.glob('*_detections.json'):
            frame_id = ckpt.stem.replace('_detections', '')
            processed.add(frame_id)

        original_count = len(thermal_files)
        thermal_files = [f for f in thermal_files if f.stem not in processed]
        print(f"Resuming: Skipping {original_count - len(thermal_files)} already processed files")

    # Process images
    all_results = []
    start_time = time.time()

    if args.parallel > 1:
        # Parallel processing
        print(f"Processing with {args.parallel} parallel workers...")

        with ProcessPoolExecutor(max_workers=args.parallel) as executor:
            # Submit all tasks
            futures = {}
            for idx, f in enumerate(thermal_files):
                # Determine if this frame should save a checkpoint
                save_checkpoint = (args.checkpoint_every > 0 and
                                 (idx + 1) % args.checkpoint_every == 0)
                futures[executor.submit(process_single_frame, f, params,
                                       checkpoint_dir, save_checkpoint)] = (f, idx)

            # Process as they complete
            for i, future in enumerate(as_completed(futures), 1):
                try:
                    result = future.result()
                    all_results.append(result)

                    if args.verbose:
                        print(f"[{i}/{len(thermal_files)}] {result['frame_id']}: "
                              f"{result['count']} detections")

                    # Progress update
                    if i % 10 == 0:
                        elapsed = time.time() - start_time
                        rate = i / elapsed
                        eta = (len(thermal_files) - i) / rate
                        print(f"Progress: {i}/{len(thermal_files)} "
                              f"({i/len(thermal_files)*100:.1f}%) - "
                              f"Rate: {rate:.1f} fps - ETA: {eta/60:.1f} min")

                except Exception as e:
                    original_file, _ = futures[future]
                    print(f"Error processing {original_file}: {e}")

    else:
        # Sequential processing
        print("Processing sequentially...")

        for i, thermal_file in enumerate(thermal_files, 1):
            try:
                # Determine if this frame should save a checkpoint
                save_checkpoint = (args.checkpoint_every > 0 and
                                 i % args.checkpoint_every == 0)
                result = process_single_frame(thermal_file, params, checkpoint_dir,
                                            save_checkpoint)
                all_results.append(result)

                if args.verbose:
                    print(f"[{i}/{len(thermal_files)}] {result['frame_id']}: "
                          f"{result['count']} detections")

                # Progress update
                if i % 10 == 0 or i == len(thermal_files):
                    elapsed = time.time() - start_time
                    rate = i / elapsed
                    eta = (len(thermal_files) - i) / rate if rate > 0 else 0
                    print(f"Progress: {i}/{len(thermal_files)} "
                          f"({i/len(thermal_files)*100:.1f}%) - "
                          f"Rate: {rate:.1f} fps - ETA: {eta/60:.1f} min")

            except Exception as e:
                print(f"Error processing {thermal_file}: {e}")

    # Sort results by frame ID
    all_results.sort(key=lambda x: x['frame_id'])

    # Save final complete results as checkpoint
    if checkpoint_dir and all_results:
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        final_checkpoint = checkpoint_dir / '_all_results.json'
        with open(final_checkpoint, 'w') as f:
            json.dump(all_results, f)
        print(f"Final results saved to checkpoint: {final_checkpoint}")

    # Save all detections to CSV
    csv_path = args.output / 'all_detections.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['frame_id', 'detection_id', 'x', 'y', 'temperature', 'size'])

        for result in all_results:
            if result['status'] == 'success':
                for j, det in enumerate(result['detections']):
                    writer.writerow([
                        result['frame_id'], j,
                        det['x'], det['y'],
                        det['temperature'], det['size']
                    ])

    print(f"\nDetection details saved to {csv_path}")

    # Save summary statistics
    total_count = sum(r['count'] for r in all_results if r['status'] == 'success')
    successful_frames = sum(1 for r in all_results if r['status'] == 'success')
    failed_frames = sum(1 for r in all_results if r['status'] == 'error')

    # Calculate per-frame statistics
    counts = [r['count'] for r in all_results if r['status'] == 'success']
    if counts:
        count_mean = np.mean(counts)
        count_std = np.std(counts)
        count_min = np.min(counts)
        count_max = np.max(counts)
        count_median = np.median(counts)
    else:
        count_mean = count_std = count_min = count_max = count_median = 0

    summary = {
        'total_frames': len(thermal_files),
        'successful_frames': successful_frames,
        'failed_frames': failed_frames,
        'total_detections': total_count,
        'average_per_frame': count_mean,
        'std_per_frame': count_std,
        'min_per_frame': int(count_min),
        'max_per_frame': int(count_max),
        'median_per_frame': count_median,
        'processing_time_seconds': time.time() - start_time,
        'parameters': params,
        'timestamp': datetime.now().isoformat()
    }

    summary_path = args.output / 'detection_summary.json'
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"Summary saved to {summary_path}")

    # Save per-frame counts CSV for easy analysis
    counts_csv_path = args.output / 'frame_counts.csv'
    with open(counts_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['frame_id', 'count', 'scene_mean_temp', 'scene_std_temp'])

        for result in all_results:
            if result['status'] == 'success':
                writer.writerow([
                    result['frame_id'],
                    result['count'],
                    result['scene_stats']['mean'],
                    result['scene_stats']['std']
                ])

    print(f"Frame counts saved to {counts_csv_path}")

    # Print final summary
    print("\n" + "=" * 60)
    print("BATCH PROCESSING COMPLETE")
    print("=" * 60)
    print(f"Total frames processed: {successful_frames}/{len(thermal_files)}")
    print(f"Total detections: {total_count}")
    print(f"Average per frame: {count_mean:.1f} ± {count_std:.1f}")
    print(f"Range: {count_min:.0f} - {count_max:.0f}")
    print(f"Processing time: {(time.time() - start_time)/60:.1f} minutes")
    print(f"Processing rate: {successful_frames/(time.time() - start_time):.1f} fps")

    # Compare to target
    if total_count > 0:
        target = 1533
        difference = total_count - target
        percent_diff = (difference / target) * 100
        print(f"\nTarget comparison:")
        print(f"  Target count: {target}")
        print(f"  Detected count: {total_count}")
        print(f"  Difference: {difference:+d} ({percent_diff:+.1f}%)")

        if abs(percent_diff) <= 20:
            print("  ✅ Within 20% of target")
        else:
            print(f"  ⚠️  {abs(percent_diff):.1f}% off target")


if __name__ == '__main__':
    main()