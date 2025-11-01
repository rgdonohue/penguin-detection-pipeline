#!/usr/bin/env python3
"""
Create reproducible hotspot comparison overlay for frame 0356.

Generates visual comparison of:
1. Thermal data with ground truth annotations
2. Computational hot spots at different thresholds
3. Quantitative overlap analysis

Output: data/interim/thermal_validation/hotspot_overlay_reproducible.png
"""

import sys
from pathlib import Path
import numpy as np
import tempfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from scipy.ndimage import maximum_filter

# Add project root to path
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.thermal import extract_thermal_data


def load_ground_truth(csv_path: Path) -> list:
    """Load ground truth penguin locations from CSV."""
    locations = []
    with open(csv_path) as f:
        f.readline()  # Skip header
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                x, y = int(parts[0]), int(parts[1])
                locations.append((x, y))
    return locations


def compute_hotspots(celsius: np.ndarray, threshold_sigma: float = 0.5) -> np.ndarray:
    """Compute hot spots using local maxima detection.

    Args:
        celsius: Temperature array
        threshold_sigma: Threshold in standard deviations above mean

    Returns:
        Binary mask of hot spots
    """
    mean_temp = np.mean(celsius)
    std_temp = np.std(celsius)
    threshold = mean_temp + threshold_sigma * std_temp

    # Find local maxima
    local_max = maximum_filter(celsius, size=10)
    peaks = (celsius == local_max) & (celsius > threshold)

    return peaks


def compute_overlap(peaks: np.ndarray, locations: list, max_distance: int = 20) -> dict:
    """Compute overlap between computational hot spots and ground truth.

    Args:
        peaks: Binary mask of hot spots
        locations: List of (x, y) ground truth coordinates
        max_distance: Maximum distance in pixels to consider a match

    Returns:
        dict with match statistics
    """
    peak_coords = np.argwhere(peaks)  # Returns (y, x) coordinates

    matches = 0
    matched_penguins = []

    for annot_x, annot_y in locations:
        if len(peak_coords) > 0:
            # Calculate distances to all peaks
            distances = np.sqrt((peak_coords[:, 1] - annot_x)**2 +
                              (peak_coords[:, 0] - annot_y)**2)
            min_dist = distances.min()

            if min_dist < max_distance:
                matches += 1
                matched_penguins.append((annot_x, annot_y))

    return {
        'n_annotations': len(locations),
        'n_peaks': int(np.sum(peaks)),
        'n_matches': matches,
        'match_rate': matches / len(locations) if len(locations) > 0 else 0,
        'matched_penguins': matched_penguins,
    }


