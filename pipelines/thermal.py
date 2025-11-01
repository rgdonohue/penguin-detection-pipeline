"""
Thermal Orthorectification Pipeline

Back-projects DSM cells into camera frame to generate orthorectified thermal imagery.

DEPENDENCIES:
    This module requires GDAL/rasterio which has complex installation requirements.
    Install via conda or see RUNBOOK.md for platform-specific instructions.

    Required: rasterio, pyproj, numpy, pandas, pillow

    To install (conda recommended):
        conda install -c conda-forge gdal rasterio pyproj

    Or via pip (requires GDAL system libraries):
        pip install gdal rasterio pyproj

USAGE:
    See scripts/run_thermal_ortho.py for CLI interface.
"""

from __future__ import annotations
import math
import json
import subprocess
import tempfile
import warnings
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple
from fractions import Fraction
from decimal import Decimal, getcontext

import numpy as np
import pandas as pd

# Guarded imports for GDAL stack
try:
    import rasterio
    from rasterio.windows import from_bounds
    from rasterio.transform import from_origin
    from rasterio.enums import Resampling
    from pyproj import Transformer
    GDAL_AVAILABLE = True
except ImportError as e:
    GDAL_AVAILABLE = False
    _GDAL_IMPORT_ERROR = str(e)

# PIL/Pillow is available via scikit-image dependency
try:
    from PIL import Image, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

getcontext().prec = 28


def check_dependencies():
    """Check if required dependencies are available. Raises ImportError if not."""
    if not GDAL_AVAILABLE:
        raise ImportError(
            f"GDAL/rasterio not available: {_GDAL_IMPORT_ERROR}\n"
            "Install via: conda install -c conda-forge gdal rasterio pyproj\n"
            "Or see RUNBOOK.md for platform-specific instructions."
        )
    if not PIL_AVAILABLE:
        raise ImportError("PIL/Pillow not available. Install via: pip install pillow")


# ========================= Thermal Data Extraction =========================

SUPPORTED_THERMAL_SHAPES: Dict[int, Tuple[int, int]] = {
    640 * 512: (512, 640),        # H20T
    1280 * 1024: (1024, 1280),    # H30T
}
DEFAULT_THERMAL_SCALE = 64.0
ALTERNATE_SCALES = (96.0, 80.0, 128.0)
MAX_REASONABLE_TEMP = 120.0
MIN_REASONABLE_TEMP = -80.0
MAX_REASONABLE_MEAN = 80.0


@dataclass
class ThermalFrame:
    """Container for extracted thermal data and diagnostics."""

    celsius: np.ndarray
    scale: float
    raw_shape: Tuple[int, int]
    mode: str
    raw_stats: Dict[str, float]
    source: Path


def extract_thermal_data(image_path: Path, temp_dir: Optional[Path] = None) -> np.ndarray:
    """Extract radiometric thermal data as a float32 Celsius array.

    This is a thin wrapper over ``extract_thermal_frame`` kept for backward
    compatibility with existing callers that expect only the temperature grid.
    """
    frame = extract_thermal_frame(image_path, temp_dir=temp_dir)
    return frame.celsius


def extract_thermal_frame(
    image_path: Path,
    temp_dir: Optional[Path] = None,
) -> ThermalFrame:
    """Extract 16-bit radiometric thermal data and metadata from DJI RJPEG.

    Supports both 640×512 (H20T) and 1280×1024 (H30T) thermal payloads and
    heuristically rescales frames captured with high-contrast digital gain.
    """
    cleanup = False
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp())
        cleanup = True
    else:
        temp_dir = Path(temp_dir)

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        raw = _load_thermal_raw(image_path=image_path, temp_dir=temp_dir)
        celsius, scale, mode = _convert_raw_to_celsius(raw, image_path=image_path)

        raw_stats = {
            "min": float(raw.min()),
            "max": float(raw.max()),
            "mean": float(raw.mean()),
            "std": float(raw.std(ddof=0)),
        }

        return ThermalFrame(
            celsius=celsius,
            scale=scale,
            raw_shape=tuple(raw.shape),
            mode=mode,
            raw_stats=raw_stats,
            source=image_path,
        )
    finally:
        if cleanup:
            shutil.rmtree(temp_dir, ignore_errors=True)


