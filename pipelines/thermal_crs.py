"""
Thermal → CRS helpers.

This module intentionally avoids GDAL/rasterio dependencies. It provides small,
testable utilities to convert pixel detections into projected CRS coordinates
using a GDAL-style geotransform, which is the standard way orthorectified
GeoTIFFs encode pixel→world mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple


Geotransform = Tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class CrsDetections:
    """A minimal, fusion-ready detection set in projected CRS coordinates."""

    crs: str
    detections: List[dict]
    schema_version: str = "1"
    purpose: str = "qc_alignment"
    temperature_calibrated: bool = False


def apply_geotransform(gt: Geotransform, col: float, row: float) -> Tuple[float, float]:
    """Apply GDAL geotransform to pixel (col,row) to produce (x,y) in CRS units."""

    x0, a, b, y0, d, e = gt
    x = x0 + a * col + b * row
    y = y0 + d * col + e * row
    return float(x), float(y)


def detections_px_to_crs(
    detections: Sequence[Mapping[str, object]],
    *,
    geotransform: Geotransform,
    crs: str,
    col_key: str = "col",
    row_key: str = "row",
) -> CrsDetections:
    """Convert pixel-space detections into CRS `x/y` detections using a geotransform."""

    out: List[dict] = []
    for det in detections:
        if col_key not in det or row_key not in det:
            continue
        col = float(det[col_key])  # type: ignore[arg-type]
        row = float(det[row_key])  # type: ignore[arg-type]
        x, y = apply_geotransform(geotransform, col=col, row=row)
        out.append({**dict(det), "x": x, "y": y})

    return CrsDetections(crs=str(crs), detections=out)

