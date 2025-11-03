#!/usr/bin/env python3
"""
Investigate thermal calibration and weak signal (0.05σ contrast).

Examines:
1. EXIF calibration parameters (emissivity, reflective temp, atmospheric)
2. ThermalCalibration blob structure
3. Comparison with 8-bit JPEG preview
4. Alternative conversion formulas with corrections
5. Frame-to-frame consistency

Goal: Understand why penguins show only 0.14°C contrast (0.05σ).
"""

import sys
from pathlib import Path
import numpy as np
import subprocess
import tempfile
import json

# Add project root to path
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.thermal import extract_thermal_data


def extract_calibration_params(image_path: Path) -> dict:
    """Extract thermal calibration parameters from EXIF."""
    cmd = ["exiftool", "-j", "-a", "-G1", str(image_path)]
    result = subprocess.run(cmd, capture_output=True, check=True)
    metadata = json.loads(result.stdout)[0]

    # Extract relevant parameters
    params = {
        'emissivity': None,
        'reflection': None,
        'ambient_temp': None,
        'humidity': None,
        'object_distance': None,
        'lrf_distance': None,
    }

    for key, value in metadata.items():
        key_lower = key.lower()
        if 'emissivity' in key_lower:
            params['emissivity'] = value
        elif 'reflection' in key_lower:
            params['reflection'] = value
        elif 'ambienttemperature' in key_lower:
            params['ambient_temp'] = value
        elif 'humidity' in key_lower:
            params['humidity'] = value
        elif 'objectdistance' in key_lower:
            params['object_distance'] = value
        elif 'lrftargetdistance' in key_lower:
            params['lrf_distance'] = value

    return params


def basic_formula(raw_dn: np.ndarray) -> np.ndarray:
    """Current formula: (DN >> 2) * 0.0625 - 273.15"""
    celsius = np.right_shift(raw_dn, 2).astype(np.float32)
    celsius *= 0.0625
    celsius -= 273.15
    return celsius


def formula_with_emissivity(raw_dn: np.ndarray, emissivity: float,
                            reflected_temp_c: float) -> np.ndarray:
    """Apply emissivity correction.

    Formula: T_object = T_measured / ε - ((1 - ε) / ε) * T_reflected
    """
    # Basic conversion
    t_measured = basic_formula(raw_dn)

    # Emissivity correction
    eps = emissivity / 100.0  # Assuming 100 = 1.0
    t_reflected = reflected_temp_c

    t_object = t_measured / eps - ((1 - eps) / eps) * t_reflected
    return t_object


def analyze_jpeg_preview(image_path: Path) -> dict:
    """Analyze 8-bit JPEG preview for visual contrast."""
    from PIL import Image

    # Load JPEG preview
    img = Image.open(image_path).convert('L')
    arr = np.array(img)

    return {
        'shape': arr.shape,
        'dtype': str(arr.dtype),
        'range': (arr.min(), arr.max()),
        'mean': float(arr.mean()),
        'std': float(arr.std()),
    }


def compare_conversions(image_path: Path, ground_truth_csv: Path) -> dict:
    """Compare different conversion formulas against ground truth."""
    # Load ground truth penguin locations
    locations = []
    with open(ground_truth_csv) as f:
        f.readline()  # Skip header
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                x, y = int(parts[0]), int(parts[1])
                locations.append((x, y))

    # Extract calibration parameters
    params = extract_calibration_params(image_path)
    print(f"\n📊 Calibration Parameters:")
    for key, value in params.items():
        print(f"   {key}: {value}")

    # Extract raw DN values
    print(f"\n📷 Extracting raw thermal data...")
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = Path(tmpdir) / "thermal.raw"
        cmd = ["exiftool", "-b", "-ThermalData", str(image_path)]
        result = subprocess.run(cmd, capture_output=True, check=True)
        raw_path.write_bytes(result.stdout)
        raw = np.fromfile(raw_path, dtype=np.uint16)
        img_raw = raw.reshape((512, 640))

    print(f"   Raw DN range: {img_raw.min()} - {img_raw.max()}")
    print(f"   Raw DN mean: {img_raw.mean():.1f} ± {img_raw.std():.1f}")

    # Test different formulas
    results = {}

    # 1. Basic formula (current)
    print(f"\n🔬 Testing Conversion Formulas:")
    print(f"\n1. BASIC FORMULA (current)")
    celsius_basic = basic_formula(img_raw)
    results['basic'] = analyze_contrast(celsius_basic, locations, "Basic")

    # 2. With emissivity correction
    if params['emissivity'] and params['reflection']:
        print(f"\n2. WITH EMISSIVITY CORRECTION")
        # Decode reflection parameter (likely Kelvin * 10 or similar)
        # Common encodings: 230 could be 23.0°C or 230K-273.15=-43.15°C
        reflected_temp = params['reflection'] / 10.0  # Try dividing by 10
        print(f"   Emissivity: {params['emissivity']/100.0:.2f}")
        print(f"   Reflected temp (guess): {reflected_temp:.1f}°C")

        celsius_emiss = formula_with_emissivity(
            img_raw,
            params['emissivity'],
            reflected_temp
        )
        results['emissivity'] = analyze_contrast(celsius_emiss, locations, "Emissivity")

    # 3. Alternative reflection interpretation
    if params['reflection']:
        print(f"\n3. ALTERNATIVE REFLECTION (as Kelvin)")
        reflected_kelvin = params['reflection'] - 273.15
        print(f"   Reflected temp (Kelvin interpretation): {reflected_kelvin:.1f}°C")

        celsius_alt = formula_with_emissivity(
            img_raw,
            params['emissivity'],
            reflected_kelvin
        )
        results['alt_reflection'] = analyze_contrast(celsius_alt, locations, "Alt Reflection")

    # 4. Analyze 8-bit JPEG preview
    print(f"\n4. JPEG PREVIEW ANALYSIS")
    jpeg_stats = analyze_jpeg_preview(image_path)
    print(f"   8-bit range: {jpeg_stats['range'][0]} - {jpeg_stats['range'][1]}")
    print(f"   8-bit mean: {jpeg_stats['mean']:.1f} ± {jpeg_stats['std']:.1f}")
    results['jpeg'] = jpeg_stats

    return results