def _load_thermal_raw(image_path: Path, temp_dir: Path) -> np.ndarray:
    """Extract the raw thermal payload as a uint16 array."""
    raw_path = temp_dir / "thermal.raw"
    cmd = ["exiftool", "-b", "-ThermalData", str(image_path)]

    try:
        result = subprocess.run(cmd, capture_output=True, check=True)
        raw_path.write_bytes(result.stdout)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "exiftool not found. Install via: brew install exiftool (macOS) "
            "or apt-get install libimage-exiftool-perl (Linux)"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"exiftool failed: {exc.stderr.decode()}") from exc

    raw = np.fromfile(raw_path, dtype=np.uint16)
    try:
        shape = SUPPORTED_THERMAL_SHAPES[len(raw)]
    except KeyError as exc:
        raise RuntimeError(
            f"ThermalData size mismatch: got {len(raw)} elements; "
            "supported sensors: "
            + ", ".join(
                f"{w}x{h}" for (h, w) in SUPPORTED_THERMAL_SHAPES.values()
            )
        ) from exc

    return raw.reshape(shape)


def _convert_raw_to_celsius(raw: np.ndarray, image_path: Path) -> Tuple[np.ndarray, float, str]:
    """Convert raw uint16 thermal data to Celsius with scale heuristics."""
    raw_float = raw.astype(np.float32, copy=False)

    def convert(scale: float) -> np.ndarray:
        kelvin = raw_float / scale
        return kelvin - 273.15

    def temp_range_okay(celsius: np.ndarray) -> bool:
        min_val = float(celsius.min())
        max_val = float(celsius.max())
        mean_val = float(celsius.mean())
        return (
            MIN_REASONABLE_TEMP <= min_val <= MAX_REASONABLE_TEMP
            and MIN_REASONABLE_TEMP <= mean_val <= MAX_REASONABLE_MEAN
            and max_val <= MAX_REASONABLE_TEMP
        )

    celsius = convert(DEFAULT_THERMAL_SCALE)
    scale = DEFAULT_THERMAL_SCALE
    mode = "normal"

    if not temp_range_okay(celsius):
        selected_scale = None
        for candidate in ALTERNATE_SCALES:
            alt = convert(candidate)
            if temp_range_okay(alt):
                celsius = alt
                scale = candidate
                selected_scale = candidate
                break

        if selected_scale is None:
            # Fall back to dynamic scaling anchored to 20°C expectation.
            target_kelvin = 20.0 + 273.15
            mean_raw = float(raw_float.mean())
            if mean_raw <= 0:
                raise RuntimeError(
                    f"Unable to determine thermal scale for {image_path}; "
                    "mean raw DN is non-positive."
                )
            scale = mean_raw / target_kelvin
            celsius = convert(scale)
            mode = "dynamic"
        else:
            mode = "high_contrast" if math.isclose(scale, 96.0, rel_tol=1e-3) else "rescaled"

        if mode != "normal":
            warnings.warn(
                f"Thermal frame {image_path.name} required scale {scale:.2f} "
                f"({mode}); radiometric accuracy should be validated.",
                RuntimeWarning,
                stacklevel=2,
            )

    return celsius.astype(np.float32, copy=False), scale, mode


# ========================= Grid Alignment =========================

def nested_grid(dsm_transform, user_px: float, bounds: Tuple[float, float, float, float]) -> Tuple[float, float, float, float, float]:
    """
    Build a fine grid nested exactly on the DSM grid.

    Ensures output pixel size evenly divides DSM pixel size and origins align.

    Args:
        dsm_transform: rasterio affine transform from DSM
        user_px: Requested output pixel size (meters)
        bounds: (x0, y0, x1, y1) initial AOI bounds

    Returns:
        (x0, y0, x1, y1, px) where px == user_px and grid aligns to DSM
    """
    dsm_px = float(dsm_transform.a)
    dsm_x0 = float(dsm_transform.c)
    dsm_y0 = float(dsm_transform.f)
    x0, y0, x1, y1 = map(float, bounds)

    # Enforce exact integer nesting
    r = Fraction(dsm_px).limit_denominator() / Fraction(user_px).limit_denominator()
    k = round(float(r))
    if not (abs(float(r) - k) < 1e-9 and k >= 1):
        raise ValueError(
            f"Requested pixel {user_px} must evenly divide DSM {dsm_px}; ratio={float(r)}"
        )

    # Snap AOI bounds to DSM grid
    x0s = dsm_x0 + dsm_px * math.floor((x0 - dsm_x0) / dsm_px)
    y0s = dsm_y0 + dsm_px * math.floor((y0 - dsm_y0) / dsm_px)
    x1s = dsm_x0 + dsm_px * math.ceil((x1 - dsm_x0) / dsm_px)
    y1s = dsm_y0 + dsm_px * math.ceil((y1 - dsm_y0) / dsm_px)

    # Use Decimal to avoid floating point drift
    px = float(Decimal(str(user_px)))
    X0 = float(Decimal(str(x0s)))
    Y0 = float(Decimal(str(y0s)))
    w = int(math.ceil((x1s - X0) / px))
    h = int(math.ceil((y1s - Y0) / px))
    X1 = X0 + w * px
    Y1 = Y0 + h * px

    return X0, Y0, X1, Y1, px


