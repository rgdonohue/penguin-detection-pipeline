"""
LiDAR candidate detection stage.

This module wraps the legacy CLI implementation in ``scripts/run_lidar_hag.py``
so that pipeline orchestration code can depend on a typed ``run()`` entry
point.  The goal is to migrate all stage logic here over time; for now we
shell out to the script to keep behaviour identical while we incrementally
modularise the codebase.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence


@dataclass
class LidarParams:
    """Configuration for the LiDAR height-above-ground stage."""

    data_root: Path
    out_path: Path
    cell_res: float = 0.25
    hag_min: float = 0.2
    hag_max: float = 0.6
    ground_method: str = "min"
    top_method: str = "p95"
    top_zscore_cap: float = 3.0
    connectivity: int = 2
    emit_geojson: bool = False
    min_area_cells: int = 2
    max_area_cells: int = 80
    chunk_size: int = 1_000_000
    plots: bool = False
    emit_csv: bool = False
    csv_path: Optional[Path] = None
    verbose: bool = False
    exclude_dirs: Sequence[str] = field(default_factory=tuple)
    skip_copc: bool = False
    only_las: bool = False
    refine_grid_pct: Optional[float] = None
    refine_size: int = 3
    se_radius_m: float = 0.15
    circularity_min: float = 0.2
    solidity_min: float = 0.7
    watershed: bool = False
    h_maxima: float = 0.05
    min_split_area_cells: int = 12
    border_trim_px: int = 0
    slope_max_deg: Optional[float] = None
    dedupe_radius_m: Optional[float] = None


def run(params: LidarParams) -> Path:
    """Execute the LiDAR stage and return the summary JSON path."""

    script_path = (
        Path(__file__).resolve().parent.parent / "scripts" / "run_lidar_hag.py"
    )
    if not script_path.exists():
        raise FileNotFoundError(f"LiDAR CLI not found at {script_path}")

    params.out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(script_path),
        "--data-root",
        str(params.data_root),
        "--out",
        str(params.out_path),
        "--cell-res",
        str(params.cell_res),
        "--hag-min",
        str(params.hag_min),
        "--hag-max",
        str(params.hag_max),
        "--ground-method",
        params.ground_method,
        "--top-method",
        params.top_method,
        "--top-zscore-cap",
        str(params.top_zscore_cap),
        "--connectivity",
        str(params.connectivity),
        "--min-area-cells",
        str(params.min_area_cells),
        "--max-area-cells",
        str(params.max_area_cells),
        "--chunk-size",
        str(params.chunk_size),
        "--refine-size",
        str(params.refine_size),
        "--se-radius-m",
        str(params.se_radius_m),
        "--circularity-min",
        str(params.circularity_min),
        "--solidity-min",
        str(params.solidity_min),
        "--h-maxima",
        str(params.h_maxima),
        "--min-split-area-cells",
        str(params.min_split_area_cells),
        "--border-trim-px",
        str(params.border_trim_px),
    ]

    if params.emit_geojson:
        cmd.append("--emit-geojson")
    if params.plots:
        cmd.append("--plots")
    if params.emit_csv:
        cmd.append("--emit-csv")
    if params.verbose:
        cmd.append("--verbose")
    if params.skip_copc:
        cmd.append("--skip-copc")
    if params.only_las:
        cmd.append("--only-las")
    if params.watershed:
        cmd.append("--watershed")

    if params.csv_path:
        cmd.extend(["--csv-path", str(params.csv_path)])
    if params.refine_grid_pct is not None:
        cmd.extend(["--refine-grid-pct", str(params.refine_grid_pct)])
    if params.slope_max_deg is not None:
        cmd.extend(["--slope-max-deg", str(params.slope_max_deg)])
    if params.dedupe_radius_m is not None:
        cmd.extend(["--dedupe-radius-m", str(params.dedupe_radius_m)])

    for name in params.exclude_dirs:
        cmd.extend(["--exclude-dir", name])

    subprocess.run(cmd, check=True)
    return params.out_path
