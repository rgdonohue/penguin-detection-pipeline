"""
Golden AOI regression guardrail.

The golden harness currently shells out to the stage Makefile targets.  This
module exposes a ``run()`` entry point so that future orchestration can call
into a single location once we finish lifting the guardrail logic out of the
shell scripts.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class GoldenParams:
    """Inputs required for the golden AOI regression suite."""

    intake_root: Path
    processed_root: Path
    qc_root: Path
    manifest_path: Optional[Path] = None
    pytest_args: Optional[list[str]] = None


def run(params: GoldenParams) -> None:
    """Run the golden AOI guardrail suite.

    This is intentionally a *QC/engineering* harness. It validates deterministic
    LiDAR behavior on the golden tile and basic invariants. It does not imply
    thermal calibration or scientifically valid thermal-derived counts.
    """

    args = params.pytest_args or ["-q", "tests/test_golden_aoi.py"]
    cmd = [sys.executable, "-m", "pytest", *args]
    subprocess.run(cmd, check=True)
