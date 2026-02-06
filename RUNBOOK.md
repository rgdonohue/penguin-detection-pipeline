# RUNBOOK — Penguin Detection Pipeline

**Single source of truth for commands that actually work.**

Last updated: 2025-12-17

---

## Test Suite Status

| Test | Status | Notes |
|------|--------|-------|
| `tests/test_golden_aoi.py` | PASSING | Golden AOI regression guardrail (cloud3.las is sourced from `data/legacy_ro/`) |
| `tests/test_lidar_dem_hag_unit.py` | PASSING | Unit coverage for DEM/HAG edge cases |
| `tests/test_thermal.py` | PASSING | GDAL-dependent tests may skip |
| `tests/test_thermal_radiometric.py` | PASSING | Data-dependent integration cases may skip |
| `tests/test_data_2025_invariants.py` | PASSING | Asserts catalogue + ground truth totals |

Quick run:
```bash
source .venv/bin/activate
.venv/bin/python -m pytest -q tests/test_golden_aoi.py tests/test_data_2025_invariants.py
```

---

## Prerequisites

- Python 3.12.x (verify: `python3.12 --version`)
- Git (to clone/navigate repo)
- pip (comes with Python)

---

## Setup (One-Time)

### Automated Setup (Recommended)

```bash
# Run automated environment validation
./scripts/validate_environment.sh

# This script will:
# 1. Check Python 3.12 is available
# 2. Create .venv virtual environment if needed
# 3. Install dependencies from requirements.txt
# 4. Validate all required modules
# 5. Check legacy data mounts
# 6. Run LiDAR smoke test (776 detections expected on golden AOI)
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
.venv/bin/python -c "import laspy, scipy, skimage, pytest; print('✓ Dependencies installed')"

# Run golden AOI tests
.venv/bin/python -m pytest tests/test_golden_aoi.py -v
```

### Manual Setup: Option 2 - Direct venv Creation

```bash
# Create virtual environment
python3.12 -m venv .venv

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
- Python 3.12.x
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
.venv/bin/python -m pytest tests/test_golden_aoi.py -v
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
  --emit-geojson --crs-epsg 32720 --plots --strict-outputs
```

**Production policy:** do not use `--allow-unknown-crs` or `--skip-oversized-tiles` for final counts.

**Expected output:**
```json
{
  "files": 1,
  "total_count": 776
}
```

**Generated files:**
- `data/interim/lidar_test.json` - Detection results
- `data/interim/lidar_hag_geojson/cloud3_detections.geojson` - Spatial data
- `data/interim/lidar_hag_plots/cloud3_hag.png` - HAG visualization
- `data/interim/lidar_hag_plots/cloud3_hag_detect.png` - Detections overlay
- `data/interim/provenance_lidar.json` - Run metadata
- `data/interim/timings.json` - Performance data

**Status:** ✅ TESTED (legacy: 2025-10-08; Argentina: 2025-12-10)

### 1b. LiDAR Output Semantics + “Official” Determinism Policy

LiDAR outputs are explicitly **candidates**, not guaranteed individuals:
- Contract is embedded in summary JSON under `contract` and defined in `pipelines/contracts.py`.

For “official/defensible” runs where strict reproducibility matters, prefer deterministic estimators:
- Recommended: `--ground-method p05 --top-method max`
- Treat `--top-method p95` as **experimental** (streaming quantile sensitivity to chunking/order).

Reference policy constants: `pipelines/lidar_profiles.py` (`OFFICIAL_DETERMINISTIC`).

### 1b2. CRS Audit

Audit embedded CRS metadata across all LAS files:

```bash
source .venv/bin/activate

python scripts/audit_crs.py --data-root data/2025/ --json-out data/processed/crs_audit.json
```

### 1b3. LiDAR with Intensity Extraction

Extract per-cell mean intensity grid and enrich detections with intensity features:

