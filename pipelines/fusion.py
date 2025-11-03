"""
Fusion stage (thermal + LiDAR reconciliation).

The fusion logic still lives in ad-hoc notebooks and shell commands.  This
module provides a typed placeholder so downstream orchestration code can
depend on a stable ``run()`` entry point once the implementation is migrated.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class FusionParams:
    """Inputs and outputs required to produce the fusion rollup."""

    lidar_summary: Path
    thermal_summary: Path
    out_path: Path
    qc_panel: Optional[Path] = None


def run(params: FusionParams) -> Path:
    """Placeholder fusion pipeline; raise until the stage is implemented."""

    raise NotImplementedError(
        "Fusion stage not yet modularised. Use `make fusion` while the pipeline "
        "implementation is migrated into pipelines/fusion.py."
    )
