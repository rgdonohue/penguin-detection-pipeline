# RUNBOOK — Penguin Detection Pipeline

**Single source of truth for commands that actually work.**

Last updated: 2025-10-08

---

## Prerequisites

- Python 3.11+ (verify: `python3 --version`)
- Git (to clone/navigate repo)
- pip (comes with Python)

---

## Setup (One-Time)

### Automated Setup (Recommended)

```bash
# Run automated environment validation
./scripts/validate_environment.sh

# This script will:
# 1. Check Python 3.11+ is available
# 2. Create .venv virtual environment if needed
# 3. Install dependencies from requirements.txt
# 4. Validate all required modules
# 5. Check legacy data mounts
# 6. Run LiDAR smoke test (879 detections expected)
# 7. Run golden AOI test suite (12 tests)
```

**Status:** ✅ Validation script tested (2025-10-10, venv-based)

### Manual Setup: Option 1 - Using Makefile (Recommended)

```bash
# Navigate to project root
cd /Users/richard/Documents/projects/penguins-4.0

# Create venv and install dependencies
make env

# Activate environment
source .venv/bin/activate

# Verify installation
python3 -c "import laspy, scipy, skimage, pytest; print('✓ Dependencies installed')"

# Run golden AOI tests
pytest tests/test_golden_aoi.py -v
```

### Manual Setup: Option 2 - Direct venv Creation

```bash
# Create virtual environment
python3 -m venv .venv

# Activate environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run validation
./scripts/validate_environment.sh
```

### Manual Setup: Option 3 - System-wide Install (Not Recommended)

```bash
# Install core dependencies globally
pip install laspy scipy scikit-image numpy matplotlib pytest

# Note: This skips isolation and may conflict with other projects
```

**Core dependencies (LiDAR stage):**
- Python 3.11+
- laspy >= 2.4.0 (LiDAR I/O)
- scipy >= 1.10.0 (scientific computing)
- scikit-image >= 0.20.0 (image processing)
- numpy >= 1.24.0, matplotlib >= 3.7.0 (numerics + plotting)
- pytest >= 7.3.0 (testing framework)

**Additional dependencies (Thermal/Fusion stages):**
- See `requirements-full.txt` for GDAL, rasterio, geopandas (install when needed)

---

## Working Commands

### 0. Environment Validation

```bash
# One-command validation (checks everything)
./scripts/validate_environment.sh

# Manual validation steps
source .venv/bin/activate
pytest tests/test_golden_aoi.py -v
make test-lidar
```

**Status:** ✅ VALIDATED (2025-10-10) - venv-based, 12 tests

### 1. LiDAR Detection (Proven)

```bash
# Using Makefile (requires environment set up)
make test-lidar

# Or direct invocation:
python3 scripts/run_lidar_hag.py \
  --data-root data/legacy_ro/penguin-2.0/data/raw/LiDAR/sample \
  --out data/interim/lidar_test.json \
  --cell-res 0.25 \
  --hag-min 0.2 --hag-max 0.6 \
  --min-area-cells 2 --max-area-cells 80 \
  --emit-geojson --plots
```

**Expected output:**
```json
{
  "files": 1,
  "total_count": 879
}
```

**Generated files:**
- `data/interim/lidar_test.json` - Detection results
- `data/interim/lidar_hag_geojson/cloud3_detections.geojson` - Spatial data
- `data/interim/lidar_hag_plots/cloud3_hag.png` - HAG visualization
- `data/interim/lidar_hag_plots/cloud3_hag_detect.png` - Detections overlay
- `data/interim/provenance_lidar.json` - Run metadata
- `data/interim/timings.json` - Performance data

**Status:** ✅ TESTED (2025-10-08, 3 successful runs)

### 2. Thermal Orthorectification (Extracted, Not Yet Tested)

**⚠️  REQUIRES GDAL INSTALLATION (see below)**

**Note:** CLI will exit with error before showing --help if GDAL not installed. This is intentional - install GDAL first to access commands.

```bash
# Export DJI thermal metadata to CSV first (requires exiftool)
exiftool -n -csv -G1 -a -s -ee \
  -XMP:CreateDate -XMP-drone-dji:GPSLatitude -XMP-drone-dji:GPSLongitude \
  -XMP-drone-dji:AbsoluteAltitude -XMP-drone-dji:RelativeAltitude \
  -XMP-drone-dji:GimbalYawDegree -XMP-drone-dji:GimbalPitchDegree -XMP-drone-dji:GimbalRollDegree \
  -XMP-drone-dji:FlightYawDegree -XMP-drone-dji:FlightPitchDegree -XMP-drone-dji:FlightRollDegree \
  -XMP-drone-dji:LRFTargetLat -XMP-drone-dji:LRFTargetLon -XMP-drone-dji:LRFTargetAbsAlt -XMP-drone-dji:LRFTargetDistance \
  data/thermal/*.JPG > data/thermal/poses.csv

# Estimate boresight calibration from LRF measurements (optional but recommended)
python scripts/run_thermal_ortho.py boresight \
  --poses data/thermal/poses.csv
# Output: suggested boresight values (e.g., "-24.18,6.66,0")

# Orthorectify single frame
python scripts/run_thermal_ortho.py ortho-one \
  --image data/thermal/DJI_0001_T.JPG \
  --poses data/thermal/poses.csv \
  --dsm data/processed/lidar/dsm.tif \
  --out data/processed/thermal/ortho_0001.tif \
  --boresight "-24.18,6.66,0" \
  --snap-grid

# Verify grid alignment
python scripts/run_thermal_ortho.py verify-grid \
  --dsm data/processed/lidar/dsm.tif \
  --ortho data/processed/thermal/ortho_0001.tif
```