```bash
python3 scripts/run_lidar_hag.py \
  --data-root "data/2025/Caleta Tiny Island" \
  --out data/interim/caleta_tiny_intensity.json \
  --cell-res 0.25 --hag-min 0.28 --hag-max 0.48 \
  --min-area-cells 3 --max-area-cells 60 \
  --dedupe-radius-m 0.5 --crs-epsg 32720 \
  --extract-intensity --verbose
```

### 1b4. LiDAR with Confidence Scoring

Add per-detection confidence scores:

```bash
python3 scripts/run_lidar_hag.py \
  --data-root "data/2025/Caleta Tiny Island" \
  --out data/interim/caleta_tiny_scored.json \
  --cell-res 0.25 --hag-min 0.28 --hag-max 0.48 \
  --min-area-cells 3 --max-area-cells 60 \
  --dedupe-radius-m 0.5 --crs-epsg 32720 \
  --compute-confidence --verbose
```

### 1b5. Parameter Sensitivity Sweep

Run parameter sweep on a single tile:

```bash
python scripts/lidar_parameter_sweep.py \
  --las-file data/legacy_ro/penguin-2.0/data/raw/LiDAR/sample/cloud3.las \
  --out-dir qc/panels/parameter_sensitivity \
  --verbose
```

### 1b6. Intensity Analysis

Plot intensity distributions across sites:

```bash
python scripts/analyze_lidar_intensity.py \
  --inputs data/interim/caleta_tiny_intensity.json data/interim/caleta_small_intensity.json \
  --labels "Caleta Tiny" "Caleta Small" \
  --out-dir qc/panels/intensity_analysis
```

### 1b7. San Lorenzo AOI Generation

Regenerate San Lorenzo AOIs (includes Bushes box):

```bash
python scripts/create_san_lorenzo_aois.py \
  --output data/processed/aoi_san_lorenzo_epsg5345.geojson
```

### 1b8. Precision Estimation

Estimate precision from labeled samples:

```bash
python scripts/estimate_precision.py \
  --label-csvs data/interim/lidar_label_samples/bushes_box/label_sample.csv \
  --site-labels "Bushes Box" \
  --candidate-counts 45 \
  --out data/processed/precision_estimates.json
```

### 1c. AOI-Clipped Evaluation (QC / Alignment)

Compute counts/densities inside AOI polygons (GeoJSON FeatureCollection). AOIs must be in the **same CRS** as the LiDAR detections (typically projected meters).

```bash
source .venv/bin/activate

python scripts/evaluate_lidar_aoi.py \
  --lidar-summary data/interim/lidar_test.json \
  --aoi-geojson path/to/aoi_polygons.geojson \
  --aoi-crs-epsg 32720 \
  --out data/interim/lidar_aoi_eval.json
```

### 1e. Derive Island AOI from LiDAR Footprint (Caleta-style)

When the counted region is a closed natural boundary (e.g., an island), you can derive an AOI polygon directly from LiDAR coverage in the same projected CRS.

```bash
source .venv/bin/activate

PYTHONPATH=. python scripts/extract_lidar_island_aoi.py \
  --data-root "data/2025/Caleta Small Island" \
  --out data/processed/aoi_caleta_small_island_epsg32720.geojson \
  --crs-epsg 32720 \
  --aoi-id caleta_small_island \
  --threshold-method fixed \
  --min-points-per-cell 1 \
  --cell-res-m 1.0
```

If the LiDAR folder includes nearby mainland and you only want the island component, pass a detections summary to select the connected component nearest those detections:

```bash
PYTHONPATH=. python scripts/extract_lidar_island_aoi.py \
  --data-root "data/2025/Caleta Tiny Island" \
  --out data/processed/aoi_caleta_tiny_island_epsg32720.geojson \
  --crs-epsg 32720 \
  --aoi-id caleta_tiny_island \
  --threshold-method otsu \
  --roi-from-detections data/interim/tiny_best.json \
  --roi-buffer-m 60 \
  --cell-res-m 1.0
```

If you want the exact detections included in each AOI (can be large):

