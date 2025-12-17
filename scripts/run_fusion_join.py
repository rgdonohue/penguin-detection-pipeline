#!/usr/bin/env python3
"""
Run the fusion stage (LiDAR + thermal reconciliation).

This is a thin CLI wrapper over `pipelines.fusion.run()`.

Important: this script assumes both input summaries already include detections
with `x`/`y` coordinates in the same projected CRS (meters). It does not
georeference thermal pixel detections.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Ensure the repository root is importable when running as a script.
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipelines.fusion import FusionParams, run


def main() -> int:
    parser = argparse.ArgumentParser(description="Fuse LiDAR and thermal detections via spatial join")
    parser.add_argument("--lidar-summary", type=Path, required=True, help="LiDAR detections summary JSON path")
    parser.add_argument("--thermal-summary", type=Path, required=True, help="Thermal detections summary JSON path")
    parser.add_argument("--out", type=Path, required=True, help="Output fusion rollup JSON path")
    parser.add_argument("--match-radius-m", type=float, default=0.5, help="Matching radius in meters (default: 0.5)")
    args = parser.parse_args()

    run(
        FusionParams(
            lidar_summary=args.lidar_summary,
            thermal_summary=args.thermal_summary,
            out_path=args.out,
            match_radius_m=float(args.match_radius_m),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
