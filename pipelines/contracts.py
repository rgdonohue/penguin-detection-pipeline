"""
Lightweight, versioned-ish contracts for pipeline outputs.

These are *documentation-as-code* constants used to keep summary JSON outputs
interpretable. They intentionally avoid heavy dependencies.
"""

from __future__ import annotations

from typing import Dict


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