**Status:** 🔨 CODE EXTRACTED (2025-10-10), awaiting GDAL install + testing

#### GDAL/Rasterio Installation

**Thermal processing requires GDAL**, which has complex system dependencies. Choose one method:

##### Method 1: Conda (RECOMMENDED)

```bash
# Create new conda environment with GDAL pre-built
conda create -n penguins-thermal python=3.11
conda activate penguins-thermal

# Install GDAL stack from conda-forge
conda install -c conda-forge gdal rasterio pyproj geopandas

# Install remaining dependencies
pip install -r requirements.txt

# Verify installation
python -c "import rasterio, pyproj; print('✓ GDAL stack installed')"

# Run thermal tests (should pass, not skip)
pytest tests/test_thermal.py -v
```

##### Method 2: System GDAL + pip (Advanced)

```bash
# Install system GDAL first
# macOS:
brew install gdal

# Ubuntu:
sudo apt-get install gdal-bin libgdal-dev

# Fedora:
sudo dnf install gdal gdal-devel

# Then install Python bindings (version must match!)
GDAL_VERSION=$(gdal-config --version)
pip install gdal==$GDAL_VERSION
pip install rasterio pyproj geopandas

# Verify
python -c "import rasterio; print('✓ GDAL installed')"
```

**Note:** See `requirements-full.txt` for detailed installation instructions and troubleshooting.

---

## Thermal Detection Commands

### Thermal Parameter Optimization

Optimize detection parameters using ground truth data:

```bash
# Run parameter sweep on validated frames
python scripts/optimize_thermal_detection.py \
  --ground-truth-dir verification_images/ \
  --thermal-dir data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5/ \
  --output data/interim/optimization_results.json \
  --csv-output data/interim/optimization_summary.csv \
  --verbose

# Output includes:
# - data/interim/optimization_results.json (detailed results)
# - data/interim/optimization_summary.csv (summary table)
# - data/interim/optimal_thermal_params.json (best parameters)
```

**Expected output:** F1 scores 0.02-0.30 depending on frame contrast

### Batch Thermal Detection

Process full dataset with optimized parameters:

```bash
# Sequential processing (slower but stable)
python scripts/run_thermal_detection_batch.py \
  --input data/legacy_ro/penguin-2.0/data/raw/thermal-images/ \
  --params data/interim/optimal_thermal_params.json \
  --output data/processed/thermal_detections/ \
  --checkpoint-every 100 \
  --verbose

# Parallel processing (faster, requires multicore)
python scripts/run_thermal_detection_batch.py \
  --input data/legacy_ro/penguin-2.0/data/raw/thermal-images/ \
  --params data/interim/optimal_thermal_params.json \
  --output data/processed/thermal_detections/ \
  --parallel 4 \
  --checkpoint-every 100

# Resume from checkpoint after interruption
python scripts/run_thermal_detection_batch.py \
  --input data/legacy_ro/penguin-2.0/data/raw/thermal-images/ \
  --params data/interim/optimal_thermal_params.json \
  --output data/processed/thermal_detections/ \
  --resume \
  --parallel 4

# Test on subset first
python scripts/run_thermal_detection_batch.py \
  --input data/legacy_ro/penguin-2.0/data/raw/thermal-images/ \
  --params data/interim/optimal_thermal_params.json \
  --output data/processed/thermal_test/ \
  --limit 100 \
  --verbose
```

**Outputs:**
- `all_detections.csv` - All individual detections with coordinates
- `frame_counts.csv` - Per-frame detection counts
- `detection_summary.json` - Statistics and total count
- `checkpoints/` - Resume capability

**Expected:** Total count within 20% of 1533 target

### Thermal Smoke Test

Run a quick sanity check on the staged H30T frames:

```
make thermal
```

This invokes `scripts/run_thermal_smoketest.py`, summarising one frame per intake subdirectory and writing stats to `data/interim/thermal_smoketest.json`. High-contrast frames still emit a warning when the heuristic scale (96.0) is applied—review the JSON if values look off.

---

## Not Yet Implemented

These commands are planned but don't work yet:

```bash
# ❌ NOT WORKING - scripts don't exist
# make harvest      - Automated legacy data import with checksums
# make fusion       - LiDAR + thermal fusion analysis
# make golden       - Full end-to-end pipeline on golden AOI
# make rollback     - Restore from .rollback/ snapshot
```

