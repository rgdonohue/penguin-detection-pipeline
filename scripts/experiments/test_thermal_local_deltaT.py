#!/usr/bin/env python3
"""
Test local ΔT (delta-temperature) detection method for thermal penguin detection.

Instead of global mean+σ thresholding, this uses:
1. Local background subtraction: ΔT = pixel - median(annulus)
2. Local z-score normalization: z = ΔT / σ_local
3. Connected-component filtering for size constraints

This addresses the false positive explosion seen with global thresholding
while preserving the 8-10°C penguin contrast signal.

References:
- THERMAL_INVESTIGATION_REVIEW.md section on ΔT annulus
- Aerial wildlife literature: local background subtraction + morphological filtering

Usage:
    python scripts/test_thermal_local_deltaT.py \
        --thermal-image data/.../DJI_20241106194532_0353_T.JPG \
        --ground-truth verification_images/frame_0353_locations.csv \
        --output data/interim/thermal_validation/
"""

import sys
import argparse
from pathlib import Path
import numpy as np
import subprocess
import tempfile
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from scipy import ndimage
from skimage import morphology


def extract_thermal_data(image_path: Path, temp_dir: Path) -> np.ndarray:
    """Extract 16-bit radiometric thermal data from DJI RJPEG.

    Args:
        image_path: Path to DJI thermal JPEG
        temp_dir: Directory to store temporary raw file

    Returns:
        Temperature array (512, 640) in Celsius
    """
    raw_path = temp_dir / "thermal.raw"

    cmd = ["exiftool", "-b", "-ThermalData", str(image_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, check=True)
        raw_path.write_bytes(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"exiftool failed: {e.stderr.decode()}")

    raw = np.fromfile(raw_path, dtype=np.uint16)

    if len(raw) != 640 * 512:
        raise RuntimeError(f"ThermalData size mismatch: {len(raw)}, expected {640*512}")

    img_raw = raw.reshape((512, 640))

    # DJI thermal conversion
    celsius = np.right_shift(img_raw, 2).astype(np.float32)
    celsius *= 0.0625
    celsius -= 273.15

    return celsius


def load_ground_truth(csv_path: Path) -> list:
    """Load ground truth penguin locations from CSV.

    Returns:
        List of (x, y) tuples
    """
    locations = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            x, y = int(row['x']), int(row['y'])
            locations.append((x, y))
    return locations


def compute_local_deltaT(temp_array: np.ndarray,
                         window_size: int = 21,
                         core_size: int = 3) -> tuple:
    """Compute local ΔT using annulus background subtraction.

    For each pixel:
    - Core: central core_size × core_size region (the potential penguin)
    - Annulus: window_size × window_size region excluding core (local background)
    - ΔT = median(core) - median(annulus)
    - σ_local = std(annulus)
    - z-score = ΔT / σ_local

    Args:
        temp_array: Temperature array (H, W)
        window_size: Size of outer window for background (must be odd)
        core_size: Size of inner core to exclude (must be odd)

    Returns:
        (deltaT, local_std, zscore) arrays, all same shape as temp_array
    """
    H, W = temp_array.shape
    half_win = window_size // 2
    half_core = core_size // 2

    # Pad array to handle edges
    padded = np.pad(temp_array, half_win, mode='reflect')

    deltaT = np.zeros_like(temp_array)
    local_std = np.zeros_like(temp_array)
    zscore = np.zeros_like(temp_array)

    print(f"Computing local ΔT with {window_size}×{window_size} window, {core_size}×{core_size} core...")

    # Create mask for annulus (window minus core)
    mask = np.ones((window_size, window_size), dtype=bool)
    c_start = half_win - half_core
    c_end = half_win + half_core + 1
    mask[c_start:c_end, c_start:c_end] = False

    for i in range(H):
        if i % 100 == 0:
            print(f"  Processing row {i}/{H}...")
        for j in range(W):
            # Extract window from padded array
            window = padded[i:i+window_size, j:j+window_size]

            # Core (potential penguin)
            core = window[c_start:c_end, c_start:c_end]
            core_median = np.median(core)

            # Annulus (local background)
            annulus = window[mask]
            annulus_median = np.median(annulus)
            annulus_std = np.std(annulus)

            # Compute ΔT and z-score
            dt = core_median - annulus_median
            deltaT[i, j] = dt
            local_std[i, j] = annulus_std

            if annulus_std > 0:
                zscore[i, j] = dt / annulus_std
            else:
                zscore[i, j] = 0

    print("  ✓ Local ΔT computation complete")
    return deltaT, local_std, zscore


def detect_peaks_local(zscore: np.ndarray,
                       threshold_sigma: float = 2.0,
                       min_area: int = 4,
                       max_area: int = 50) -> list:
    """Detect peaks using local z-score threshold and connected components.

    Args:
        zscore: Local z-score array
        threshold_sigma: Threshold in local standard deviations
        min_area: Minimum blob area in pixels
        max_area: Maximum blob area in pixels

    Returns:
        List of detections with (x, y, area, max_zscore)
    """
    # Threshold
    binary = zscore > threshold_sigma

    # Morphological cleaning (remove tiny noise)
    binary = morphology.binary_opening(binary, morphology.disk(1))

    # Label connected components
    labeled, num_features = ndimage.label(binary)

    detections = []
    for i in range(1, num_features + 1):
        blob = (labeled == i)
        area = np.sum(blob)

        if min_area <= area <= max_area:
            # Compute centroid
            coords = np.argwhere(blob)
            centroid_y = np.mean(coords[:, 0])
            centroid_x = np.mean(coords[:, 1])

            # Get max z-score in blob
            max_z = np.max(zscore[blob])

            detections.append({
                'x': centroid_x,
                'y': centroid_y,
                'area': area,
                'max_zscore': max_z
            })

    return detections


def calculate_metrics(ground_truth: list, detections: list,
                     distance_threshold: float = 20.0) -> dict:
    """Calculate precision, recall, and F1 score.

    Args:
        ground_truth: List of (x, y) ground truth locations
        detections: List of detection dicts with 'x', 'y' keys
        distance_threshold: Maximum distance for a match (pixels)

    Returns:
        Dict with TP, FP, FN, precision, recall, F1
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

    # Convert to numpy arrays
    gt_array = np.array(ground_truth)
    det_array = np.array([[d['x'], d['y']] for d in detections])

    matched_gt = set()
    matched_det = set()

    for i, gt_pos in enumerate(gt_array):
        for j, det_pos in enumerate(det_array):
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


def visualize_results(temp_array: np.ndarray,
                     zscore: np.ndarray,
                     ground_truth: list,
                     detections: list,
                     metrics: dict,
                     threshold: float,
                     output_path: Path):
    """Create visualization comparing local ΔT method with ground truth."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    # Raw thermal
    ax = axes[0, 0]
    im = ax.imshow(temp_array, cmap='hot', origin='upper')
    ax.set_title('Raw Thermal Image', fontsize=11, fontweight='bold')
    plt.colorbar(im, ax=ax, label='Temperature (°C)', fraction=0.046)
    ax.axis('off')

    # Local z-score map
    ax = axes[0, 1]
    im = ax.imshow(zscore, cmap='RdYlBu_r', origin='upper', vmin=-3, vmax=6)
    ax.set_title('Local Z-Score (ΔT/σ_local)', fontsize=11, fontweight='bold')
    plt.colorbar(im, ax=ax, label='Z-Score', fraction=0.046)
    ax.axis('off')

    # Z-score histogram
    ax = axes[0, 2]
    ax.hist(zscore.ravel(), bins=100, alpha=0.7, color='steelblue', edgecolor='black')
    ax.axvline(threshold, color='red', linestyle='--', linewidth=2,
               label=f'Threshold: {threshold:.1f}σ')
    ax.set_xlabel('Local Z-Score', fontsize=10)
    ax.set_ylabel('Pixel Count', fontsize=10)
    ax.set_title('Z-Score Distribution', fontsize=11, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Ground truth overlay
    ax = axes[1, 0]
    ax.imshow(temp_array, cmap='gray', origin='upper')
    for (x, y) in ground_truth:
        circle = Circle((x, y), radius=10, color='lime', fill=False, linewidth=2)
        ax.add_patch(circle)
        ax.plot(x, y, 'g+', markersize=10, markeredgewidth=2)
    ax.set_title(f'Ground Truth (n={len(ground_truth)})', fontsize=11, fontweight='bold')
    ax.axis('off')

    # Detections overlay
    ax = axes[1, 1]
    ax.imshow(temp_array, cmap='gray', origin='upper')
    for (x, y) in ground_truth:
        circle = Circle((x, y), radius=10, color='lime', fill=False, linewidth=2, alpha=0.5)
        ax.add_patch(circle)
    if detections:
        for det in detections:
            ax.plot(det['x'], det['y'], 'rx', markersize=8, markeredgewidth=2)
    ax.set_title(f'Detections (n={len(detections)}) vs GT', fontsize=11, fontweight='bold')
    ax.axis('off')

    # Metrics table
    ax = axes[1, 2]
    ax.axis('off')

    metrics_text = f"""
LOCAL ΔT METHOD

Parameters:
  Threshold: {threshold:.1f}σ_local
  Window: 21×21 px
  Core: 3×3 px

Detection Metrics:
  True Positives:  {metrics['true_positives']}
  False Positives: {metrics['false_positives']}
  False Negatives: {metrics['false_negatives']}

  Precision: {metrics['precision']:.1%}
  Recall:    {metrics['recall']:.1%}
  F1 Score:  {metrics['f1_score']:.3f}

Ground Truth: {len(ground_truth)} penguins
Detections:   {len(detections)} peaks
"""

    ax.text(0.05, 0.95, metrics_text, transform=ax.transAxes,
            fontsize=11, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✅ Saved visualization: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Test local ΔT detection method on thermal imagery"
    )
    parser.add_argument("--thermal-image", type=Path, required=True,
                       help="DJI thermal JPEG image")
    parser.add_argument("--ground-truth", type=Path, required=True,
                       help="CSV with penguin locations (x,y,label)")
    parser.add_argument("--output", type=Path,
                       default=Path("data/interim/thermal_validation"),
                       help="Output directory")
    parser.add_argument("--window-size", type=int, default=21,
                       help="Local window size (must be odd)")
    parser.add_argument("--core-size", type=int, default=3,
                       help="Core size to exclude (must be odd)")
    parser.add_argument("--thresholds", nargs='+', type=float,
                       default=[1.0, 1.5, 2.0, 2.5, 3.0],
                       help="Z-score thresholds to test")

    args = parser.parse_args()

    print("=" * 80)
    print("LOCAL ΔT THERMAL DETECTION TEST")
    print("=" * 80)
    print(f"\nImage: {args.thermal_image.name}")
    print(f"Ground truth: {args.ground_truth.name}")
    print(f"Window size: {args.window_size}×{args.window_size}")
    print(f"Core size: {args.core_size}×{args.core_size}")
    print()

    # Extract thermal data
    print("Extracting thermal data...")
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_array = extract_thermal_data(args.thermal_image, Path(tmpdir))

    print(f"✓ Temperature range: {temp_array.min():.2f}°C to {temp_array.max():.2f}°C")
    print(f"✓ Mean: {temp_array.mean():.2f}°C ± {temp_array.std():.2f}°C")
    print()

    # Load ground truth
    ground_truth = load_ground_truth(args.ground_truth)
    print(f"✓ Loaded {len(ground_truth)} ground truth penguin locations")
    print()

    # Compute local ΔT and z-scores
    deltaT, local_std, zscore = compute_local_deltaT(
        temp_array,
        window_size=args.window_size,
        core_size=args.core_size
    )

    print(f"\nLocal ΔT statistics:")
    print(f"  ΔT range: {deltaT.min():.2f}°C to {deltaT.max():.2f}°C")
    print(f"  ΔT mean: {deltaT.mean():.2f}°C ± {deltaT.std():.2f}°C")
    print(f"  Z-score range: {zscore.min():.2f}σ to {zscore.max():.2f}σ")
    print(f"  Z-score mean: {zscore.mean():.2f}σ ± {zscore.std():.2f}σ")
    print()

    # Test multiple thresholds
    print("=" * 80)
    print("TESTING MULTIPLE THRESHOLDS")
    print("=" * 80)

    results = []
    for threshold in args.thresholds:
        print(f"\nThreshold: {threshold:.1f}σ_local")

        detections = detect_peaks_local(
            zscore,
            threshold_sigma=threshold,
            min_area=4,
            max_area=50
        )

        metrics = calculate_metrics(ground_truth, detections, distance_threshold=20.0)

        print(f"  Detections: {len(detections)}")
        print(f"  True Positives:  {metrics['true_positives']}")
        print(f"  False Positives: {metrics['false_positives']}")
        print(f"  False Negatives: {metrics['false_negatives']}")
        print(f"  Precision: {metrics['precision']:.1%}")
        print(f"  Recall:    {metrics['recall']:.1%}")
        print(f"  F1 Score:  {metrics['f1_score']:.3f}")

        results.append({
            'threshold': threshold,
            'detections': detections,
            'metrics': metrics
        })

    # Find best F1
    best = max(results, key=lambda r: r['metrics']['f1_score'])

    print("\n" + "=" * 80)
    print("BEST RESULT")
    print("=" * 80)
    print(f"Threshold: {best['threshold']:.1f}σ_local")
    print(f"F1 Score: {best['metrics']['f1_score']:.3f}")
    print(f"Precision: {best['metrics']['precision']:.1%}")
    print(f"Recall: {best['metrics']['recall']:.1%}")
    print(f"Detections: {len(best['detections'])}")
    print()

    # Create visualization for best result
    output_fig = args.output / f"{args.thermal_image.stem}_localDeltaT.png"
    visualize_results(
        temp_array,
        zscore,
        ground_truth,
        best['detections'],
        best['metrics'],
        best['threshold'],
        output_fig
    )

    # Save results table
    output_csv = args.output / f"{args.thermal_image.stem}_localDeltaT_results.csv"
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['threshold_sigma', 'detections', 'true_positives',
                        'false_positives', 'false_negatives',
                        'precision', 'recall', 'f1_score'])
        for r in results:
            m = r['metrics']
            writer.writerow([
                f"{r['threshold']:.1f}",
                len(r['detections']),
                m['true_positives'],
                m['false_positives'],
                m['false_negatives'],
                f"{m['precision']:.3f}",
                f"{m['recall']:.3f}",
                f"{m['f1_score']:.3f}"
            ])

    print(f"📊 Saved results table: {output_csv}")
    print()
    print("=" * 80)
    print("✅ Local ΔT test complete!")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
