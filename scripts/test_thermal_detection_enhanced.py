#!/usr/bin/env python3
"""
Enhanced thermal detection algorithm with preprocessing pipeline.

Incorporates best practices from thermal infrared small target detection:
- Contrast enhancement via Top-Hat transform and CLAHE
- Bilateral filtering for edge-preserving noise reduction
- Morphological operations for cleaning binary masks
- Multi-scale detection approach

References:
- Logarithmic Image Processing (LIP) framework for contrast enhancement
- Bilateral filtering for thermal noise while preserving penguin edges
- Morphological operations (opening/closing) for mask refinement
"""

import sys
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scipy import ndimage
from skimage import exposure, filters, morphology
from skimage.restoration import denoise_bilateral


def extract_thermal_data(image_path):
    """Extract 16-bit radiometric thermal data from DJI H20T image."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = Path(tmpdir) / "thermal.raw"

        cmd = ["exiftool", "-b", "-ThermalData", str(image_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, check=True)
            raw_path.write_bytes(result.stdout)
        except FileNotFoundError:
            print("ERROR: exiftool not found")
            return None
        except subprocess.CalledProcessError as e:
            print(f"ERROR: exiftool failed: {e.stderr.decode()}")
            return None

        raw = np.fromfile(raw_path, dtype=np.uint16)

        if len(raw) != 640 * 512:
            print(f"ERROR: Wrong data size: {len(raw)}")
            return None

        img_raw = raw.reshape((512, 640))

        # DJI thermal conversion
        celsius = np.right_shift(img_raw, 2).astype(np.float32)
        celsius *= 0.0625
        celsius -= 273.15

        return celsius


def enhance_contrast_tophat(temp_array, disk_size=15):
    """
    Apply morphological Top-Hat transform for contrast enhancement.

    Top-Hat = Original - Opening
    Enhances bright features (penguins) against darker background.
    """
    # Normalize to 0-1 for processing
    temp_norm = (temp_array - temp_array.min()) / (temp_array.max() - temp_array.min())

    # Morphological opening to estimate background
    selem = morphology.disk(disk_size)
    background = morphology.opening(temp_norm, selem)

    # Top-Hat: subtract background to enhance foreground
    enhanced = temp_norm - background

    # Convert back to temperature scale
    enhanced = enhanced * (temp_array.max() - temp_array.min()) + temp_array.min()

    return enhanced


def enhance_contrast_clahe(temp_array, kernel_size=None, clip_limit=0.03):
    """
    Apply Contrast Limited Adaptive Histogram Equalization (CLAHE).

    CLAHE enhances local contrast while limiting noise amplification.
    """
    # Normalize to 0-1
    temp_norm = (temp_array - temp_array.min()) / (temp_array.max() - temp_array.min())

    # Apply CLAHE
    enhanced = exposure.equalize_adapthist(
        temp_norm,
        kernel_size=kernel_size,
        clip_limit=clip_limit
    )

    # Convert back to temperature scale
    enhanced = enhanced * (temp_array.max() - temp_array.min()) + temp_array.min()

    return enhanced


def bilateral_denoise(temp_array, sigma_spatial=2.0, sigma_range=None):
    """
    Apply bilateral filtering for edge-preserving noise reduction.

    Reduces thermal noise while preserving penguin boundaries.
    """
    if sigma_range is None:
        # Auto-set based on temperature std dev
        sigma_range = np.std(temp_array) * 0.1

    # Normalize for processing
    temp_norm = (temp_array - temp_array.min()) / (temp_array.max() - temp_array.min())

    # Apply bilateral filter
    denoised = denoise_bilateral(
        temp_norm,
        sigma_spatial=sigma_spatial,
        sigma_color=sigma_range,
        channel_axis=None
    )

    # Convert back to temperature scale
    denoised = denoised * (temp_array.max() - temp_array.min()) + temp_array.min()

    return denoised


def detect_blobs_enhanced(temp_array, threshold_sigma=0.5, min_area=4, max_area=200,
                         use_tophat=True, use_clahe=False, use_bilateral=True,
                         morphological_cleaning=True):
    """
    Enhanced blob detection with preprocessing pipeline.

    Args:
        temp_array: 2D array of temperatures
        threshold_sigma: Threshold in standard deviations above mean
        min_area: Minimum blob area in pixels
        max_area: Maximum blob area in pixels
        use_tophat: Apply Top-Hat transform
        use_clahe: Apply CLAHE (alternative to Top-Hat)
        use_bilateral: Apply bilateral filtering
        morphological_cleaning: Apply morphological opening/closing to clean masks

    Returns:
        List of detections with centroids and areas
    """
    processed = temp_array.copy()

    # Step 1: Bilateral filtering (noise reduction)
    if use_bilateral:
        processed = bilateral_denoise(processed, sigma_spatial=2.0)

    # Step 2: Contrast enhancement (choose one)
    if use_tophat:
        processed = enhance_contrast_tophat(processed, disk_size=15)
    elif use_clahe:
        processed = enhance_contrast_clahe(processed, clip_limit=0.03)

    # Step 3: Thresholding
    mean_temp = np.mean(processed)
    std_temp = np.std(processed)
    threshold = mean_temp + (threshold_sigma * std_temp)

    binary = processed > threshold

    # Step 4: Morphological cleaning
    if morphological_cleaning:
        # Opening: remove small noise
        binary = morphology.binary_opening(binary, morphology.disk(1))
        # Closing: fill small holes
        binary = morphology.binary_closing(binary, morphology.disk(2))

    # Step 5: Connected components labeling
    labeled, num_features = ndimage.label(binary)

    # Step 6: Extract blob properties
    detections = []
    for i in range(1, num_features + 1):
        blob = (labeled == i)
        area = np.sum(blob)

        if min_area <= area <= max_area:
            coords = np.argwhere(blob)
            centroid_y = np.mean(coords[:, 0])
            centroid_x = np.mean(coords[:, 1])

            detections.append({
                'centroid_x': centroid_x,
                'centroid_y': centroid_y,
                'area': area
            })

    return detections, processed


def load_ground_truth(pixel_coords):
    """Convert pixel coordinates to numpy array."""
    coords = []
    for line in pixel_coords.strip().split('\n'):
        x, y = map(float, line.split(','))
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


def visualize_comparison(temp_raw, temp_processed, ground_truth, detections,
                        metrics, method_name, output_path):
    """Create visualization comparing raw and processed results."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    # Raw thermal image
    ax = axes[0, 0]
    im = ax.imshow(temp_raw, cmap='hot', origin='upper')
    ax.set_title('Raw Thermal Image', fontsize=11, fontweight='bold')
    plt.colorbar(im, ax=ax, label='Temperature (°C)', fraction=0.046)
    ax.axis('off')

    # Processed thermal image
    ax = axes[0, 1]
    im = ax.imshow(temp_processed, cmap='hot', origin='upper')
    ax.set_title(f'Processed ({method_name})', fontsize=11, fontweight='bold')
    plt.colorbar(im, ax=ax, label='Enhanced Temperature', fraction=0.046)
    ax.axis('off')

    # Ground truth overlay
    ax = axes[0, 2]
    ax.imshow(temp_processed, cmap='gray', origin='upper')
    ax.scatter(ground_truth[:, 0], ground_truth[:, 1],
              c='lime', s=100, marker='o', edgecolors='black', linewidths=2,
              label=f'Ground Truth (n={len(ground_truth)})', alpha=0.8)
    ax.set_title('Ground Truth Positions', fontsize=11, fontweight='bold')
    ax.legend(loc='upper right', fontsize=9)
    ax.axis('off')

    # Raw detections
    ax = axes[1, 0]
    ax.imshow(temp_raw, cmap='gray', origin='upper')
    ax.scatter(ground_truth[:, 0], ground_truth[:, 1],
              c='lime', s=100, marker='o', edgecolors='black', linewidths=2,
              label='Ground Truth', alpha=0.7)
    ax.set_title('Raw (Baseline)', fontsize=11, fontweight='bold')
    ax.legend(loc='upper right', fontsize=9)
    ax.axis('off')

    # Enhanced detections
    ax = axes[1, 1]
    ax.imshow(temp_processed, cmap='gray', origin='upper')
    ax.scatter(ground_truth[:, 0], ground_truth[:, 1],
              c='lime', s=100, marker='o', edgecolors='black', linewidths=2,
              label='Ground Truth', alpha=0.7)
    if len(detections) > 0:
        det_coords = np.array([[d['centroid_x'], d['centroid_y']] for d in detections])
        ax.scatter(det_coords[:, 0], det_coords[:, 1],
                  c='red', s=80, marker='x', linewidths=2.5,
                  label=f'Detections (n={len(detections)})')
    ax.set_title(f'{method_name} Detections', fontsize=11, fontweight='bold')
    ax.legend(loc='upper right', fontsize=9)
    ax.axis('off')

    # Metrics table
    ax = axes[1, 2]
    ax.axis('off')

    metrics_text = f"""
{method_name}

True Positives:  {metrics['true_positives']}
False Positives: {metrics['false_positives']}
False Negatives: {metrics['false_negatives']}

Precision: {metrics['precision']:.1%}
Recall:    {metrics['recall']:.1%}
F1 Score:  {metrics['f1_score']:.3f}

Ground Truth: {len(ground_truth)} penguins
"""

    ax.text(0.1, 0.5, metrics_text, fontsize=12, family='monospace',
            verticalalignment='center', transform=ax.transAxes)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"Visualization saved to: {output_path}")


