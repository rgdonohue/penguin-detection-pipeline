"""
Parameter profiles for LiDAR runs.

Profiles are *recommendations*, not automatic overrides; the CLI still accepts
explicit flags. The purpose is to make our determinism/validation stance
machine-readable and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class LidarProfile:
    name: str
    ground_method: str
    top_method: str
    notes: str


OFFICIAL_DETERMINISTIC = LidarProfile(
    name="official_deterministic",
    ground_method="p05",
    top_method="max",
    notes=(
        "Official/defensible runs prefer deterministic estimators. "
        "Use max for top surface (deterministic). Treat p95 as experimental "
        "until stability across chunking/order is proven."
    ),
)


def as_policy_dict() -> Dict[str, object]:
    """Small policy block that can be embedded in summary outputs."""
    return {
        "lidar": {
            "official_profile": OFFICIAL_DETERMINISTIC.name,
            "official_ground_method": OFFICIAL_DETERMINISTIC.ground_method,
            "official_top_method": OFFICIAL_DETERMINISTIC.top_method,
            "p95_is_experimental": True,
        }
    }


