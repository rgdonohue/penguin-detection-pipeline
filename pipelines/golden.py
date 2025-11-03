"""
Golden AOI regression guardrail.

The golden harness currently shells out to the stage Makefile targets.  This
module exposes a ``run()`` entry point so that future orchestration can call
into a single location once we finish lifting the guardrail logic out of the
shell scripts.
"""

from __future__ import annotations

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


def run(params: GoldenParams) -> None:
    """Placeholder golden harness."""

    raise NotImplementedError(
        "Golden harness not yet ported into Python. Continue using `make golden` "
        "until the guardrail suite is migrated."
    )
