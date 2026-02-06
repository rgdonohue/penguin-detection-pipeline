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
    # Watershed parameters (optional — None means "use CLI default")
    h_maxima_h: Optional[float] = None
    min_split_area_cells: Optional[int] = None
    watershed_merge_threshold: Optional[float] = None


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


# ---------------------------------------------------------------------------
# Sensor-specific profiles (Argentina 2025)
# ---------------------------------------------------------------------------

DJI_L2_CALETA = LidarProfile(
    name="dji_l2_caleta",
    ground_method="p05",
    top_method="max",
    notes="DJI L2 sensor at Caleta sites (Tiny Island, Small Island).",
    h_maxima_h=0.05,
    min_split_area_cells=12,
    watershed_merge_threshold=1.5,
)

TRUEVIEW_515_SAN_LORENZO = LidarProfile(
    name="trueview_515_san_lorenzo",
    ground_method="p05",
    top_method="max",
    notes="TrueView 515 sensor at San Lorenzo sites.",
    h_maxima_h=0.05,
    min_split_area_cells=15,
    watershed_merge_threshold=1.5,
)

# Lookup table for --profile CLI arg
SENSOR_PROFILES: Dict[str, LidarProfile] = {
    "dji_l2_caleta": DJI_L2_CALETA,
    "trueview_515_san_lorenzo": TRUEVIEW_515_SAN_LORENZO,
}


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
