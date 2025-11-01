#!/usr/bin/env python3
"""Compare thermal statistics across multiple frames to check consistency."""

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
    frames = [
        "data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5/DJI_20241106194542_0356_T.JPG",
        "data/legacy_ro/penguin-2.0/data/pilot_frames/DJI_20241106184025_0007_T.JPG",
        "data/legacy_ro/penguin-2.0/data/pilot_frames/DJI_20241106184035_0012_T.JPG",
        "data/legacy_ro/penguin-2.0/data/pilot_frames/DJI_20241106184014_0001_T.JPG",
    ]

    print("=" * 70)
    print("Frame-to-Frame Temperature Comparison")
    print("=" * 70)

    for frame_path in frames:
        p = Path(frame_path)
        if not p.exists():
            print(f"\n❌ {p.name}: NOT FOUND")
            continue

        print(f"\n📷 {p.name}")

        with tempfile.TemporaryDirectory() as tmpdir:
            celsius = extract_thermal_data(p, Path(tmpdir))

        print(f"   Range: {celsius.min():.2f}°C to {celsius.max():.2f}°C")
        print(f"   Mean: {celsius.mean():.2f}°C ± {celsius.std():.2f}°C")
        print(f"   Median: {np.median(celsius):.2f}°C")

        # Temperature distribution
        p25, p75 = np.percentile(celsius, [25, 75])
        print(f"   IQR: {p25:.2f}°C to {p75:.2f}°C")

    print(f"\n" + "=" * 70)
    print("📊 Observations:")
    print("   - If all frames show similar cold temps → calibration issue")
    print("   - If ranges vary significantly → environmental variation")
    print("   - If std ~3°C across frames → consistent weak signal")
    print("=" * 70)


if __name__ == "__main__":
    sys.exit(main())