def analyze_contrast(celsius: np.ndarray, locations: list, label: str) -> dict:
    """Analyze thermal contrast between penguins and background."""
    # Get penguin temperatures
    penguin_temps = []
    for x, y in locations:
        if 0 <= y < celsius.shape[0] and 0 <= x < celsius.shape[1]:
            penguin_temps.append(celsius[y, x])

    penguin_temps = np.array(penguin_temps)
    valid = penguin_temps[~np.isnan(penguin_temps)]

    # Get background (excluding penguin regions)
    mask = np.ones_like(celsius, dtype=bool)
    for x, y in locations:
        if 0 <= y < celsius.shape[0] and 0 <= x < celsius.shape[1]:
            y0, y1 = max(0, y-2), min(celsius.shape[0], y+3)
            x0, x1 = max(0, x-2), min(celsius.shape[1], x+3)
            mask[y0:y1, x0:x1] = False

    background = celsius[mask]

    # Calculate statistics
    penguin_mean = np.nanmean(valid)
    penguin_std = np.nanstd(valid)
    bg_mean = np.mean(background)
    bg_std = np.std(background)
    contrast = penguin_mean - bg_mean
    snr = contrast / bg_std if bg_std > 0 else 0

    print(f"   Range: {celsius.min():.2f}°C to {celsius.max():.2f}°C")
    print(f"   Background: {bg_mean:.2f}°C ± {bg_std:.2f}°C")
    print(f"   Penguins: {penguin_mean:.2f}°C ± {penguin_std:.2f}°C")
    print(f"   Contrast: {contrast:.2f}°C ({snr:.2f}σ)")

    return {
        'range': (float(celsius.min()), float(celsius.max())),
        'bg_mean': float(bg_mean),
        'bg_std': float(bg_std),
        'penguin_mean': float(penguin_mean),
        'penguin_std': float(penguin_std),
        'contrast': float(contrast),
        'snr': float(snr),
    }


def main():
    print("=" * 70)
    print("Thermal Calibration Investigation")
    print("=" * 70)

    # Frame 0356 (validated)
    image_path = Path("data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5/DJI_20241106194542_0356_T.JPG")
    ground_truth_csv = Path("verification_images/frame_0356_locations.csv")

    if not image_path.exists():
        print(f"❌ Image not found: {image_path}")
        return 1

    if not ground_truth_csv.exists():
        print(f"❌ Ground truth not found: {ground_truth_csv}")
        return 1

    print(f"\n📁 Test Image: {image_path.name}")
    print(f"📍 Ground Truth: 26 verified penguins")

    # Run comparison
    results = compare_conversions(image_path, ground_truth_csv)

    # Summary
    print(f"\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"\n🎯 Best SNR: ", end="")
    best_snr = 0
    best_method = None
    for method, data in results.items():
        if method != 'jpeg' and 'snr' in data:
            if data['snr'] > best_snr:
                best_snr = data['snr']
                best_method = method

    if best_method:
        print(f"{best_method} ({best_snr:.2f}σ)")
        if best_snr < 0.5:
            print(f"   ⚠️  Still very weak signal (< 0.5σ)")
        elif best_snr < 1.0:
            print(f"   ⚠️  Marginal signal (0.5-1.0σ)")
        elif best_snr < 2.0:
            print(f"   ✅ Usable signal (1.0-2.0σ)")
        else:
            print(f"   ✅ Good signal (> 2.0σ)")

    print(f"\n📋 Recommendations:")
    if best_snr < 0.5:
        print(f"   1. Check if camera thermal mode was set correctly")
        print(f"   2. Verify emissivity setting (should be ~0.98 for biological)")
        print(f"   3. Decode ThermalCalibration blob (32KB) for proper formula")
        print(f"   4. Consider environmental factors (cold day = low contrast)")
        print(f"   5. Check other frames for consistency")
    else:
        print(f"   1. Use {best_method} formula in production")
        print(f"   2. Validate on additional frames")
        print(f"   3. Proceed with fusion analysis")

    return 0


if __name__ == "__main__":
    sys.exit(main())