def verify_grid(dsm_path: str, ortho_path: str, tol: float = 1e-9) -> dict:
    """
    Verify that ortho grid is properly nested on DSM grid.

    Returns dict with validation results including 'ok' boolean.
    """
    check_dependencies()

    with rasterio.open(dsm_path) as A, rasterio.open(ortho_path) as B:
        dpx = float(A.transform.a)
        opx = float(B.transform.a)
        ratio = dpx / opx
        dx_mod = (B.transform.c - A.transform.c) % dpx
        dy_mod = (B.transform.f - A.transform.f) % dpx
        int_ok = abs(ratio - round(ratio)) < tol

        def rem_ok(r):
            return (r < tol) or (abs(r - dpx) < tol)

        ok = int_ok and rem_ok(dx_mod) and rem_ok(dy_mod)

        return {
            "dsm_pixel": dpx,
            "ortho_pixel": opx,
            "ratio": ratio,
            "dx_mod": dx_mod,
            "dy_mod": dy_mod,
            "ok": ok,
            "dsm": dsm_path,
            "ortho": ortho_path,
        }


# ========================= Pose Data Parsing =========================

# DJI XMP metadata column mappings (supports bare and namespaced names)
POSE_COLS = {
    "SourceFile": ["SourceFile", "FileName", "Source", "File"],
    "CreateDate": ["CreateDate", "XMP:CreateDate", "XMP-CreateDate"],
    "GPSLatitude": ["GPSLatitude", "XMP-drone-dji:GPSLatitude"],
    "GPSLongitude": ["GPSLongitude", "XMP-drone-dji:GPSLongitude"],
    "AbsoluteAltitude": ["AbsoluteAltitude", "XMP-drone-dji:AbsoluteAltitude"],
    "RelativeAltitude": ["RelativeAltitude", "XMP-drone-dji:RelativeAltitude"],
    "FlightYawDegree": ["FlightYawDegree", "XMP-drone-dji:FlightYawDegree"],
    "FlightPitchDegree": ["FlightPitchDegree", "XMP-drone-dji:FlightPitchDegree"],
    "FlightRollDegree": ["FlightRollDegree", "XMP-drone-dji:FlightRollDegree"],
    "GimbalYawDegree": ["GimbalYawDegree", "XMP-drone-dji:GimbalYawDegree"],
    "GimbalPitchDegree": ["GimbalPitchDegree", "XMP-drone-dji:GimbalPitchDegree"],
    "GimbalRollDegree": ["GimbalRollDegree", "XMP-drone-dji:GimbalRollDegree"],
    "LRFTargetLat": ["LRFTargetLat", "XMP-drone-dji:LRFTargetLat"],
    "LRFTargetLon": ["LRFTargetLon", "XMP-drone-dji:LRFTargetLon"],
    "LRFTargetAbsAlt": ["LRFTargetAbsAlt", "XMP-drone-dji:LRFTargetAbsAlt"],
    "LRFTargetDistance": ["LRFTargetDistance", "XMP-drone-dji:LRFTargetDistance"],
}


def _find_col(df: pd.DataFrame, candidates):
    """Find column in DataFrame by case-insensitive suffix matching."""
    lower = {c.lower(): c for c in df.columns}
    for key in candidates:
        k = key.lower()
        if k in lower:
            return lower[k]
        for c_l, c in lower.items():
            if c_l.endswith(k):
                return c
    return None


@dataclass
class Pose:
    """Camera/gimbal pose from DJI XMP metadata."""
    image_name: str
    lat: float
    lon: float
    h_abs: float
    yaw_f: float
    pitch_f: float
    roll_f: float
    yaw_g: float
    pitch_g: float
    roll_g: float
    lrf_lat: Optional[float]
    lrf_lon: Optional[float]
    lrf_alt: Optional[float]
    lrf_dist: Optional[float]

    @property
    def yaw_total(self) -> float:
        """Combined flight + gimbal yaw."""
        return self.yaw_f + self.yaw_g

    @property
    def pitch_total(self) -> float:
        """Combined flight + gimbal pitch."""
        return self.pitch_f + self.pitch_g

    @property
    def roll_total(self) -> float:
        """Combined flight + gimbal roll."""
        return self.roll_f + self.roll_g