**Note:** `make test` and `make validate` are now working (added 2025-10-10).

See `STATUS.md` for details on missing pieces.

---

## Data Access

### Legacy Projects (Read-Only)

```bash
# View mounted legacy projects
ls -l data/legacy_ro/

# Available:
# - penguin-2.0/        (has working LiDAR scripts + data)
# - penguin-3.0/        (most recent project)
# - thermal-lidar-fusion/ (failed attempt, may have pieces)
# - penguin-thermal-og/ (original, may have working LiDAR)
```

### LiDAR Test Data

```bash
# Sample data (4.4 GB)
data/legacy_ro/penguin-2.0/data/raw/LiDAR/sample/cloud3.las

# Full dataset (35 GB total)
data/legacy_ro/penguin-2.0/data/raw/LiDAR/cloud[0-4].las
```

### H30T Thermal Test Flights

```
data/H30T_Test_Files/                              # Client drop (read-only)
├── DJI_202510221803_001_Create-Area-Route27/      # Normal radiometric capture
├── DJI_202510221803_002_Create-Area-Route27/      # High-contrast digital gain
└── DJI_202510221803_003/                          # Stills with mode toggles

data/intake/h30t/                                  # Symlinks for reproducible runs
├── flight_001/normal_0001_T.JPG                   # 1280×1024, scale 64.0
├── flight_002/high_contrast_0001_T.JPG            # 1280×1024, scale 96.0 heuristic
└── stills/toggle_0001_T.JPG                       # Mixed modes for regression tests
```

*Pipelines:* `pipelines/thermal.extract_thermal_frame` now auto-detects H30T payloads and rescales high-contrast frames (warns when heuristics kick in). Run `python -m pytest -q tests/test_thermal_radiometric.py` after any thermal changes to confirm coverage for both modes.

**Status (2025-10-23):** Flight 001 radiometry aligns with the legacy transfer function. Flight 002 (high-contrast) decodes with a different gain bucket (96.0, single 80.0 transition frame) and shows a very wide °C span; treated as relative-only until the client supplies ground references or DJI TA3 exports to validate calibration.

---

## Troubleshooting

### Import Errors (laspy, scipy, skimage)

**Problem:** `ModuleNotFoundError: No module named 'laspy'`

**Solution:** Environment not set up. Run setup steps above.

### Python Command Not Found

**Problem:** `pyenv: python: command not found`

**Solution:** Use `python3` instead of `python`, or set up pyenv global.

### Permission Denied (legacy_ro)

**Problem:** Can't modify files in `data/legacy_ro/`

**Expected:** This is intentional (read-only). Copy to `data/intake/` instead.

---

## Quality Control

### Verify LiDAR Output

```bash
# Check detection count
jq '.total_count' data/interim/lidar_test.json

# Expected: 879

# Check file sizes
ls -lh data/interim/lidar_hag_plots/
# Should see two PNG files (~500KB each)
```

### Clean Interim Files

```bash
make clean

# Or manually:
rm -rf data/interim/*
```

---

## Next Pipeline Stages (To Be Added)

### When Harvest Script Exists

```bash
# Not yet implemented
# python scripts/harvest_legacy.py --config manifests/harvest_rules.yml
```

### When Thermal Script Exists

```bash
# Not yet implemented
# python scripts/run_thermal_ortho_pilot.py \
#   --frames data/intake/thermal/subset/*.tif \
#   --poses data/intake/thermal/poses.csv \
#   --dsm data/intake/lidar/dsm.tif \
#   --max-tiepoints 12 --rmse-threshold 2.0 \
#   --out-dir data/processed/thermal
```

### When Fusion Script Exists

```bash
# Not yet implemented
# python scripts/run_fusion_join.py \
#   --candidates data/processed/lidar/candidates.gpkg \
#   --thermal-vrt data/processed/thermal/thermal.vrt \
#   --px-window 2 \
#   --out data/processed/fusion/fusion.csv \
#   --qc-panel qc/panels/fusion_aoi.png
```

---

## DORA Principle: Incremental Growth

This RUNBOOK grows as scripts are proven to work:

1. ✅ Write script
2. ✅ Test on sample data
3. ✅ Document command here
4. ⏳ Add to Makefile
5. ⏳ Add automated tests

**No command gets documented until it's tested.**

---

## Validation Checklist

Before adding a new command to this RUNBOOK:

- [ ] Script exists and has correct dependencies
- [ ] Command runs without errors on test data
- [ ] Outputs match expected format/size
- [ ] Run tested at least once successfully
- [ ] Parameters match PRD specifications
- [ ] Error handling tested (missing files, bad params)

---

## Emergency Recovery

If something breaks:

```bash
# 1. Clean interim files
make clean

# 2. Re-run working LiDAR test
make test-lidar

# 3. If that fails, environment is broken
# Recreate venv:
rm -rf .venv
make env
source .venv/bin/activate
```

---

## Contact / Support

See PRD.md for project requirements.
See STATUS.md for current implementation state.
See AI_POLICY.md for collaboration with AI assistants.

---

**Principle:** Only tested commands go in this file.
