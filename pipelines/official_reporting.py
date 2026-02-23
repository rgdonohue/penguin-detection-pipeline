"""
Official reporting helpers for LiDAR runs.

This module centralizes:
- AOI block-list registry loading
- AOI integrity checks (CRS + area property consistency)
- lightweight git metadata capture
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from pipelines.aoi_eval import (
    _extract_aois,
    _extract_crs_code,
    _geometry_area_m2,
    _properties_area_m2,
)


def load_aoi_registry(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load AOI registry entries keyed by AOI id.

    Supported shapes:
    - {"aois": {"aoi_id": {...}, ...}}
    - {"aois": [{"aoi_id": "...", ...}, ...]}
    """
    p = Path(path)
    if not p.exists():
        return {}
    obj = json.loads(p.read_text())
    aois = obj.get("aois")
    out: Dict[str, Dict[str, Any]] = {}

    if isinstance(aois, Mapping):
        for aoi_id, entry in aois.items():
            if not isinstance(entry, Mapping):
                continue
            row = dict(entry)
            row.setdefault("aoi_id", str(aoi_id))
            status = str(row.get("status", "UNKNOWN")).upper()
            row["status"] = status
            out[str(aoi_id)] = row
        return out

    if isinstance(aois, list):
        for entry in aois:
            if not isinstance(entry, Mapping):
                continue
            aoi_id = entry.get("aoi_id")
            if aoi_id is None:
                continue
            row = dict(entry)
            status = str(row.get("status", "UNKNOWN")).upper()
            row["status"] = status
            out[str(aoi_id)] = row
    return out


def lookup_aoi_registry_entry(
    registry: Mapping[str, Dict[str, Any]],
    aoi_id: str,
) -> Optional[Dict[str, Any]]:
    """Lookup AOI registry entry by exact id, then lowercase id."""
    if aoi_id in registry:
        return dict(registry[aoi_id])
    lower = aoi_id.lower()
    for key, value in registry.items():
        if str(key).lower() == lower:
            return dict(value)
    return None


def check_aoi_integrity(
    *,
    aoi_geojson: Path,
    expected_crs: Optional[str],
    area_property_tolerance_pct: float = 5.0,
) -> Dict[str, Any]:
    """Check AOI integrity without modifying AOI geometries.

    Returns:
    {
      "aoi_crs": "...",
      "feature_count": int,
      "issues": [...],   # degraders
      "warnings": [...], # non-fatal notes
    }
    """
    obj = json.loads(Path(aoi_geojson).read_text())
    issues: List[str] = []
    warnings: List[str] = []

    aoi_crs = _extract_crs_code(obj)
    if expected_crs and aoi_crs and str(expected_crs) != str(aoi_crs):
        issues.append(
            f"AOI CRS mismatch: expected {expected_crs}, got {aoi_crs}"
        )

    try:
        aois = _extract_aois(obj)
    except Exception as exc:
        return {
            "aoi_crs": aoi_crs,
            "feature_count": 0,
            "issues": [f"AOI parse failure: {exc}"],
            "warnings": warnings,
        }

    for aoi in aois:
        aoi_id = str(aoi.get("aoi_id", "unknown"))
        geom = aoi.get("geometry")
        props = aoi.get("properties", {})
        if not isinstance(geom, Mapping):
            issues.append(f"AOI '{aoi_id}' missing geometry")
            continue
        try:
            area_m2 = float(_geometry_area_m2(geom))
        except Exception as exc:
            issues.append(f"AOI '{aoi_id}' invalid geometry: {exc}")
            continue
        if area_m2 <= 0:
            issues.append(f"AOI '{aoi_id}' has non-positive computed area ({area_m2})")
            continue

        prop_area_m2 = _properties_area_m2(props)
        if prop_area_m2 is None:
            warnings.append(f"AOI '{aoi_id}' missing area_m2/area_ha property")
            continue

        delta_pct = abs(area_m2 - float(prop_area_m2)) / area_m2 * 100.0
        if delta_pct > float(area_property_tolerance_pct):
            issues.append(
                f"AOI '{aoi_id}' area mismatch {delta_pct:.2f}% "
                f"(property={float(prop_area_m2):.3f} m2, computed={area_m2:.3f} m2, "
                f"tolerance={float(area_property_tolerance_pct):.2f}%)"
            )

    return {
        "aoi_crs": aoi_crs,
        "feature_count": len(aois),
        "issues": issues,
        "warnings": warnings,
    }


def collect_git_context(repo_root: Path) -> Dict[str, Optional[str]]:
    """Return git context (best effort, no hard failure)."""
    root = Path(repo_root)
    out: Dict[str, Optional[str]] = {"commit": None, "branch": None, "dirty": None}

    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0:
            out["commit"] = r.stdout.strip() or None
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0:
            out["branch"] = r.stdout.strip() or None
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0:
            out["dirty"] = "true" if bool(r.stdout.strip()) else "false"
    except Exception:
        pass

    return out


def collect_ground_quantile_fallbacks(file_summaries: List[Mapping[str, Any]]) -> List[str]:
    """Return tile paths where p05 ground fell back to min."""
    out: List[str] = []
    for row in file_summaries:
        gq = row.get("ground_quantile")
        if not isinstance(gq, Mapping):
            continue
        if gq.get("fallback_method"):
            out.append(str(row.get("path") or "unknown"))
    return out