```bash
python scripts/evaluate_lidar_aoi.py \
  --lidar-summary data/interim/lidar_test.json \
  --aoi-geojson path/to/aoi_polygons.geojson \
  --aoi-crs-epsg 32720 \
  --emit-detection-ids \
  --out data/interim/lidar_aoi_eval_with_ids.json
```

### 1d. LiDAR Label-Sample Export (Precision / FP-Rate Bootstrap)

Export a deterministic, stratified sample of detections for manual labeling (TP/FP/uncertain), plus optional small PNG crops.

```bash
source .venv/bin/activate

python scripts/export_lidar_label_sample.py \
  --lidar-summary data/interim/lidar_test.json \
  --out-dir data/interim/lidar_label_sample \
  --n 80 \
  --seed 0
```

Fast mode (no crops):

```bash
python scripts/export_lidar_label_sample.py \
  --lidar-summary data/interim/lidar_test.json \
  --out-dir data/interim/lidar_label_sample \
  --n 80 \
  --seed 0 \
  --no-crops
```

Notes:
- Crops are best-effort; the primary artifacts are `label_sample.csv` and `label_sample_manifest.json`.
- Crop generation streams the LAS file referenced by each detection’s `file` field; keep those paths accessible.

---

## Argentina LiDAR Detection (Validated 2025-12-10)

### DJI L2 Sensors (Caleta Sites)

Tuned parameters for DJI L2 LiDAR (Caleta Tiny Island, Small Island, Box Counts):

```bash
source .venv/bin/activate

# Caleta Small Island (validated: 1,473 detections vs 1,557 ground truth = -5%)
python3 scripts/run_lidar_hag.py \
  --data-root "data/2025/Caleta Small Island" \
  --out data/interim/caleta_small_island.json \
  --cell-res 0.25 --hag-min 0.28 --hag-max 0.48 \
  --min-area-cells 3 --max-area-cells 60 \
  --dedupe-radius-m 0.5 --emit-geojson --crs-epsg 32720 --plots

# Caleta Tiny Island (341 detections vs 321 ground truth = +6%)
python3 scripts/run_lidar_hag.py \
  --data-root "data/2025/Caleta Tiny Island" \
  --out data/interim/caleta_tiny_island.json \
  --cell-res 0.25 --hag-min 0.28 --hag-max 0.48 \
  --min-area-cells 3 --max-area-cells 60 \
  --dedupe-radius-m 0.5 --emit-geojson --crs-epsg 32720 \
  --top-method max --skip-copc --plots
```

**Key DJI L2 Parameters:**
- Cell resolution: 0.25m
- HAG range: 0.28-0.48m (narrower than legacy 0.2-0.6m)
- Min area: 3 cells
- Dedupe radius: 0.5m (prevents double-counting at tile boundaries)

### TrueView 515 Sensors (San Lorenzo)

TrueView 515 data requires CRS reprojection from POSGAR to UTM:

```bash
# Step 1: Reproject from POSGAR 2007/Argentina 3 to UTM 20S
pdal translate "data/2025/San Lorenzo Box Count 11.9.25 LAS.las" \
  "data/2025/San_Lorenzo_UTM/box_count_11.9.las" \
  --filters.reprojection.in_srs="EPSG:5345" \
  --filters.reprojection.out_srs="EPSG:32720" \
  -f filters.reprojection

# Step 2: Run detection (1,297 detections across 2 tiles — under investigation)
# NOTE: Previous claim of "108 detections" is not reproducible with current code.
# The 87 ground-truth penguins are spread across ~5 ha; high detection count
# likely reflects dense bush vegetation in the HAG band.
python3 scripts/run_lidar_hag.py \
  --data-root "data/2025/San_Lorenzo_UTM" \
  --out data/interim/san_lorenzo_box_count.json \
  --cell-res 0.3 --hag-min 0.28 --hag-max 0.48 \
  --min-area-cells 3 --max-area-cells 50 \
  --dedupe-radius-m 0.5 --emit-geojson --crs-epsg 32720 \
  --top-method max --plots
```