def test_image(image_name, image_path, gt_coords, output_suffix):
    """Test enhanced detection on a single image."""
    ground_truth = load_ground_truth(gt_coords)

    print(f"\n{'='*80}")
    print(f"TESTING IMAGE: {image_name}")
    print(f"{'='*80}")
    print(f"Ground truth penguins: {len(ground_truth)}")

    # Extract thermal data
    print("\nExtracting thermal data...")
    temp_array = extract_thermal_data(image_path)

    if temp_array is None:
        return None

    print(f"Temperature range: {temp_array.min():.2f}°C to {temp_array.max():.2f}°C")
    print(f"Temperature mean: {temp_array.mean():.2f}°C")
    print(f"Temperature std dev: {temp_array.std():.2f}°C")

    # Test different preprocessing combinations
    methods = [
        {
            'name': 'Baseline (No Enhancement)',
            'use_tophat': False,
            'use_clahe': False,
            'use_bilateral': False,
            'morphological_cleaning': False
        },
        {
            'name': 'Bilateral Only',
            'use_tophat': False,
            'use_clahe': False,
            'use_bilateral': True,
            'morphological_cleaning': False
        },
        {
            'name': 'Top-Hat + Bilateral',
            'use_tophat': True,
            'use_clahe': False,
            'use_bilateral': True,
            'morphological_cleaning': True
        },
        {
            'name': 'CLAHE + Bilateral',
            'use_tophat': False,
            'use_clahe': True,
            'use_bilateral': True,
            'morphological_cleaning': True
        },
        {
            'name': 'Top-Hat + Morphological',
            'use_tophat': True,
            'use_clahe': False,
            'use_bilateral': False,
            'morphological_cleaning': True
        }
    ]

    results = []
    thresholds = [0.5, 1.0, 1.5, 2.0]

    for method in methods:
        print(f"\n{'-'*80}")
        print(f"Testing: {method['name']}")
        print(f"{'-'*80}")

        best_f1 = 0
        best_threshold = None
        best_detections = None
        best_metrics = None
        best_processed = None

        for threshold_sigma in thresholds:
            detections, processed = detect_blobs_enhanced(
                temp_array,
                threshold_sigma=threshold_sigma,
                min_area=4,
                max_area=200,
                use_tophat=method['use_tophat'],
                use_clahe=method['use_clahe'],
                use_bilateral=method['use_bilateral'],
                morphological_cleaning=method['morphological_cleaning']
            )

            if len(detections) > 0:
                det_coords = np.array([[d['centroid_x'], d['centroid_y']] for d in detections])
            else:
                det_coords = np.array([]).reshape(0, 2)

            metrics = calculate_metrics(ground_truth, det_coords, distance_threshold=15.0)

            print(f"  σ={threshold_sigma:.1f}: Det={len(detections)}, "
                  f"TP={metrics['true_positives']}, FP={metrics['false_positives']}, "
                  f"P={metrics['precision']:.1%}, R={metrics['recall']:.1%}, "
                  f"F1={metrics['f1_score']:.3f}")

            if metrics['f1_score'] > best_f1:
                best_f1 = metrics['f1_score']
                best_threshold = threshold_sigma
                best_detections = detections
                best_metrics = metrics
                best_processed = processed

        results.append({
            'method': method['name'],
            'f1': best_f1,
            'threshold': best_threshold,
            'metrics': best_metrics,
            'detections': best_detections,
            'processed': best_processed
        })

        print(f"\nBest for {method['name']}: F1={best_f1:.3f} at σ={best_threshold:.1f}")

    # Find overall best method
    best_result = max(results, key=lambda x: x['f1'])

    print(f"\n{'='*80}")
    print("BEST METHOD")
    print(f"{'='*80}")
    print(f"Method: {best_result['method']}")
    print(f"F1 Score: {best_result['f1']:.3f}")
    print(f"Threshold: {best_result['threshold']:.1f}σ")
    print(f"Precision: {best_result['metrics']['precision']:.1%}")
    print(f"Recall: {best_result['metrics']['recall']:.1%}")

    # Create visualization
    output_dir = Path("data/interim/thermal_validation")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"thermal_enhanced_{output_suffix}.png"
    visualize_comparison(
        temp_array,
        best_result['processed'],
        ground_truth,
        best_result['detections'],
        best_result['metrics'],
        best_result['method'],
        output_path
    )

    return results


