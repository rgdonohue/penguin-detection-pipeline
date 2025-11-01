#!/usr/bin/env python3
"""
Validate DJI H20T 16-bit thermal extraction against ground truth.

Overlays verified penguin locations from PDF ground truth onto extracted
thermal data to confirm radiometric extraction is working correctly.

Usage:
    python scripts/validate_thermal_extraction.py \
        --thermal-image data/legacy_ro/penguin-2.0/.../DJI_20241106194542_0356_T.JPG \
        --ground-truth verification_images/frame_0356_locations.csv \
        --output data/interim/thermal_validation/

Ground truth CSV format:
    x,y,label
    320,256,penguin
    ...

Where x,y are pixel coordinates in the original 640×512 thermal frame.
"""

import sys
import argparse
from pathlib import Path
import numpy as np
import subprocess
import tempfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle


def extract_thermal_data(image_path: Path, temp_dir: Path) -> np.ndarray:
    """Extract 16-bit radiometric thermal data from DJI RJPEG.

    Args:
        image_path: Path to DJI thermal JPEG
        temp_dir: Directory to store temporary raw file

    Returns:
        Temperature array (512, 640) in Celsius

    Raises:
        RuntimeError: If extraction fails or data size is wrong
    """
    raw_path = temp_dir / "thermal.raw"

    # Extract ThermalData blob using exiftool
    cmd = ["exiftool", "-b", "-ThermalData", str(image_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, check=True)
        raw_path.write_bytes(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"exiftool failed: {e.stderr.decode()}")

    # Load as 16-bit unsigned integers
    raw = np.fromfile(raw_path, dtype=np.uint16)

    expected_size = 640 * 512
    if len(raw) != expected_size:
        raise RuntimeError(
            f"ThermalData size mismatch: got {len(raw)}, expected {expected_size}"
        )

    # Reshape to image dimensions (height, width)
    img_raw = raw.reshape((512, 640))

    # DJI thermal conversion formula
    # Source: https://github.com/uav4geo/Thermal-Tools
    # Formula: (DN >> 2) * 0.0625 - 273.15
    celsius = np.right_shift(img_raw, 2).astype(np.float32)
    celsius *= 0.0625  # = 1/16
    celsius -= 273.15   # Kelvin to Celsius

    return celsius


def load_ground_truth(csv_path: Path) -> dict:
    """Load ground truth penguin locations from CSV.

    Returns:
        dict with keys:
            'locations': list of (x, y) tuples
            'labels': list of label strings
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {csv_path}")

    locations = []
    labels = []

    with open(csv_path) as f:
        header = f.readline().strip()
        if not header.startswith("x,y"):
            raise ValueError(f"Invalid CSV header: {header}")

        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                x, y = int(parts[0]), int(parts[1])
                label = parts[2] if len(parts) > 2 else "penguin"
                locations.append((x, y))
                labels.append(label)

    return {
        'locations': locations,
        'labels': labels,
        'count': len(locations)
    }


def analyze_ground_truth_temps(celsius: np.ndarray, locations: list) -> dict:
    """Extract temperature statistics at ground truth penguin locations.

    Args:
        celsius: Temperature array (512, 640)
        locations: List of (x, y) pixel coordinates

    Returns:
        dict with temperature statistics
    """
    temps = []
    for x, y in locations:
        if 0 <= y < celsius.shape[0] and 0 <= x < celsius.shape[1]:
            temps.append(celsius[y, x])
        else:
            temps.append(np.nan)

    temps = np.array(temps)
    valid_temps = temps[~np.isnan(temps)]

    # Get background statistics (excluding penguin locations)
    mask = np.ones_like(celsius, dtype=bool)
    for x, y in locations:
        if 0 <= y < celsius.shape[0] and 0 <= x < celsius.shape[1]:
            # Exclude 5×5 region around each penguin
            y0, y1 = max(0, y-2), min(celsius.shape[0], y+3)
            x0, x1 = max(0, x-2), min(celsius.shape[1], x+3)
            mask[y0:y1, x0:x1] = False

    background = celsius[mask]

    return {
        'penguin_temps': temps,
        'penguin_mean': float(np.nanmean(valid_temps)),
        'penguin_std': float(np.nanstd(valid_temps)),
        'penguin_min': float(np.nanmin(valid_temps)),
        'penguin_max': float(np.nanmax(valid_temps)),
        'background_mean': float(np.mean(background)),
        'background_std': float(np.std(background)),
        'contrast': float(np.nanmean(valid_temps) - np.mean(background)),
        'n_valid': int(np.sum(~np.isnan(temps))),
        'n_total': len(temps)
    }


def visualize_validation(
    celsius: np.ndarray,
    locations: list,
    labels: list,
    stats: dict,
    output_path: Path
):
    """Create validation visualization showing thermal data + ground truth.

    Args:
        celsius: Temperature array (512, 640)
        locations: List of (x, y) penguin coordinates
        labels: List of label strings
        stats: Temperature statistics dict
        output_path: Path to save figure
    """
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))

    # 1. Raw thermal with ground truth overlay
    ax = axes[0, 0]
    im = ax.imshow(celsius, cmap='hot', aspect='equal')
    for (x, y), label in zip(locations, labels):
        circle = Circle((x, y), radius=3, color='cyan', fill=False, linewidth=2)
        ax.add_patch(circle)
        ax.plot(x, y, 'c+', markersize=8, markeredgewidth=2)
    ax.set_title(f'Thermal + Ground Truth ({len(locations)} verified penguins)', fontsize=12)
    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')
    plt.colorbar(im, ax=ax, label='Temperature (°C)')

    # 2. Zoomed thermal on central penguins (if locations available)
    ax = axes[0, 1]
    if locations:
        # Find center region with most penguins
        xs = [loc[0] for loc in locations]
        ys = [loc[1] for loc in locations]
        cx, cy = int(np.median(xs)), int(np.median(ys))

        # 100×100 pixel window centered on median location
        x0, x1 = max(0, cx-50), min(640, cx+50)
        y0, y1 = max(0, cy-50), min(512, cy+50)

        im = ax.imshow(celsius[y0:y1, x0:x1], cmap='hot', aspect='equal',
                      extent=[x0, x1, y1, y0])

        for (x, y), label in zip(locations, labels):
            if x0 <= x < x1 and y0 <= y < y1:
                circle = Circle((x, y), radius=3, color='cyan', fill=False, linewidth=2)
                ax.add_patch(circle)
                ax.plot(x, y, 'c+', markersize=10, markeredgewidth=2)

        ax.set_title(f'Zoomed Region (center: {cx},{cy})', fontsize=12)
        ax.set_xlabel('X (pixels)')
        ax.set_ylabel('Y (pixels)')
        plt.colorbar(im, ax=ax, label='Temperature (°C)')
    else:
        ax.text(0.5, 0.5, 'No ground truth locations', ha='center', va='center')
        ax.axis('off')

    # 3. Temperature distribution histogram
    ax = axes[1, 0]
    ax.hist(celsius.ravel(), bins=100, alpha=0.7, label='All pixels', color='gray', edgecolor='black')
    if stats['n_valid'] > 0:
        penguin_temps = stats['penguin_temps'][~np.isnan(stats['penguin_temps'])]
        ax.hist(penguin_temps, bins=20, alpha=0.9, label='Penguin pixels', color='red', edgecolor='darkred')

    ax.axvline(stats['background_mean'], color='blue', linestyle='--', linewidth=2,
               label=f"Background mean: {stats['background_mean']:.2f}°C")
    if stats['n_valid'] > 0:
        ax.axvline(stats['penguin_mean'], color='red', linestyle='--', linewidth=2,
                   label=f"Penguin mean: {stats['penguin_mean']:.2f}°C")

    ax.set_xlabel('Temperature (°C)', fontsize=11)
    ax.set_ylabel('Pixel count', fontsize=11)
    ax.set_title('Temperature Distribution', fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    # 4. Statistics summary
    ax = axes[1, 1]
    ax.axis('off')

    summary_text = f"""
VALIDATION SUMMARY

Ground Truth:
  • Verified penguins: {len(locations)}
  • Valid locations: {stats['n_valid']} / {stats['n_total']}

Temperature Statistics:
  • Image range: {celsius.min():.2f}°C to {celsius.max():.2f}°C
  • Image mean: {celsius.mean():.2f}°C ± {celsius.std():.2f}°C

  • Background mean: {stats['background_mean']:.2f}°C ± {stats['background_std']:.2f}°C
  • Penguin mean: {stats['penguin_mean']:.2f}°C ± {stats['penguin_std']:.2f}°C
  • Penguin range: {stats['penguin_min']:.2f}°C to {stats['penguin_max']:.2f}°C

  • Thermal contrast: {stats['contrast']:.2f}°C
  • Contrast ratio: {stats['contrast'] / stats['background_std']:.2f}σ

Detection Assessment:
  • Expected: Penguins should be WARMER than background
  • Observed: Contrast = {stats['contrast']:.2f}°C
  • Status: {'✅ POSITIVE' if stats['contrast'] > 0 else '❌ NEGATIVE'}

  • Typical penguin surface temp: 25-30°C (literature)
  • Observed penguin temp: {stats['penguin_mean']:.2f}°C
  • Offset from expected: ~{25 - stats['penguin_mean']:.1f}°C

Notes:
  • Cyan circles/crosses mark verified penguin locations
  • Red histogram shows temperature at penguin pixels
  • Positive contrast confirms radiometric extraction works
  • Large offset suggests calibration refinement needed
"""

    ax.text(0.05, 0.95, summary_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✅ Saved validation figure: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate 16-bit thermal extraction against ground truth"
    )
    parser.add_argument(
        "--thermal-image",
        type=Path,
        required=True,
        help="DJI thermal JPEG image path"
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        required=True,
        help="CSV file with penguin locations (x,y,label)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/interim/thermal_validation"),
        help="Output directory for validation results"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("DJI H20T Thermal Extraction Validation")
    print("=" * 60)
    print()

    # Extract thermal data
    print(f"📷 Extracting thermal data from: {args.thermal_image.name}")
    with tempfile.TemporaryDirectory() as tmpdir:
        celsius = extract_thermal_data(args.thermal_image, Path(tmpdir))

    print(f"✅ Extracted 16-bit thermal data:")
    print(f"   Shape: {celsius.shape}")
    print(f"   Range: {celsius.min():.2f}°C to {celsius.max():.2f}°C")
    print(f"   Mean: {celsius.mean():.2f}°C ± {celsius.std():.2f}°C")
    print()

    # Load ground truth
    print(f"📍 Loading ground truth from: {args.ground_truth.name}")
    gt = load_ground_truth(args.ground_truth)
    print(f"✅ Loaded {gt['count']} verified penguin locations")
    print()

    # Analyze temperatures at penguin locations
    print("🔬 Analyzing temperature at verified penguin locations...")
    stats = analyze_ground_truth_temps(celsius, gt['locations'])

    print(f"   Background: {stats['background_mean']:.2f}°C ± {stats['background_std']:.2f}°C")
    print(f"   Penguins:   {stats['penguin_mean']:.2f}°C ± {stats['penguin_std']:.2f}°C")
    print(f"   Contrast:   {stats['contrast']:.2f}°C ({stats['contrast']/stats['background_std']:.2f}σ)")
    print()

    # Assessment
    if stats['contrast'] > 0:
        print("✅ POSITIVE CONTRAST: Penguins are warmer than background")
        print("   → Radiometric extraction is working correctly!")
    else:
        print("❌ NEGATIVE CONTRAST: Penguins are cooler than background")
        print("   → Possible calibration or location mismatch issue")
    print()

    # Visualize
    output_fig = args.output / f"{args.thermal_image.stem}_validation.png"
    print(f"📊 Creating validation visualization...")
    visualize_validation(celsius, gt['locations'], gt['labels'], stats, output_fig)

    # Save temperature array
    output_npy = args.output / f"{args.thermal_image.stem}_celsius.npy"
    np.save(output_npy, celsius)
    print(f"💾 Saved temperature array: {output_npy}")
    print()

    # Save statistics
    output_stats = args.output / f"{args.thermal_image.stem}_stats.txt"
    with open(output_stats, 'w') as f:
        f.write("DJI H20T Thermal Extraction Validation\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Image: {args.thermal_image.name}\n")
        f.write(f"Ground truth: {gt['count']} verified penguins\n\n")
        f.write("Temperature Statistics:\n")
        f.write(f"  Image range: {celsius.min():.2f}°C to {celsius.max():.2f}°C\n")
        f.write(f"  Background:  {stats['background_mean']:.2f}°C ± {stats['background_std']:.2f}°C\n")
        f.write(f"  Penguins:    {stats['penguin_mean']:.2f}°C ± {stats['penguin_std']:.2f}°C\n")
        f.write(f"  Contrast:    {stats['contrast']:.2f}°C ({stats['contrast']/stats['background_std']:.2f}σ)\n\n")
        f.write("Assessment:\n")
        if stats['contrast'] > 0:
            f.write("  ✅ Positive contrast confirms radiometric extraction works\n")
            f.write(f"  ⚠️  Calibration offset: ~{25 - stats['penguin_mean']:.1f}°C from expected\n")
        else:
            f.write("  ❌ Negative contrast suggests calibration or mismatch issue\n")

    print(f"📄 Saved statistics: {output_stats}")
    print()
    print("=" * 60)
    print("✅ Validation complete!")
    print("=" * 60)

    return 0 if stats['contrast'] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
