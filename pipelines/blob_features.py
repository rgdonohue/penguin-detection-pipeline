"""
Blob feature extraction for LiDAR penguin detection.

Provides comprehensive feature extraction for detected blobs, including:
- HAG height statistics (min, max, mean, std, percentiles)
- Geometry features (area, perimeter, eccentricity, circularity, solidity)
- Point statistics (point_count, point_density, vertical_spread)
- Spectral features (intensity, RGB, greenness) with per-tile z-score normalization

These features enable multi-feature classification to escape the
"single-threshold trap" where hag_max dominates detection behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from skimage import measure


@dataclass
class BlobFeatures:
    """Feature vector for a single detected blob.

    All features are computed from the blob's pixels in various grids
    (HAG, intensity, RGB). Features are designed to be useful for
    classification while remaining interpretable.
    """

    # Identification
    label: int
    tile: str = ""
    detection_id: str = ""

    # Location (grid coordinates)
    centroid_row: float = 0.0
    centroid_col: float = 0.0

    # Location (projected coordinates if available)
    x: Optional[float] = None
    y: Optional[float] = None

    # HAG height statistics
    hag_min: float = 0.0
    hag_max: float = 0.0
    hag_mean: float = 0.0
    hag_std: float = 0.0
    hag_p50: float = 0.0  # median
    hag_p90: float = 0.0
    hag_p95: float = 0.0
    hag_range: float = 0.0  # max - min
    hag_skewness: float = 0.0

    # Geometry features
    area_cells: int = 0
    area_m2: float = 0.0
    perimeter: float = 0.0
    perimeter_m: float = 0.0
    eccentricity: float = 0.0
    circularity: float = 0.0
    solidity: float = 0.0
    extent: float = 0.0  # ratio of pixels to bounding box
    axis_major_length: float = 0.0
    axis_minor_length: float = 0.0
    aspect_ratio: float = 0.0

    # Point statistics (from point count grid)
    point_count: int = 0
    point_density_per_cell: float = 0.0
    vertical_spread: float = 0.0  # std dev of Z values

    # Spectral features (raw values)
    intensity_mean: Optional[float] = None
    intensity_min: Optional[float] = None
    intensity_max: Optional[float] = None
    intensity_std: Optional[float] = None
    rgb_r_mean: Optional[float] = None
    rgb_g_mean: Optional[float] = None
    rgb_b_mean: Optional[float] = None
    greenness: Optional[float] = None  # (G - R) / (G + R + B + eps)

    # Spectral features (z-score normalized per tile)
    intensity_zscore: Optional[float] = None
    rgb_r_zscore: Optional[float] = None
    rgb_g_zscore: Optional[float] = None
    rgb_b_zscore: Optional[float] = None
    greenness_zscore: Optional[float] = None

    # Single-return fraction (solid surface indicator)
    single_return_fraction: Optional[float] = None

    # Watershed/merge indicators
    likely_merged_score: float = 0.0
    was_split: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON/CSV export."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


def compute_hag_features(
    labeled: np.ndarray,
    hag: np.ndarray,
    label: int,
) -> Dict[str, float]:
    """Compute HAG-based features for a single blob.

    Args:
        labeled: Label image (ny, nx)
        hag: HAG grid (ny, nx)
        label: Label ID of the blob to analyze

    Returns:
        Dict of HAG features
    """
    mask = labeled == label
    if not np.any(mask):
        return {}

    values = hag[mask]
    if values.size == 0:
        return {}

    # Basic statistics
    features = {
        "hag_min": float(np.min(values)),
        "hag_max": float(np.max(values)),
        "hag_mean": float(np.mean(values)),
        "hag_std": float(np.std(values)),
        "hag_range": float(np.ptp(values)),
    }

    # Percentiles
    features["hag_p50"] = float(np.percentile(values, 50))
    features["hag_p90"] = float(np.percentile(values, 90))
    features["hag_p95"] = float(np.percentile(values, 95))

    # Skewness (requires scipy)
    try:
        from scipy.stats import skew
        features["hag_skewness"] = float(skew(values))
    except ImportError:
        features["hag_skewness"] = 0.0

    return features


def compute_geometry_features(
    region: "measure._regionprops._RegionProperties",
    cell_res: float,
) -> Dict[str, float]:
    """Compute geometry features from a regionprops object.

    Args:
        region: skimage regionprops region
        cell_res: Cell resolution in meters

    Returns:
        Dict of geometry features
    """
    area = region.area
    perimeter = region.perimeter

    features = {
        "area_cells": int(area),
        "area_m2": float(area * cell_res * cell_res),
        "perimeter": float(perimeter),
        "perimeter_m": float(perimeter * cell_res),
        "eccentricity": float(region.eccentricity),
        "solidity": float(region.solidity),
        "extent": float(region.extent),
    }

    # Circularity
    if perimeter > 0:
        features["circularity"] = float(4.0 * np.pi * area / (perimeter * perimeter))
    else:
        features["circularity"] = 0.0

    # Axis lengths (handle potential attribute differences across skimage versions)
    try:
        features["axis_major_length"] = float(region.major_axis_length) * cell_res
        features["axis_minor_length"] = float(region.minor_axis_length) * cell_res
    except AttributeError:
        features["axis_major_length"] = 0.0
        features["axis_minor_length"] = 0.0

    # Aspect ratio
    if features["axis_minor_length"] > 0:
        features["aspect_ratio"] = features["axis_major_length"] / features["axis_minor_length"]
    else:
        features["aspect_ratio"] = 1.0

    return features


def compute_spectral_features(
    labeled: np.ndarray,
    label: int,
    intensity_grid: Optional[np.ndarray] = None,
    rgb_r_grid: Optional[np.ndarray] = None,
    rgb_g_grid: Optional[np.ndarray] = None,
    rgb_b_grid: Optional[np.ndarray] = None,
) -> Dict[str, Optional[float]]:
    """Compute spectral features for a blob.

    Args:
        labeled: Label image
        label: Label ID
        intensity_grid: Per-cell mean intensity grid (optional)
        rgb_r_grid: Per-cell mean red grid (optional)
        rgb_g_grid: Per-cell mean green grid (optional)
        rgb_b_grid: Per-cell mean blue grid (optional)

    Returns:
        Dict of spectral features (None for unavailable)
    """
    mask = labeled == label
    if not np.any(mask):
        return {}

    features: Dict[str, Optional[float]] = {}

    # Intensity features
    if intensity_grid is not None:
        vals = intensity_grid[mask]
        if vals.size > 0:
            features["intensity_mean"] = float(np.mean(vals))
            features["intensity_min"] = float(np.min(vals))
            features["intensity_max"] = float(np.max(vals))
            features["intensity_std"] = float(np.std(vals))

    # RGB features
    if rgb_r_grid is not None and rgb_g_grid is not None and rgb_b_grid is not None:
        r_vals = rgb_r_grid[mask]
        g_vals = rgb_g_grid[mask]
        b_vals = rgb_b_grid[mask]
        if r_vals.size > 0:
            r_mean = float(np.mean(r_vals))
            g_mean = float(np.mean(g_vals))
            b_mean = float(np.mean(b_vals))
            features["rgb_r_mean"] = r_mean
            features["rgb_g_mean"] = g_mean
            features["rgb_b_mean"] = b_mean

            # Greenness index: normalized vegetation indicator
            denom = g_mean + r_mean + b_mean + 1e-6
            features["greenness"] = (g_mean - r_mean) / denom

    return features


def compute_tile_normalization(
    detections: List[Dict],
    features: List[BlobFeatures],
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Compute per-tile mean and std for spectral feature normalization.

    Args:
        detections: List of detection dicts (for backwards compatibility)
        features: List of BlobFeatures objects

    Returns:
        Tuple of (means_dict, stds_dict) for z-score normalization
    """
    # Collect values for normalization
    intensity_vals = []
    rgb_r_vals = []
    rgb_g_vals = []
    rgb_b_vals = []
    greenness_vals = []

    for feat in features:
        if feat.intensity_mean is not None:
            intensity_vals.append(feat.intensity_mean)
        if feat.rgb_r_mean is not None:
            rgb_r_vals.append(feat.rgb_r_mean)
        if feat.rgb_g_mean is not None:
            rgb_g_vals.append(feat.rgb_g_mean)
        if feat.rgb_b_mean is not None:
            rgb_b_vals.append(feat.rgb_b_mean)
        if feat.greenness is not None:
            greenness_vals.append(feat.greenness)

    means = {}
    stds = {}

    for name, vals in [
        ("intensity", intensity_vals),
        ("rgb_r", rgb_r_vals),
        ("rgb_g", rgb_g_vals),
        ("rgb_b", rgb_b_vals),
        ("greenness", greenness_vals),
    ]:
        if vals:
            arr = np.array(vals)
            means[name] = float(np.mean(arr))
            stds[name] = float(np.std(arr)) if len(arr) > 1 else 1.0
        else:
            means[name] = 0.0
            stds[name] = 1.0

    return means, stds