**Key TrueView 515 Parameters:**
- Cell resolution: 0.30m (larger than DJI L2 due to different point density)
- HAG range: 0.28-0.48m
- Requires PDAL for CRS reprojection

**Data Catalogue:**
- Location: `data/2025/lidar_catalogue_full.json`
- Total: 24 source LAS files, ~762M points, ~25.5 GB (plus COPC/UTM copies)
- Session report: `docs/reports/SESSION_2025-12-10_LIDAR_TUNING.md`

---

## AOI + Coverage Web Map (2025)

Generate the AOI catalogue and LiDAR coverage layers, then build the interactive map:

```bash
source .venv/bin/activate

# 1) AOI catalogue (WGS84 with confidence metadata)
python scripts/create_aoi_catalogue.py \
  --output data/processed/aoi_catalogue_wgs84.geojson

# 2) LiDAR coverage extents + thermal targets (WGS84)
# Extract LiDAR coverage extents (bounding boxes - fast)
PYTHONPATH=. python scripts/extract_lidar_coverage.py \
  --data-root data/2025 \
  --output data/processed/lidar_coverage_wgs84.geojson \
  --include-thermal

# Extract LiDAR coverage outlines (actual data footprint - slower but more accurate)
PYTHONPATH=. python scripts/extract_lidar_coverage.py \
  --data-root data/2025 \
  --output data/processed/lidar_coverage_wgs84.geojson \
  --outline-mode outline \
  --cell-res 2.0 \
  --simplify-tol 5.0 \
  --include-thermal

# 3) Build the web map
python scripts/create_argentina_map.py \
  --lidar-coverage data/processed/lidar_coverage_wgs84.geojson \
  --aoi-catalogue data/processed/aoi_catalogue_wgs84.geojson \
  --output qc/panels/argentina_aoi_overview.html
```

**Study sites static map (README image):** requires `contextily` (see `requirements-full.txt`).

```bash
python scripts/create_study_sites_map.py
# Output: qc/panels/study_sites_map.png
```

---

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
conda create -n penguins-thermal python=3.12
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

## Experiments

### Ground Model Comparison (min vs p05 vs CSF)

```bash
python scripts/experiments/compare_ground_models.py \
  --tile "data/2025/Caleta Tiny Island/cloud0.las" \
  --out data/interim/ground_model_comparison_caleta.json --crs-epsg 32720
```

Requires `cloth-simulation-filter` for CSF; min and p05 run regardless. Outputs JSON + multi-panel comparison PNG.

### Resolution Sweep

```bash
python scripts/experiments/resolution_sweep.py \
  --tile "data/2025/Caleta Tiny Island/cloud0.las" \
  --out data/interim/resolution_sweep_caleta.json --crs-epsg 32720
```

Tests cell sizes [0.10, 0.15, 0.20, 0.25, 0.30] m. Self-contained density stats per resolution.

### Watershed Parameter Sweep

```bash
python scripts/experiments/watershed_sweep.py \
  --data-root "data/2025/Caleta Tiny Island" \
  --aoi data/processed/aoi_caleta_tiny_island_epsg32720.geojson \
  --out data/interim/watershed_sweep_caleta_tiny.json --crs-epsg 32720 \
  --field-count 321
```

21 configurations (1 baseline + 20 watershed combos). Uses AOI-clipped counts.

### HAG Histogram Analysis

```bash
python scripts/experiments/hag_histogram.py \
  --tile "data/2025/Caleta Tiny Island/cloud0.las" \
  --out data/interim/hag_histogram_caleta.json \
  --plot data/interim/hag_histogram_caleta.png --crs-epsg 32720
```

Per-tile HAG distribution with peak detection and suggested threshold range.

### Density Stats

Add `--density-stats` to any `run_lidar_hag.py` invocation to include per-tile density metrics (`total_points`, `density_pts_per_m2`, `mean_pts_per_cell`, `pct_empty_cells`, `min/max_pts_per_cell`) in the output JSON.