def load_poses(csv_path: Path) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Load poses CSV exported from exiftool.

    Returns (DataFrame, column_mapping_dict)
    """
    df = pd.read_csv(csv_path)
    cols = {k: _find_col(df, v) for k, v in POSE_COLS.items()}

    missing = [
        k for k, v in cols.items()
        if v is None and k not in ("RelativeAltitude", "LRFTargetDistance")
    ]
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}\nHave: {list(df.columns)}"
        )

    return df, cols


def pose_for_image(df: pd.DataFrame, cols: Dict[str, str], image_path: Path) -> Pose:
    """
    Extract pose for specific image from poses DataFrame.

    Matches by filename; falls back to first row if no match found.
    """
    name = image_path.name

    # Try exact filename match
    if cols.get("SourceFile") and cols["SourceFile"] in df.columns:
        series = df[cols["SourceFile"]].astype(str).apply(lambda s: Path(s).name)
        idx = series[series == name].index
    else:
        idx = pd.Index([])

    if len(idx) == 0:
        i = 0  # Fallback to first row
    else:
        i = int(idx[0])

    def g(k, default=np.nan):
        """Get value from DataFrame with fallback."""
        col = cols.get(k)
        if col and col in df.columns:
            return df.iloc[i][col]
        return default

    return Pose(
        image_name=name,
        lat=float(g("GPSLatitude")),
        lon=float(g("GPSLongitude")),
        h_abs=float(g("AbsoluteAltitude")),
        yaw_f=float(g("FlightYawDegree", 0.0)),
        pitch_f=float(g("FlightPitchDegree", 0.0)),
        roll_f=float(g("FlightRollDegree", 0.0)),
        yaw_g=float(g("GimbalYawDegree", 0.0)),
        pitch_g=float(g("GimbalPitchDegree", 0.0)),
        roll_g=float(g("GimbalRollDegree", 0.0)),
        lrf_lat=float(g("LRFTargetLat")) if not pd.isna(g("LRFTargetLat")) else None,
        lrf_lon=float(g("LRFTargetLon")) if not pd.isna(g("LRFTargetLon")) else None,
        lrf_alt=float(g("LRFTargetAbsAlt")) if not pd.isna(g("LRFTargetAbsAlt")) else None,
        lrf_dist=float(g("LRFTargetDistance", np.nan)) if not pd.isna(g("LRFTargetDistance", np.nan)) else None,
    )


# ========================= Camera Model =========================

def hv_from_dfov(dfov_deg: float, w: int, h: int) -> Tuple[float, float]:
    """Compute HFOV and VFOV from diagonal FOV and aspect ratio."""
    dfov = math.radians(dfov_deg)
    t = math.tan(dfov / 2.0)
    r = w / h
    b = t / math.sqrt(r * r + 1.0)  # tan(vfov/2)
    a = r * b  # tan(hfov/2)
    hfov = 2.0 * math.atan(a)
    vfov = 2.0 * math.atan(b)
    return math.degrees(hfov), math.degrees(vfov)


def intrinsics_from_fov(hfov_deg: float, vfov_deg: float, w: int, h: int) -> Tuple[float, float, float, float]:
    """Compute camera intrinsics (fx, fy, cx, cy) from FOV and image size."""
    hfov = math.radians(hfov_deg)
    vfov = math.radians(vfov_deg)
    fx = (w / 2.0) / math.tan(hfov / 2.0)
    fy = (h / 2.0) / math.tan(vfov / 2.0)
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    return fx, fy, cx, cy


def rotation_from_ypr(yaw_deg: float, pitch_deg: float, roll_deg: float) -> np.ndarray:
    """
    Build world→camera rotation matrix from yaw/pitch/roll.

    Conventions:
        - Yaw: North→East (degrees)
        - Pitch: Positive up (degrees)
        - Roll: Right-hand about forward (degrees)
        - Camera axes: x=right, y=down, z=forward
        - World frame: ENU (East-North-Up)

    Returns:
        3x3 rotation matrix R where v_world = R @ v_cam
    """
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)

    # Forward vector in ENU from yaw/pitch
    c = math.cos(pitch)
    f_e = math.sin(yaw) * c
    f_n = math.cos(yaw) * c
    f_u = math.sin(pitch)
    f = np.array([f_e, f_n, f_u], dtype=float)
    f /= max(1e-12, np.linalg.norm(f))

    # Right and down vectors
    up = np.array([0.0, 0.0, 1.0], dtype=float)
    r = np.cross(f, up)
    if np.linalg.norm(r) < 1e-9:
        r = np.array([1.0, 0.0, 0.0])
    else:
        r /= np.linalg.norm(r)

    d = np.cross(r, f)  # down
    d /= max(1e-12, np.linalg.norm(d))

    # Apply roll if present
    if abs(roll_deg) > 1e-8:
        th = math.radians(roll_deg)
        ct, st = math.cos(th), math.sin(th)
        r2 = ct * r + st * d
        d2 = -st * r + ct * d
        r, d = r2, d2

    R = np.stack([r, d, f], axis=1)  # columns are camera axes in world frame
    return R


# ========================= Image Resampling =========================

def bilinear_sample(img: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """
    Bilinear sample from image at floating-point pixel coordinates.

    Args:
        img: HxW or HxWxC image
        u: x-coordinates (pixel units)
        v: y-coordinates (pixel units)

    Returns:
        Sampled values with same shape as u/v
    """
    H, W = img.shape[:2]
    C = 1 if img.ndim == 2 else img.shape[2]

    u0 = np.floor(u).astype(np.int32)
    v0 = np.floor(v).astype(np.int32)
    du = u - u0
    dv = v - v0

    u1 = u0 + 1
    v1 = v0 + 1

    u0c = np.clip(u0, 0, W - 1)
    u1c = np.clip(u1, 0, W - 1)
    v0c = np.clip(v0, 0, H - 1)
    v1c = np.clip(v1, 0, H - 1)

    if C == 1:
        I00 = img[v0c, u0c]
        I10 = img[v0c, u1c]
        I01 = img[v1c, u0c]
        I11 = img[v1c, u1c]
    else:
        I00 = img[v0c, u0c, :]
        I10 = img[v0c, u1c, :]
        I01 = img[v1c, u0c, :]
        I11 = img[v1c, u1c, :]

    w00 = (1 - du) * (1 - dv)
    w10 = du * (1 - dv)
    w01 = (1 - du) * dv
    w11 = du * dv

    if C == 1:
        out = w00 * I00 + w10 * I10 + w01 * I01 + w11 * I11
        return out
    else:
        out = (
            I00 * w00[..., None] + I10 * w10[..., None] +
            I01 * w01[..., None] + I11 * w11[..., None]
        )
        return out


# ========================= Orthorectification =========================

def compute_aoi(
    center_xy: Tuple[float, float],
    dfov_deg: float,
    aspect: float,
    slant_m: float,
    margin: float
) -> Tuple[float, float, float, float]:
    """
    Compute AOI bounds from camera parameters.

    Args:
        center_xy: (x, y) ground coordinates of AOI center
        dfov_deg: Diagonal field of view (degrees)
        aspect: Image width/height ratio
        slant_m: Slant range from camera to ground (meters)
        margin: Expansion factor (>1.0)

    Returns:
        (x0, y0, x1, y1) bounds in ground coordinates
    """
    dfov = math.radians(dfov_deg)
    t = math.tan(dfov / 2.0)
    b = t / math.sqrt(aspect * aspect + 1.0)
    a = aspect * b
    half_w = math.tan(2 * math.atan(a) / 2.0) * slant_m
    half_h = math.tan(2 * math.atan(b) / 2.0) * slant_m
    half_w *= margin
    half_h *= margin

    x0 = center_xy[0] - half_w
    x1 = center_xy[0] + half_w
    y0 = center_xy[1] - half_h
    y1 = center_xy[1] + half_h

    return x0, y0, x1, y1


def ortho_one(
    image_path: Path,
    poses_csv: Path,
    dsm_path: Path,
    out_path: Path,
    boresight: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    dfov_deg: float = 40.6,
    pixel_size: Optional[float] = None,
    margin: float = 1.25,
    z_offset: float = 0.0,
    mono: bool = True,
    pre_blur: float = 0.0,
    strict_bounds: bool = True,
    tight_crop: bool = True,
    snap_to_dsm_grid: bool = False,
    radiometric: bool = False,
) -> dict:
    """
    Orthorectify a single thermal image via DSM back-projection.

    Args:
        image_path: Path to thermal image (JPG/TIFF)
        poses_csv: Path to poses CSV from exiftool
        dsm_path: Path to LiDAR DSM GeoTIFF
        out_path: Output ortho GeoTIFF path
        boresight: (Δyaw, Δpitch, Δroll) calibration offset in degrees
        dfov_deg: Diagonal field of view (degrees). H20T thermal ≈ 40.6°
        pixel_size: Output pixel size (meters). None = match DSM
        margin: AOI expansion factor (>1.0)
        z_offset: Altitude bias to add to AbsoluteAltitude (meters)
        mono: Convert to grayscale (luminance) - ignored if radiometric=True
        pre_blur: Gaussian blur radius before resampling - ignored if radiometric=True
        strict_bounds: Treat out-of-image samples as nodata
        tight_crop: Crop output to valid footprint
        snap_to_dsm_grid: Ensure output grid nests exactly on DSM grid
        radiometric: Extract 16-bit thermal data as Celsius (DJI H20T only).
                    If True, extracts ThermalData blob and outputs float32 GeoTIFF.
                    If False (default), uses 8-bit JPEG preview.

    Returns:
        Info dict with metadata (emitted as JSON to stdout)

    Side effects:
        Writes GeoTIFF to out_path with GDAL mask band for transparency.
        Output dtype: float32 if radiometric=True, uint8 otherwise.
    """
    check_dependencies()

    info = {}
    df, cols = load_poses(poses_csv)
    pose = pose_for_image(df, cols, image_path)

    # Load source image
    if radiometric:
        # Extract 16-bit thermal data as float32 Celsius
        with tempfile.TemporaryDirectory() as tmpdir:
            img = extract_thermal_data(image_path, Path(tmpdir))
        # Add channel dimension: (H, W) -> (H, W, 1)
        if img.ndim == 2:
            img = img[..., None]
        Hs, Ws = img.shape[:2]
    else:
        # Load 8-bit JPEG preview using PIL
        pil = Image.open(image_path)
        if mono and pil.mode != "L":
            pil = pil.convert("L")
        if pre_blur > 0:
            pil = pil.filter(ImageFilter.GaussianBlur(radius=float(pre_blur)))

        img = np.asarray(pil)
        if img.ndim == 2:
            img = img[..., None]
        Hs, Ws = img.shape[:2]

    # Camera intrinsics from DFOV
    hfov_deg, vfov_deg = hv_from_dfov(dfov_deg, Ws, Hs)
    fx, fy, cx, cy = intrinsics_from_fov(hfov_deg, vfov_deg, Ws, Hs)

    # Compose yaw/pitch/roll + boresight
    yaw = pose.yaw_total + boresight[0]
    pitch = pose.pitch_total + boresight[1]
    roll = pose.roll_total + boresight[2]
    R = rotation_from_ypr(yaw, pitch, roll)  # world←cam

    # Open DSM
    with rasterio.open(dsm_path) as dsm:
        crs = dsm.crs
        tx = dsm.transform
        dsm_px = tx.a
        if pixel_size is None:
            pixel_size = dsm_px

        # Camera center in DSM CRS
        t4326_to_dsm = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        Cx, Cy = t4326_to_dsm.transform(pose.lon, pose.lat)
        Cz = pose.h_abs + z_offset

        # AOI center: prefer LRF; fallback to camera XY
        if pose.lrf_lat is not None and pose.lrf_lon is not None:
            Lx, Ly = t4326_to_dsm.transform(pose.lrf_lon, pose.lrf_lat)
            center_xy = (Lx, Ly)
            slant = (
                float(pose.lrf_dist)
                if (pose.lrf_dist is not None and not math.isnan(pose.lrf_dist))
                else 50.0
            )
        else:
            center_xy = (Cx, Cy)
            slant = max(
                30.0,
                abs(Cz) / max(1e-3, math.cos(math.radians(max(1.0, abs(pitch)))))
            )

        x0, y0, x1, y1 = compute_aoi(center_xy, dfov_deg, Ws / Hs, slant, margin)

        # Align output grid to DSM if requested
        if snap_to_dsm_grid:
            x0, y0, x1, y1, pixel_size = nested_grid(
                dsm.transform, pixel_size, (x0, y0, x1, y1)
            )

        # Compute output dimensions
        w = int(math.ceil((x1 - x0) / pixel_size))
        h = int(math.ceil((y1 - y0) / pixel_size))

        if not snap_to_dsm_grid:
            x1 = x0 + w * pixel_size
            y1 = y0 + h * pixel_size

        out_transform = from_origin(x0, y1, pixel_size, pixel_size)

        # Sample DSM to output grid
        win = rasterio.windows.from_bounds(x0, y0, x1, y1, dsm.transform)
        z = dsm.read(
            1, window=win, out_shape=(h, w), resampling=Resampling.bilinear
        ).astype(float)

    # Build ground coordinate arrays
    jj = np.arange(w, dtype=float)
    ii = np.arange(h, dtype=float)
    X = x0 + (jj + 0.5) * pixel_size
    Y = y1 - (ii + 0.5) * pixel_size
    XX, YY = np.meshgrid(X, Y)

    # Vector from camera to ground
    dE = XX - Cx
    dN = YY - Cy
    dU = z - Cz

    # Transform to camera coordinates: v_cam = R^T @ v_world
    Vw = np.stack([dE, dN, dU], axis=0).reshape(3, -1)
    Vc = R.T @ Vw
    xc = Vc[0, :]
    yc = Vc[1, :]
    zc = Vc[2, :]

    # Perspective projection
    vis = zc > 1e-6
    u = np.empty_like(xc)
    v = np.empty_like(yc)
    u[:] = np.nan
    v[:] = np.nan
    u[vis] = fx * (xc[vis] / zc[vis]) + cx
    v[vis] = fy * (yc[vis] / zc[vis]) + cy

    # Check bounds
    u_img = u.reshape(h, w)
    v_img = v.reshape(h, w)
    in_bounds = (
        (u_img >= 0) & (u_img <= (Ws - 1)) &
        (v_img >= 0) & (v_img <= (Hs - 1))
    )
    inside = vis.reshape(h, w)
    good = (
        inside & in_bounds if strict_bounds
        else (np.isfinite(u_img) & np.isfinite(v_img))
    )

    # Tight crop to valid footprint
    if tight_crop and np.any(good):
        ys, xs = np.where(good)
        pad = 4
        y0i = max(int(ys.min()) - pad, 0)
        y1i = min(int(ys.max()) + pad + 1, h)
        x0i = max(int(xs.min()) - pad, 0)
        x1i = min(int(xs.max()) + pad + 1, w)

        # Crop arrays
        u_img = u_img[y0i:y1i, x0i:x1i]
        v_img = v_img[y0i:y1i, x0i:x1i]
        good = good[y0i:y1i, x0i:x1i]
        inside = inside[y0i:y1i, x0i:x1i]
        z = z[y0i:y1i, x0i:x1i]
        h, w = good.shape

        # Update transform to cropped origin
        x0 = x0 + x0i * pixel_size
        y1 = y1 - y0i * pixel_size
        out_transform = from_origin(x0, y1, pixel_size, pixel_size)

    # Sample source image
    samp = np.zeros((h, w, img.shape[2]), dtype=img.dtype)
    if img.shape[2] == 1:
        vals = bilinear_sample(img[..., 0], u_img, v_img)
        if radiometric:
            # Float32 temperature data - no clipping
            samp[..., 0][good] = vals[good].astype(img.dtype)
        else:
            # uint8 image data - clip to 0-255
            samp[..., 0][good] = np.clip(vals[good], 0, 255).astype(img.dtype)
    else:
        for c in range(img.shape[2]):
            vals = bilinear_sample(img[..., c], u_img, v_img)
            if radiometric:
                # Float32 temperature data - no clipping
                samp[..., c][good] = vals[good].astype(img.dtype)
            else:
                # uint8 image data - clip to 0-255
                samp[..., c][good] = np.clip(vals[good], 0, 255).astype(img.dtype)

    # Build mask band (0=transparent, 255=opaque)
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[good] = 255

    # Write GeoTIFF with proper mask band
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    profile = {
        "driver": "GTiff",
        "width": w,
        "height": h,
        "count": img.shape[2],
        "dtype": str(samp.dtype),
        "crs": crs,
        "transform": out_transform,
        "compress": "DEFLATE",
        "predictor": 2,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "BIGTIFF": "IF_SAFER",
        "photometric": "MINISBLACK" if img.shape[2] == 1 else "RGB",
    }

    with rasterio.open(out_path, "w", **profile) as dst:
        for b in range(img.shape[2]):
            dst.write(samp[..., b], b + 1)
        dst.write_mask(mask)

    # Populate info dict
    info.update({
        "image": str(image_path),
        "out": str(out_path),
        "yaw": yaw,
        "pitch": pitch,
        "roll": roll,
        "hfov_deg": hfov_deg,
        "vfov_deg": vfov_deg,
        "pixel_size": pixel_size,
        "aoi_bounds": [x0, y0, x1, y1],
        "width": w,
        "height": h,
        "crs": str(crs),
        "mono": mono,
        "pre_blur": pre_blur,
        "strict_bounds": strict_bounds,
        "tight_crop": tight_crop,
        "snap_to_dsm_grid": snap_to_dsm_grid,
        "radiometric": radiometric,
        "dtype": str(samp.dtype),
    })

    return info


# ========================= Boresight Calibration from LRF =========================

def _ecef_from_llh(lat_deg: float, lon_deg: float, h_m: float) -> np.ndarray:
    """Convert lat/lon/height to ECEF (Earth-Centered Earth-Fixed) coordinates."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    a = 6378137.0  # WGS84 semi-major axis
    f = 1 / 298.257223563  # WGS84 flattening
    e2 = f * (2 - f)
    s = math.sin(lat)
    c = math.cos(lat)
    N = a / math.sqrt(1 - e2 * s * s)
    X = (N + h_m) * c * math.cos(lon)
    Y = (N + h_m) * c * math.sin(lon)
    Z = (N * (1 - e2) + h_m) * s
    return np.array([X, Y, Z], dtype=float)


