"""
Lightweight, versioned-ish contracts for pipeline outputs.

These are *documentation-as-code* constants used to keep summary JSON outputs
interpretable. They intentionally avoid heavy dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple


LIDAR_CANDIDATES_PURPOSE = "lidar_candidates"
LIDAR_CANDIDATES_SEMANTICS = (
    "Each detection is a centroid of a connected-component blob in a HAG threshold mask. "
    "It is a candidate for review/fusion and is NOT guaranteed to represent a single penguin."
)

LIDAR_CANDIDATES_CONTRACT: Dict[str, object] = {
    "schema_version": "1",
    "purpose": LIDAR_CANDIDATES_PURPOSE,
    "semantic_unit": "candidate",
    "represents": "blob_centroid",
    "not_guaranteed_to_represent": "individual_penguin",
    "notes": LIDAR_CANDIDATES_SEMANTICS,
}

DTM_QUALITY_CONTRACT: Dict[str, object] = {
    "schema_version": "1",
    "purpose": "dtm_quality",
    "description": (
        "DTM quality metrics for a LiDAR tile: point count statistics, "
        "local roughness, and quality flags (HIGH_EMPTY_CELLS, LOW_SUPPORT, HIGH_ROUGHNESS)."
    ),
}


# ---------------------------------------------------------------------------
# Required Artifacts Contract
# ---------------------------------------------------------------------------

# Defines the expected outputs from a LiDAR pipeline run.
# Each artifact is (filename_pattern, required, description, content_check).
# content_check is optional: if provided, it's a key that must exist in the JSON.
REQUIRED_ARTIFACTS: List[Tuple[str, bool, str, Optional[str]]] = [
    # Core outputs (always required)
    # Note: summary JSON is validated by content (must have "purpose": "lidar_candidates")
    ("_summary_json_", True, "Summary JSON with detection counts and metadata", "purpose"),
    ("config.effective.json", True, "Effective configuration artifact for reproducibility", None),
    ("provenance_lidar.json", True, "Provenance tracking with timestamps and parameters", None),

    # Optional outputs (only validated when corresponding flags are set)
    ("lidar_hag_geojson/*.geojson", False, "Per-tile GeoJSON detections (--emit-geojson)", None),
    ("lidar_hag_plots/*.png", False, "QC visualization plots (--plots)", None),
    ("lidar_hag_dtm/*.tif", False, "Ground DTM GeoTIFFs (--emit-dtm)", None),
    ("lidar_hag_detections*.csv", False, "Aggregated detections CSV (--emit-csv)", None),
    ("*.gpkg", False, "GeoPackage output (--emit-gpkg)", None),
]


def _find_summary_json(output_dir: Path) -> Optional[Path]:
    """Find the summary JSON file by checking content for 'purpose': 'lidar_candidates'."""
    import json

    for json_file in output_dir.glob("*.json"):
        # Skip known non-summary files
        if json_file.name in ("config.effective.json", "provenance_lidar.json", "timings.json"):
            continue
        if "_deduped" in json_file.name:
            continue
        try:
            with open(json_file) as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("purpose") == "lidar_candidates":
                return json_file
        except (json.JSONDecodeError, IOError):
            continue
    return None


def validate_artifact_contract(
    output_dir: Path,
    emit_geojson: bool = False,
    emit_plots: bool = False,
    emit_dtm: bool = False,
    emit_csv: bool = False,
    emit_gpkg: bool = False,
) -> Tuple[bool, List[str]]:
    """Validate that a pipeline run produced the expected artifacts.

    Args:
        output_dir: Directory containing pipeline outputs
        emit_geojson: Whether GeoJSON output was requested
        emit_plots: Whether plot output was requested
        emit_dtm: Whether DTM output was requested
        emit_csv: Whether CSV output was requested
        emit_gpkg: Whether GeoPackage output was requested

    Returns:
        Tuple of (is_valid, list_of_errors).
        is_valid is True if all required artifacts are present.
        list_of_errors contains descriptions of missing artifacts.
    """
    errors: List[str] = []

    # Check required artifacts
    for item in REQUIRED_ARTIFACTS:
        pattern, required, description = item[0], item[1], item[2]
        content_check = item[3] if len(item) > 3 else None

        # Determine if this artifact should be checked
        should_check = required
        if "geojson" in pattern.lower():
            should_check = emit_geojson
        elif "plots" in pattern.lower():
            should_check = emit_plots
        elif "dtm" in pattern.lower():
            should_check = emit_dtm
        elif "csv" in pattern.lower():
            should_check = emit_csv
        elif pattern == "*.gpkg":
            should_check = emit_gpkg

        if not should_check:
            continue

        # Special handling for summary JSON (content-based validation)
        if pattern == "_summary_json_":
            summary_json = _find_summary_json(output_dir)
            if summary_json is None:
                errors.append(f"Missing artifact: Summary JSON with 'purpose': 'lidar_candidates' ({description})")
            continue

        # Check for presence of artifact
        matches = list(output_dir.glob(pattern))
        if not matches:
            errors.append(f"Missing artifact: {pattern} ({description})")

    return (len(errors) == 0, errors)


def get_artifact_summary(output_dir: Path) -> Dict[str, object]:
    """Generate a summary of artifacts present in an output directory.

    Returns a dict mapping artifact type to presence/count information.
    """
    summary: Dict[str, object] = {
        "output_dir": str(output_dir),
        "artifacts": {},
    }

    artifact_checks = [
        ("summary_json", "*.json", "Summary JSON files"),
        ("effective_config", "config.effective.json", "Effective configuration"),
        ("provenance", "provenance_lidar.json", "Provenance file"),
        ("geojson", "lidar_hag_geojson/*.geojson", "GeoJSON detections"),
        ("plots", "lidar_hag_plots/*.png", "QC plots"),
        ("dtm", "lidar_hag_dtm/*.tif", "DTM GeoTIFFs"),
        ("csv", "*.csv", "CSV outputs"),
        ("gpkg", "*.gpkg", "GeoPackage outputs"),
    ]

    for key, pattern, description in artifact_checks:
        matches = list(output_dir.glob(pattern))
        summary["artifacts"][key] = {
            "pattern": pattern,
            "description": description,
            "present": len(matches) > 0,
            "count": len(matches),
            "files": [str(m.name) for m in matches[:10]],  # Limit to first 10
        }

    return summary


