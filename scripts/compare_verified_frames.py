#!/usr/bin/env python3
"""Compare temperature statistics across verified frames 0353-0359."""

import sys
from pathlib import Path
import numpy as np
import tempfile

# Add project root to path
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.thermal import extract_thermal_data


def main():
    base_dir = Path("data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5")

    frames = [
        base_dir / f"DJI_20241106194{timestamp}_{num:04d}_T.JPG"
        for num, timestamp in [
            (353, "532"),
            (354, "535"),
            (355, "539"),
            (356, "542"),
            (357, "546"),
            (358, "549"),
            (359, "553"),
        ]
    ]

    print("=" * 70)
    print("Verified Frames 0353-0359 Temperature Comparison")
    print("All captured within 21 seconds (19:45:32 - 19:45:53)")
    print("=" * 70)

    stats = []
    for frame_path in frames:
        if not frame_path.exists():
            print(f"\n❌ {frame_path.name}: NOT FOUND")
            continue

        print(f"\n📷 {frame_path.name}")
        # Extract timestamp from filename
        timestamp = frame_path.stem.split("_")[1]
        time_str = f"{timestamp[0:2]}:{timestamp[2:4]}:{timestamp[4:6]}"
        print(f"   Time: {time_str}")

        with tempfile.TemporaryDirectory() as tmpdir:
            celsius = extract_thermal_data(frame_path, Path(tmpdir))

        min_temp = celsius.min()
        max_temp = celsius.max()
        mean_temp = celsius.mean()
        std_temp = celsius.std()
        median_temp = np.median(celsius)

        print(f"   Range: {min_temp:.2f}°C to {max_temp:.2f}°C")
        print(f"   Mean: {mean_temp:.2f}°C ± {std_temp:.2f}°C")
        print(f"   Median: {median_temp:.2f}°C")

        stats.append({
            'frame': frame_path.stem.split("_")[-2],
            'time': time_str,
            'min': min_temp,
            'max': max_temp,
            'mean': mean_temp,
            'std': std_temp,
            'median': median_temp,
        })

    # Summary statistics
    if stats:
        print(f"\n" + "=" * 70)
        print("SUMMARY ACROSS VERIFIED FRAMES")
        print("=" * 70)

        means = [s['mean'] for s in stats]
        stds = [s['std'] for s in stats]

        print(f"\nMean temperatures:")
        print(f"   Range: {min(means):.2f}°C to {max(means):.2f}°C")
        print(f"   Variation: {max(means) - min(means):.2f}°C")
        print(f"   Average std dev: {np.mean(stds):.2f}°C")

        print(f"\n📊 Interpretation:")
        temp_variation = max(means) - min(means)
        avg_std = np.mean(stds)

        if temp_variation < avg_std:
            print(f"   ✅ Frame-to-frame variation ({temp_variation:.2f}°C) < avg std dev ({avg_std:.2f}°C)")
            print(f"      Temperatures are CONSISTENT across the sequence")
        else:
            print(f"   ⚠️  Frame-to-frame variation ({temp_variation:.2f}°C) > avg std dev ({avg_std:.2f}°C)")
            print(f"      Some temperature drift within sequence")


if __name__ == "__main__":
    sys.exit(main())