```bash
python3 scripts/run_lidar_hag.py \
  --data-root "data/2025/Caleta Tiny Island" \
  --out data/interim/caleta_tiny_density.json \
  --cell-res 0.25 --hag-min 0.28 --hag-max 0.48 \
  --min-area-cells 3 --max-area-cells 60 \
  --dedupe-radius-m 0.5 --crs-epsg 32720 \
  --density-stats
```

---

## Not Yet Implemented

These commands are planned but don't work yet:

```bash
# ❌ NOT WORKING - scripts don't exist
# make harvest      - Automated legacy data import with checksums
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
# Golden AOI file (cloud3.las, ~4.4 GB)
data/legacy_ro/penguin-2.0/data/raw/LiDAR/cloud3.las

# Full dataset (35 GB total)
data/legacy_ro/penguin-2.0/data/raw/LiDAR/cloud[0-4].las
```

### H30T Thermal Test Flights

```
data/legacy_ro/H30T_Test_Files/                    # Client drop (read-only)
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
# QC golden guardrail (engineering harness)
make golden

# Check detection count
jq '.total_count' data/interim/lidar_test.json

# Expected: 776

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

## Experiment Scripts

### Resolution Sweep

```bash
# Test detection at varying cell sizes (0.10-0.30 m)
.venv/bin/python scripts/experiments/resolution_sweep.py \
  --tile "data/2025/Caleta Tiny Island/cloud0.las" \
  --out data/interim/resolution_sweep_caleta.json --crs-epsg 32720

# San Lorenzo (TrueView 515)
.venv/bin/python scripts/experiments/resolution_sweep.py \
  --tile "data/2025/San_Lorenzo_UTM/box_count_11.9.las" \
  --out data/interim/resolution_sweep_san_lorenzo.json --crs-epsg 32720
```

### Ground Model Comparison

```bash
# Compare min vs p05 (vs CSF if installed) ground models
.venv/bin/python scripts/experiments/compare_ground_models.py \
  --tile "data/2025/Caleta Tiny Island/cloud0.las" \
  --out data/interim/ground_model_comparison_caleta.json --crs-epsg 32720

.venv/bin/python scripts/experiments/compare_ground_models.py \
  --tile "data/2025/San_Lorenzo_UTM/box_count_11.9.las" \
  --out data/interim/ground_model_comparison_san_lorenzo.json \
  --crs-epsg 32720 --cell-res 0.30
```

### HAG Histogram Analysis

```bash
# Per-tile HAG distribution with peak detection
.venv/bin/python scripts/experiments/hag_histogram.py \
  --tile "data/2025/Caleta Tiny Island/cloud0.las" \
  --out data/interim/hag_histogram_caleta.json \
  --plot data/interim/hag_histogram_caleta.png --crs-epsg 32720

.venv/bin/python scripts/experiments/hag_histogram.py \
  --tile "data/2025/San_Lorenzo_UTM/box_count_11.9.las" \
  --out data/interim/hag_histogram_san_lorenzo.json \
  --plot data/interim/hag_histogram_san_lorenzo.png \
  --crs-epsg 32720 --cell-res 0.30
```

### Watershed Sweep

```bash
# Parameter sweep: watershed on/off × h_maxima × min_split_area_cells
.venv/bin/python scripts/experiments/watershed_sweep.py \
  --data-root "data/2025/Caleta Tiny Island" \
  --aoi data/processed/aoi_caleta_tiny_island_epsg32720.geojson \
  --out data/interim/watershed_sweep_caleta_tiny.json --crs-epsg 32720
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
# Tested via unit tests (synthetic inputs); requires CRS `x/y` in both summaries.
python scripts/run_fusion_join.py \
  --lidar-summary path/to/lidar_summary.json \
  --thermal-summary path/to/thermal_summary.json \
  --out data/interim/fusion_rollup.json \
  --match-radius-m 0.5
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

---

**Principle:** Only tested commands go in this file.