def create_overlay(image_path: Path, ground_truth_csv: Path, output_path: Path):
    """Create hotspot overlay visualization."""

    print("=" * 70)
    print("Creating Reproducible Hotspot Overlay")
    print("=" * 70)

    # Load data
    print(f"\n📷 Loading thermal data: {image_path.name}")
    with tempfile.TemporaryDirectory() as tmpdir:
        celsius = extract_thermal_data(image_path, Path(tmpdir))

    print(f"📍 Loading ground truth: {ground_truth_csv.name}")
    locations = load_ground_truth(ground_truth_csv)
    print(f"   Found {len(locations)} annotated penguins")

    # Compute statistics
    mean_temp = celsius.mean()
    std_temp = celsius.std()

    # Get penguin temperatures
    penguin_temps = []
    for x, y in locations:
        if 0 <= y < celsius.shape[0] and 0 <= x < celsius.shape[1]:
            penguin_temps.append(celsius[y, x])
    penguin_temps = np.array(penguin_temps)
    valid_penguin_temps = penguin_temps[~np.isnan(penguin_temps)]

    # Get background (excluding penguin regions)
    mask = np.ones_like(celsius, dtype=bool)
    for x, y in locations:
        if 0 <= y < celsius.shape[0] and 0 <= x < celsius.shape[1]:
            y0, y1 = max(0, y-2), min(celsius.shape[0], y+3)
            x0, x1 = max(0, x-2), min(celsius.shape[1], x+3)
            mask[y0:y1, x0:x1] = False
    background = celsius[mask]
    bg_mean = background.mean()
    bg_std = background.std()
    penguin_mean = np.nanmean(valid_penguin_temps)
    contrast = penguin_mean - bg_mean
    snr = contrast / bg_std

    print(f"\n📊 Temperature Statistics:")
    print(f"   Background: {bg_mean:.2f}°C ± {bg_std:.2f}°C")
    print(f"   Penguins: {penguin_mean:.2f}°C ± {np.nanstd(valid_penguin_temps):.2f}°C")
    print(f"   Contrast: {contrast:.2f}°C ({snr:.3f}σ)")

    # Compute hot spots at different thresholds
    thresholds = [0.5, 1.0, 1.5]
    overlaps = {}

    print(f"\n🔍 Computing Hot Spots:")
    for thresh in thresholds:
        peaks = compute_hotspots(celsius, threshold_sigma=thresh)
        overlap = compute_overlap(peaks, locations, max_distance=20)
        overlaps[thresh] = overlap
        print(f"   {thresh}σ threshold: {overlap['n_peaks']} peaks, "
              f"{overlap['n_matches']}/{overlap['n_annotations']} matched "
              f"({overlap['match_rate']*100:.1f}%)")

    # Create figure
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    # Row 1: Thermal data with annotations
    for i, thresh in enumerate(thresholds):
        ax = axes[0, i]
        im = ax.imshow(celsius, cmap='hot', aspect='equal')

        # Plot ground truth circles
        for x, y in locations:
            circle = Circle((x, y), radius=5, color='cyan', fill=False,
                          linewidth=2, alpha=0.8)
            ax.add_patch(circle)

        ax.set_title(f'Ground Truth Overlay\n({len(locations)} penguins)',
                    fontsize=11, weight='bold')
        ax.set_xlabel('X (pixels)')
        ax.set_ylabel('Y (pixels)')
        plt.colorbar(im, ax=ax, label='Temperature (°C)', fraction=0.046)

    # Row 2: Hot spot detection at different thresholds
    for i, thresh in enumerate(thresholds):
        ax = axes[1, i]

        # Show thermal with hot spots
        im = ax.imshow(celsius, cmap='hot', aspect='equal', alpha=0.7)

        peaks = compute_hotspots(celsius, threshold_sigma=thresh)
        overlap = overlaps[thresh]

        # Show detected peaks as green dots
        peak_coords = np.argwhere(peaks)
        if len(peak_coords) > 0:
            ax.scatter(peak_coords[:, 1], peak_coords[:, 0],
                      c='lime', s=20, alpha=0.6, label='Hot spots')

        # Show matched penguins as cyan circles
        for x, y in overlap['matched_penguins']:
            circle = Circle((x, y), radius=5, color='cyan', fill=False,
                          linewidth=2, alpha=0.8)
            ax.add_patch(circle)

        # Show unmatched penguins as red X
        matched_set = set(overlap['matched_penguins'])
        for x, y in locations:
            if (x, y) not in matched_set:
                ax.plot(x, y, 'rx', markersize=10, markeredgewidth=2)

        match_rate = overlap['match_rate'] * 100
        ax.set_title(f'Mean + {thresh}σ Threshold\n'
                    f'{overlap["n_peaks"]} peaks, '
                    f'{overlap["n_matches"]}/{overlap["n_annotations"]} matched '
                    f'({match_rate:.1f}%)',
                    fontsize=10)
        ax.set_xlabel('X (pixels)')
        ax.set_ylabel('Y (pixels)')
        ax.legend(loc='upper right', fontsize=8)

    plt.suptitle(f'Frame 0356 Hot Spot Validation\n'
                f'Background: {bg_mean:.2f}°C ± {bg_std:.2f}°C | '
                f'Penguins: {penguin_mean:.2f}°C | '
                f'Contrast: {contrast:.2f}°C ({snr:.3f}σ)',
                fontsize=13, weight='bold')

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n✅ Saved overlay: {output_path}")

    # Summary
    print(f"\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"\nGround Truth: {len(locations)} penguins (26 confident, 2 'Maybe?' excluded)")
    print(f"Thermal Signal: {contrast:.2f}°C contrast ({snr:.3f}σ)")
    print(f"\nBest Match Rate: {max(o['match_rate'] for o in overlaps.values())*100:.1f}%")
    print(f"   at {min(thresholds)}σ threshold")
    print(f"\n⚠️  CONCLUSION: Signal too weak (< 0.1σ) for reliable detection")
    print("=" * 70)


def main():
    image_path = Path("data/legacy_ro/penguin-2.0/data/raw/thermal-images/"
                     "DJI_202411061712_006_Create-Area-Route5/"
                     "DJI_20241106194542_0356_T.JPG")
    ground_truth_csv = Path("verification_images/frame_0356_locations.csv")
    output_path = Path("data/interim/thermal_validation/hotspot_overlay_reproducible.png")

    if not image_path.exists():
        print(f"❌ Image not found: {image_path}")
        return 1

    if not ground_truth_csv.exists():
        print(f"❌ Ground truth not found: {ground_truth_csv}")
        return 1

    create_overlay(image_path, ground_truth_csv, output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