def apply_zscore_normalization(
    features: List[BlobFeatures],
    means: Dict[str, float],
    stds: Dict[str, float],
) -> None:
    """Apply z-score normalization to spectral features in-place.

    Args:
        features: List of BlobFeatures to normalize
        means: Per-tile mean values
        stds: Per-tile std values
    """
    for feat in features:
        if feat.intensity_mean is not None:
            feat.intensity_zscore = (feat.intensity_mean - means.get("intensity", 0)) / max(stds.get("intensity", 1), 1e-6)
        if feat.rgb_r_mean is not None:
            feat.rgb_r_zscore = (feat.rgb_r_mean - means.get("rgb_r", 0)) / max(stds.get("rgb_r", 1), 1e-6)
        if feat.rgb_g_mean is not None:
            feat.rgb_g_zscore = (feat.rgb_g_mean - means.get("rgb_g", 0)) / max(stds.get("rgb_g", 1), 1e-6)
        if feat.rgb_b_mean is not None:
            feat.rgb_b_zscore = (feat.rgb_b_mean - means.get("rgb_b", 0)) / max(stds.get("rgb_b", 1), 1e-6)
        if feat.greenness is not None:
            feat.greenness_zscore = (feat.greenness - means.get("greenness", 0)) / max(stds.get("greenness", 1), 1e-6)