def main():
    # Test image 0355 (21 penguins)
    image_0355 = Path("data/legacy_ro/penguin-2.0/data/raw/thermal-images/"
                     "DJI_202411061712_006_Create-Area-Route5/"
                     "DJI_20241106194539_0355_T.JPG")

    gt_0355 = """119.3, -402.3
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

    # Test image 0353 (13 penguins)
    image_0353 = Path("data/legacy_ro/penguin-2.0/data/raw/thermal-images/"
                     "DJI_202411061712_006_Create-Area-Route5/"
                     "DJI_20241106194532_0353_T.JPG")

    gt_0353 = """186.9, -306.7
290.6, -435.4
315.6, -426.6
318.5, -412.6
303.1, -403.8
308.2, -392.0
500.9, -496.4
573.7, -339.8
633.2, -364.8
633.8, -303.8
603.7, -223.5
530.3, -232.0
579.0, -180.8"""

    print("="*80)
    print("ENHANCED THERMAL DETECTION VALIDATION")
    print("="*80)
    print("\nTesting preprocessing techniques:")
    print("  - Bilateral filtering (edge-preserving noise reduction)")
    print("  - Top-Hat transform (contrast enhancement)")
    print("  - CLAHE (adaptive histogram equalization)")
    print("  - Morphological operations (mask cleaning)")

    # Test both images
    results_0355 = test_image("DJI_20241106194539_0355_T", image_0355, gt_0355, "0355")
    results_0353 = test_image("DJI_20241106194532_0353_T", image_0353, gt_0353, "0353")

    # Summary comparison
    print(f"\n{'='*80}")
    print("SUMMARY: BASELINE vs ENHANCED")
    print(f"{'='*80}")

    if results_0355 and results_0353:
        baseline_0355 = [r for r in results_0355 if 'Baseline' in r['method']][0]
        best_0355 = max(results_0355, key=lambda x: x['f1'])

        baseline_0353 = [r for r in results_0353 if 'Baseline' in r['method']][0]
        best_0353 = max(results_0353, key=lambda x: x['f1'])

        print("\nImage 0355 (21 penguins):")
        print(f"  Baseline:  F1={baseline_0355['f1']:.3f}")
        print(f"  Enhanced:  F1={best_0355['f1']:.3f} ({best_0355['method']})")
        print(f"  Improvement: {((best_0355['f1'] - baseline_0355['f1']) / baseline_0355['f1'] * 100):.1f}%"
              if baseline_0355['f1'] > 0 else "  Improvement: N/A")

        print("\nImage 0353 (13 penguins):")
        print(f"  Baseline:  F1={baseline_0353['f1']:.3f}")
        print(f"  Enhanced:  F1={best_0353['f1']:.3f} ({best_0353['method']})")
        print(f"  Improvement: {((best_0353['f1'] - baseline_0353['f1']) / baseline_0353['f1'] * 100):.1f}%"
              if baseline_0353['f1'] > 0 else "  Improvement: N/A")

        print(f"\n{'='*80}")
        print("CONCLUSION")
        print(f"{'='*80}")

        avg_baseline = (baseline_0355['f1'] + baseline_0353['f1']) / 2
        avg_enhanced = (best_0355['f1'] + best_0353['f1']) / 2

        if avg_enhanced > avg_baseline * 1.5:
            print("✓ Significant improvement with preprocessing")
            print(f"  Average F1: {avg_baseline:.3f} → {avg_enhanced:.3f}")
        elif avg_enhanced > avg_baseline:
            print("~ Modest improvement with preprocessing")
            print(f"  Average F1: {avg_baseline:.3f} → {avg_enhanced:.3f}")
        else:
            print("✗ Preprocessing did not improve detection")
            print(f"  Average F1: {avg_baseline:.3f} → {avg_enhanced:.3f}")

        if avg_enhanced < 0.1:
            print("\n✓ Thermal detection remains inadequate (F1 < 0.1)")
            print("✓ Confirms documented findings: 0.14°C contrast insufficient")
            print("\nRECOMMENDATION: Continue LiDAR-only approach for counting")

    return 0


if __name__ == "__main__":
    sys.exit(main())