def _enu_R(lat_deg: float, lon_deg: float) -> np.ndarray:
    """Rotation matrix from ECEF to ENU (East-North-Up) frame."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sl, cl = math.sin(lat), math.cos(lat)
    slon, clon = math.sin(lon), math.cos(lon)
    R = np.array([
        [-slon, clon, 0],
        [-sl * clon, -sl * slon, cl],
        [cl * clon, cl * slon, sl],
    ])
    return R


def _wrap180(x: float) -> float:
    """Wrap angle to [-180, 180) degrees."""
    y = (x + 180.0) % 360.0 - 180.0
    return y


def estimate_boresight(poses_csv: Path) -> dict:
    """
    Estimate boresight calibration (Δyaw, Δpitch) using LRF measurements.

    Uses laser rangefinder (LRF) target positions to compute the systematic
    offset between reported camera pointing and actual pointing direction.

    Args:
        poses_csv: Path to poses CSV with LRF target data

    Returns:
        Dict with statistics (mean, median, percentiles) for yaw/pitch bias
        and suggested boresight correction values.

    Raises:
        ValueError: If required columns missing from CSV
    """
    df = pd.read_csv(poses_csv)
    cols = {k: _find_col(df, v) for k, v in POSE_COLS.items()}

    # Check for required columns
    required = [
        "GPSLatitude", "GPSLongitude", "AbsoluteAltitude",
        "FlightYawDegree", "FlightPitchDegree",
        "GimbalYawDegree", "GimbalPitchDegree",
        "LRFTargetLat", "LRFTargetLon", "LRFTargetAbsAlt"
    ]
    missing = [k for k in required if cols.get(k) is None]
    if missing:
        raise ValueError(f"Missing required columns for boresight: {missing}")

    # Extract camera pointing angles
    yaw_cam = (
        df[cols["FlightYawDegree"]].astype(float) +
        df[cols["GimbalYawDegree"]].astype(float)
    ).values
    pitch_cam = (
        df[cols["FlightPitchDegree"]].astype(float) +
        df[cols["GimbalPitchDegree"]].astype(float)
    ).values

    # Extract camera positions
    lat = df[cols["GPSLatitude"]].astype(float).values
    lon = df[cols["GPSLongitude"]].astype(float).values
    h = df[cols["AbsoluteAltitude"]].astype(float).values

    # Extract LRF target positions
    lrf_lat = df[cols["LRFTargetLat"]].astype(float).values
    lrf_lon = df[cols["LRFTargetLon"]].astype(float).values
    lrf_alt = df[cols["LRFTargetAbsAlt"]].astype(float).values

    # Compute LRF vector yaw/pitch for each frame
    yaw_lrf = []
    pitch_lrf = []
    for i in range(len(df)):
        C = _ecef_from_llh(lat[i], lon[i], h[i])
        T = _ecef_from_llh(lrf_lat[i], lrf_lon[i], lrf_alt[i])
        Renu = _enu_R(lat[i], lon[i])
        d_enu = Renu @ (T - C)
        den = np.linalg.norm(d_enu)

        if not np.isfinite(den) or den == 0:
            yaw_lrf.append(np.nan)
            pitch_lrf.append(np.nan)
            continue

        e, n, u = d_enu / den
        yaw_lrf.append(math.degrees(math.atan2(e, n)))
        pitch_lrf.append(math.degrees(math.asin(u)))

    yaw_lrf = np.array(yaw_lrf)
    pitch_lrf = np.array(pitch_lrf)

    # Compute biases
    dyaw = _wrap180(yaw_lrf - yaw_cam)
    dpitch = _wrap180(pitch_lrf - pitch_cam)

    def _robust_stats(x):
        """Compute robust statistics for bias distribution."""
        x = x[np.isfinite(x)]
        if len(x) == 0:
            return {"n": 0}
        return {
            "n": int(len(x)),
            "mean": float(np.mean(x)),
            "median": float(np.median(x)),
            "p68": float(np.percentile(x, 68)),
            "p95": float(np.percentile(x, 95)),
        }

    return {
        "frames": int(len(df)),
        "yaw_bias_deg": _robust_stats(dyaw),
        "pitch_bias_deg": _robust_stats(dpitch),
        "suggest_boresight_deg": [
            float(np.nanmedian(dyaw)),
            float(np.nanmedian(dpitch)),
            0.0
        ]
    }