def extract_blob_features(
    labeled: np.ndarray,
    hag: np.ndarray,
    cell_res: float,
    mins: np.ndarray,
    tile_name: str = "",
    intensity_grid: Optional[np.ndarray] = None,
    rgb_r_grid: Optional[np.ndarray] = None,
    rgb_g_grid: Optional[np.ndarray] = None,
    rgb_b_grid: Optional[np.ndarray] = None,
    point_count_grid: Optional[np.ndarray] = None,
    single_return_grid: Optional[np.ndarray] = None,
    expected_penguin_area_cells: Optional[int] = None,
    normalize_spectral: bool = True,
    split_labels: Optional[set] = None,
    z_std_grid: Optional[np.ndarray] = None,
) -> List[BlobFeatures]:
    """Extract comprehensive features for all blobs in a labeled image.

    Args:
        labeled: Label image (ny, nx) with blob IDs
        hag: HAG grid (ny, nx)
        cell_res: Cell resolution in meters
        mins: Grid origin (min_x, min_y)
        tile_name: Name of the tile for identification
        intensity_grid: Per-cell mean intensity (optional)
        rgb_r_grid: Per-cell mean red (optional)
        rgb_g_grid: Per-cell mean green (optional)
        rgb_b_grid: Per-cell mean blue (optional)
        point_count_grid: Per-cell point count (optional)
        single_return_grid: Per-cell single-return fraction (optional)
        expected_penguin_area_cells: Expected area of single penguin (for merge score)
        normalize_spectral: Apply per-tile z-score normalization
        split_labels: Set of label IDs that came from watershed splitting
        z_std_grid: Per-cell Z value standard deviation (for vertical_spread)

    Returns:
        List of BlobFeatures objects
    """
    features_list: List[BlobFeatures] = []

    # Default expected area if not provided
    if expected_penguin_area_cells is None:
        expected_penguin_area_cells = 6  # ~0.38 m² at 0.25m resolution

    # Get region properties
    props = measure.regionprops(labeled, intensity_image=hag)

    for i, region in enumerate(props):
        label = region.label
        feat = BlobFeatures(label=label)
        feat.tile = tile_name
        feat.detection_id = f"{tile_name}:{label:05d}" if tile_name else f"det:{label:05d}"

        # Centroid
        feat.centroid_row = float(region.centroid[0])
        feat.centroid_col = float(region.centroid[1])

        # Projected coordinates
        feat.x = float(mins[0] + (feat.centroid_col + 0.5) * cell_res)
        feat.y = float(mins[1] + (feat.centroid_row + 0.5) * cell_res)

        # HAG features
        hag_feats = compute_hag_features(labeled, hag, label)
        for k, v in hag_feats.items():
            setattr(feat, k, v)

        # Geometry features
        geom_feats = compute_geometry_features(region, cell_res)
        for k, v in geom_feats.items():
            setattr(feat, k, v)

        # Spectral features
        spectral_feats = compute_spectral_features(
            labeled, label,
            intensity_grid, rgb_r_grid, rgb_g_grid, rgb_b_grid,
        )
        for k, v in spectral_feats.items():
            setattr(feat, k, v)

        # Point statistics
        if point_count_grid is not None:
            mask = labeled == label
            counts = point_count_grid[mask]
            if counts.size > 0:
                feat.point_count = int(np.sum(counts))
                feat.point_density_per_cell = float(np.mean(counts))

        # Single-return fraction
        if single_return_grid is not None:
            mask = labeled == label
            srf_vals = single_return_grid[mask]
            if srf_vals.size > 0:
                feat.single_return_fraction = float(np.mean(srf_vals))

        # Merge score
        feat.likely_merged_score = feat.area_cells / max(expected_penguin_area_cells, 1)

        # Was this blob created by watershed splitting?
        if split_labels is not None and label in split_labels:
            feat.was_split = True

        # Vertical spread (Z std) if available
        if z_std_grid is not None:
            mask = labeled == label
            z_std_vals = z_std_grid[mask]
            if z_std_vals.size > 0:
                # Use mean of per-cell Z std as vertical spread
                feat.vertical_spread = float(np.mean(z_std_vals))

        features_list.append(feat)

    # Apply z-score normalization if requested
    if normalize_spectral and features_list:
        means, stds = compute_tile_normalization([], features_list)
        apply_zscore_normalization(features_list, means, stds)

    return features_list


def features_to_dataframe(features: List[BlobFeatures]):
    """Convert list of BlobFeatures to a pandas DataFrame.

    Requires pandas to be installed.
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas required for DataFrame conversion")

    records = [f.to_dict() for f in features]
    return pd.DataFrame(records)


def features_to_parquet(features: List[BlobFeatures], out_path) -> None:
    """Save features to Parquet format.

    Requires pandas and pyarrow to be installed.
    """
    df = features_to_dataframe(features)
    df.to_parquet(out_path, index=False)
