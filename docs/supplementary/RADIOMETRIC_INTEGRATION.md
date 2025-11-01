# Radiometric Thermal Extraction - Infrastructure Complete ⚠️

**Status**: INFRASTRUCTURE READY, VALIDATION INCOMPLETE
**Date**: 2025-10-13
**Validation**: Partial - positive contrast confirmed, but weak signal (0.05σ)

## Overview

16-bit radiometric thermal data extraction is now fully integrated into `pipelines/thermal.py` and available via the CLI wrapper. The system extracts real temperature data from DJI H20T thermal images instead of the 8-bit JPEG preview.

## What Changed

### Core Pipeline (`pipelines/thermal.py`)

**New Function**: `extract_thermal_data(image_path, temp_dir=None)`
- Extracts ThermalData blob from DJI EXIF (655360 bytes = 640×512×16-bit)
- Converts raw DN values to Celsius: `celsius = (DN >> 2) * 0.0625 - 273.15`
- Returns float32 array (512, 640) with temperature values
- Requires `exiftool` to be installed

**Updated Function**: `ortho_one(..., radiometric=False)`
- New `radiometric` parameter (default: False for backward compatibility)
- When `radiometric=True`:
  - Uses `extract_thermal_data()` instead of `PIL.Image.open()`
  - Ignores `mono` and `pre_blur` parameters
  - Outputs float32 GeoTIFF with temperature in Celsius
  - No 0-255 clipping applied to sampled values

### CLI Wrapper (`scripts/run_thermal_ortho.py`)

**New Flag**: `--radiometric / --no-radiometric`
- Default: `--no-radiometric` (8-bit JPEG preview)
- Enable with `--radiometric` for 16-bit extraction

**Updated Usage**:
```bash
# Radiometric orthorectification (16-bit → float32 Celsius)
python scripts/run_thermal_ortho.py ortho-one \
    --image data/thermal/DJI_0001_T.JPG \
    --poses data/thermal/poses.csv \
    --dsm data/processed/lidar/dsm.tif \
    --out data/processed/thermal/ortho_0001_radiometric.tif \
    --boresight "-24.18,6.66,0" \
    --snap-grid \
    --radiometric
```

### Test Suite (`tests/test_thermal_radiometric.py`)

**Coverage**:
- ✅ Function import and signature validation
- ✅ Frame 0356 extraction (validated ground truth)
- ✅ Pilot frame extraction
- ✅ Error handling (missing files)

**Test Results**: 5/5 passed

## Validation Results

### Frame 0356 Ground Truth Validation

**Ground Truth Status**:
- ⚠️ **Incomplete**: 26/28 penguins extracted from PDF (2 missing)
- CSV: `verification_images/frame_0356_locations.csv`

**Temperature Statistics**:
- Image range: -13.77°C to 12.16°C
- Background: -5.69°C ± 2.91°C
- Penguins: -5.56°C ± 2.21°C
- Thermal contrast: **+0.14°C (0.05σ)** ⚠️

**Critical Issues**:
- ❌ **Weak Signal**: 0.14°C contrast is only 0.05σ - essentially at noise level
- ❌ **No Reproducible Matching**: Hotspot comparison created interactively but no script exists
- ⚠️ **30°C Calibration Offset**: Expected penguin temps 25-30°C, observing -5.56°C
- ❓ **Unclear if Detection Will Work**: Signal-to-noise ratio insufficient to claim "relative contrast sufficient"

**What We Know**:
- ✅ Extraction produces float32 arrays in expected range
- ✅ Positive contrast direction (penguins slightly warmer)
- ❌ Cannot claim detection works until calibration investigated

## Technical Details

### DJI Thermal Format (R-JPEG)

- **Container**: JPEG with embedded EXIF blobs
- **ThermalData**: 655360 bytes (640×512×2 bytes, uint16 little-endian)
- **Conversion Formula**: `celsius = (DN >> 2) * 0.0625 - 273.15`
- **Source**: Open-source implementations (uav4geo/Thermal-Tools, alex-suero/thermal-image-converter)

### Output Format

**Radiometric Mode**:
- Dtype: `float32`
- Units: Degrees Celsius
- CRS: Inherited from DSM
- Compression: DEFLATE with predictor=2
- Mask band: 255=valid, 0=nodata

**Non-Radiometric Mode** (default):
- Dtype: `uint8`
- Units: 8-bit grayscale (0-255)
- Same georeferencing and compression

## Dependencies

**Required**:
- `exiftool` (command-line tool)
  - macOS: `brew install exiftool`
  - Linux: `apt-get install libimage-exiftool-perl`
- Python packages: `numpy`, `subprocess` (stdlib)

**Optional**:
- Calibration refinement: ThermalCalibration blob (32KB, format TBD)

## Known Issues & Blockers

### 1. Weak Thermal Contrast (BLOCKER)

**Issue**: Penguins only 0.14°C warmer than background (0.05σ)
**Impact**: **HIGH** - Signal may be too weak for reliable detection
**Root Cause**: Unknown - likely calibration-related
**Status**: **BLOCKS fusion analysis**

### 2. Calibration Offset (~30°C)

**Issue**: Absolute temperatures ~30°C lower than expected
**Impact**: **UNKNOWN** - May explain weak contrast
**Possible Causes**:
- ThermalCalibration blob not decoded (32KB EXIF data)
- Emissivity setting incorrect (should be 0.98 for penguins)
- Reflective temperature not applied
- Environmental conditions (cold Antarctic day)

**Status**: Requires investigation before proceeding

### 3. Incomplete Ground Truth

**Issue**: Only 26/28 penguins extracted from PDF
**Impact**: MEDIUM - Validation not comprehensive
**Status**: Need to manually find missing 2 penguin locations

### 4. No Reproducible Hotspot Comparison

**Issue**: Hotspot comparison PNG exists but no script to regenerate it
**Impact**: MEDIUM - Can't verify claimed match rates
**Status**: Need to save the comparison code as a script

## Usage Examples

### Basic Radiometric Extraction

```python
from pipelines.thermal import extract_thermal_data
from pathlib import Path
import tempfile

image_path = Path("data/thermal/DJI_0001_T.JPG")

with tempfile.TemporaryDirectory() as tmpdir:
    celsius = extract_thermal_data(image_path, Path(tmpdir))

print(f"Temperature range: {celsius.min():.2f}°C to {celsius.max():.2f}°C")
print(f"Mean: {celsius.mean():.2f}°C ± {celsius.std():.2f}°C")
```

### Radiometric Orthorectification

```python
from pipelines.thermal import ortho_one
from pathlib import Path

info = ortho_one(
    image_path=Path("data/thermal/DJI_0001_T.JPG"),
    poses_csv=Path("data/thermal/poses.csv"),
    dsm_path=Path("data/lidar/dsm.tif"),
    out_path=Path("data/processed/thermal/ortho_radiometric.tif"),
    boresight=(0.0, 0.0, 0.0),
    snap_to_dsm_grid=True,
    radiometric=True  # ← Enable 16-bit extraction
)

print(f"Output dtype: {info['dtype']}")  # 'float32'
print(f"Radiometric: {info['radiometric']}")  # True
```

### CLI Workflow

```bash
# 1. Estimate boresight (if LRF data available)
python scripts/run_thermal_ortho.py boresight \
    --poses data/thermal/poses.csv

# 2. Process with radiometric extraction
python scripts/run_thermal_ortho.py ortho-one \
    --image data/thermal/DJI_0001_T.JPG \
    --poses data/thermal/poses.csv \
    --dsm data/lidar/dsm.tif \
    --out data/processed/thermal/ortho_radiometric.tif \
    --boresight "0,0,0" \
    --snap-grid \
    --radiometric

# 3. Verify grid alignment
python scripts/run_thermal_ortho.py verify-grid \
    --dsm data/lidar/dsm.tif \
    --ortho data/processed/thermal/ortho_radiometric.tif
```

## Next Steps (Before Fusion)

**BLOCKER**: Cannot proceed to fusion until signal quality confirmed

1. ❌ **Complete Ground Truth**: Find missing 2 penguins (26→28 in CSV)
2. ❌ **Create Reproducible Hotspot Script**: Save the comparison code, not just PNG
3. ❌ **Investigate Calibration**: Why 30°C offset? Why only 0.05σ contrast?
   - Decode ThermalCalibration blob (32KB in EXIF)?
   - Check emissivity/reflective temperature settings?
   - Compare with known-good thermal data?
4. ⏳ **Demonstrate Usable SNR**: Show penguins are detectable above noise
5. ⏳ **Update Documentation**: Sync STATUS.md, validation_results.md, this doc

**Not Ready For**: Fusion analysis until we prove thermal signal is usable

## References

- Validation: `data/interim/thermal_validation/hotspot_comparison.png`
- Test suite: `tests/test_thermal_radiometric.py`
- Ground truth: `verification_images/frame_0356_locations.csv`
- Technical docs: `thermal_extraction_progress.md`
