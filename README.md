# Penguin Detection Pipeline

**LiDAR-thermal fusion system for automated penguin detection in drone survey data.**

Version 0.2 | Last Updated: 2025-12-11

---

## Quick Start

### For Field Team (15 Minutes Setup)

```bash
# 1. Clone repository
cd /Users/richard/Documents/projects/penguins-4.0

# 2. Set up environment
make env
source .venv/bin/activate

# 3. Verify installation
make validate

# 4. Process your first LiDAR tile
python scripts/run_lidar_hag.py \
    --data-root field_data/lidar/ \
    --out results/detections.json \
    --plots
```

**Expected outputs:**
- `results/detections.json` - Candidate counts and statistics
- `results/lidar_hag_plots/` - Visual QC plots
- `results/lidar_hag_geojson/` - GIS-compatible spatial layers

**Expected processing time:** 5-15 minutes per tile (depending on size)

---

## What This Pipeline Does

**LiDAR Detection (Production Ready ✅)**
- Processes LiDAR point clouds to detect penguin-sized objects (0.2-0.6m HAG)
- Uses Height-Above-Ground analysis with morphological filtering
- Outputs: GeoJSON, JSON summaries, QC plots, interactive web maps
- **Proven accuracy:** 802 detections on golden AOI, reproducible across runs

**Thermal Processing (Research Phase ⚠️)**
- Extracts 16-bit radiometric temperature data from DJI RJPEG format
- Orthorectifies thermal imagery using camera model
- Status: Infrastructure validated; ~9°C calibration offset unresolved

**Fusion Pipeline (Not Yet Implemented ❌)**
- Spatial join of LiDAR and thermal detections
- Classification: Both / LiDAR-only / Thermal-only

## Ground Truth Data

**Argentina 2025 Field Collection:** ~3,705 penguins across multiple sites

| Site | Penguins | Density |
|------|----------|---------|
| San Lorenzo Caves | 908 | 1,518/ha |
| San Lorenzo Plains | 453 | 464/ha |
| San Lorenzo Road | 359 | - |
| Caleta Small Island | 1,557 | 389/ha |
| Caleta Tiny Island | 321 | 459/ha |
| Box Counts | 107 | 15-28/ha |

GPS waypoints extracted to `data/processed/san_lorenzo_waypoints.csv`.

---

## System Requirements

**Hardware:**
- 16GB+ RAM (32GB recommended for large tiles)
- 50GB+ free disk space per survey site
- Multi-core CPU (LiDAR processing is parallelizable)

**Software:**
- Python 3.11+
- macOS, Linux, or Windows with WSL2
- For thermal: GDAL/rasterio (see `requirements-full.txt`)

---

## Installation

### Option 1: Standard Setup (LiDAR Only)

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install core dependencies
pip install -r requirements.txt

# Validate installation
pytest tests/test_golden_aoi.py -v
```

### Option 2: Full Setup (LiDAR + Thermal)

Thermal processing requires GDAL. See `requirements-full.txt` for detailed installation instructions.

**Quick path (conda):**
```bash
conda create -n penguins-thermal python=3.11
conda activate penguins-thermal
conda install -c conda-forge gdal rasterio pyproj
pip install -r requirements.txt
```

### Option 3: Automated Setup

```bash
# Run automated environment validation
./scripts/validate_environment.sh
```

---

## Usage Examples

### Process LiDAR Tile with Default Parameters

```bash
python scripts/run_lidar_hag.py \
    --data-root data/intake/lidar/ \
    --out results/lidar_detections.json \
    --cell-res 0.25 \
    --hag-min 0.2 \
    --hag-max 0.6 \
    --min-area-cells 2 \
    --max-area-cells 80 \
    --emit-geojson \
    --plots
```

### Process Multiple Tiles at Once

```bash
# Process all LAS/LAZ files in directory
python scripts/run_lidar_hag.py \
    --data-root field_data/site_A/lidar/ \
    --out results/site_A_detections.json \
    --plots \
    --emit-csv
```

### Quality Control Workflow

```bash
# 1. Run detection
make test-lidar

# 2. Check outputs
jq '.total_count' data/interim/lidar_test.json

# 3. View plots
open data/interim/lidar_hag_plots/

# 4. Load GeoJSON in QGIS for validation
qgis data/interim/lidar_hag_geojson/cloud3_detections.geojson
```

---

## Field Deployment Guide

### Pre-Deployment Checklist

**Critical (Must Complete):**
- [ ] Run `make validate` successfully
- [ ] Test on sample data from target site
- [ ] Confirm 500GB+ storage available
- [ ] Review `docs/FIELD_SOP.md` with flight crew
- [ ] Backup plan established (dual hard drives)

**Recommended:**
- [ ] Pre-process one tile to validate parameters
- [ ] Create site-specific parameter config
- [ ] Test QC workflow on field laptop

### Day-of-Capture Workflow

```bash
# 1. Copy data from drone to field laptop
cp -r /Volumes/DRONE_SD/LiDAR/* field_data/raw/

# 2. Quick-look processing (first tile only, 5-10 min)
python scripts/run_lidar_hag.py \
    --data-root field_data/raw/ \
    --out quicklook/results.json \
    --plots

# 3. Visual QC check
open quicklook/lidar_hag_plots/*.png

# 4. If QC passes, continue with full site capture
# 5. Full processing after all tiles collected
```

### Expected Data Volumes

| Site Size | LiDAR Data | Processing Time | Output Size |
|-----------|------------|-----------------|-------------|
| Small (10 ha) | 5-10 GB | 30-60 min | 100-200 MB |
| Medium (50 ha) | 25-50 GB | 2-4 hours | 500 MB-1 GB |
| Large (200 ha) | 100-200 GB | 8-16 hours | 2-5 GB |

---

## Project Structure

```
penguins-4.0/
├── README.md                  # This file
├── CLAUDE.md                  # AI assistant guidance
├── PRD.md                     # Product requirements
├── RUNBOOK.md                 # Command reference (tested only)
│
├── data/
│   ├── legacy_ro/             # Read-only legacy data (NEVER MODIFY)
│   ├── intake/                # Harvested inputs with checksums
│   ├── interim/               # Temporary processing outputs
│   └── processed/             # Final outputs (GeoJSON, CSV, etc.)
│
├── scripts/
│   ├── run_lidar_hag.py       # ⭐ Main LiDAR detection script
│   ├── run_thermal_ortho.py   # Thermal orthorectification
│   ├── create_detection_map.py # Interactive Folium web maps
│   ├── analyze_san_lorenzo_counts.py # Argentina data analysis
│   └── experiments/           # Prototype scripts
│
├── pipelines/
│   ├── lidar.py               # LiDAR processing library
│   ├── thermal.py             # Thermal processing library
│   ├── fusion.py              # Fusion spatial join (requires CRS x/y inputs)
│   └── utils/                 # Shared utilities
│
├── tests/
│   ├── test_golden_aoi.py     # 12 LiDAR reproducibility tests
│   └── test_thermal_radiometric.py # Thermal extraction tests
│
├── docs/
│   ├── planning/              # Integration plans, visualization strategy
│   ├── reports/               # Status reports, assessments
│   └── supplementary/         # Technical investigations
│
├── verification_images/       # Ground truth annotations
│
└── qc/panels/                 # QC visualizations and web maps
```

---

## Documentation

**For Users:**
- [RUNBOOK.md](RUNBOOK.md) - Only tested commands, no aspirational targets
- [CLAUDE.md](CLAUDE.md) - AI assistant guidance and project context

**For Developers:**
- [PRD.md](PRD.md) - Product requirements and acceptance criteria
- [docs/reports/STATUS.md](docs/reports/STATUS.md) - Current implementation state
- [docs/planning/VISUALIZATION_STRATEGY.md](docs/planning/VISUALIZATION_STRATEGY.md) - Visualization requirements

**Technical Reports:**
- [docs/supplementary/THERMAL_INVESTIGATION_FINAL.md](docs/supplementary/THERMAL_INVESTIGATION_FINAL.md) - Thermal signal analysis
- [docs/reports/GIS_ANALYST_ASSESSMENT_2025-12-09.md](docs/reports/GIS_ANALYST_ASSESSMENT_2025-12-09.md) - External review

---

## Testing

### Run All Tests

```bash
# Activate environment
source .venv/bin/activate

# Run golden AOI test suite (12 tests)
pytest tests/test_golden_aoi.py -v

# Or use Makefile
make test
```

### Run Specific Tests

```bash
# LiDAR pipeline only
make test-lidar

# Environment validation
make validate

# Thermal processing (requires GDAL)
pytest tests/test_thermal.py -v
```

### Expected Test Results

```
tests/test_golden_aoi.py::TestLiDARPipeline::test_golden_data_exists PASSED
tests/test_golden_aoi.py::TestLiDARPipeline::test_lidar_script_runs PASSED
tests/test_golden_aoi.py::TestLiDARPipeline::test_detection_count PASSED
tests/test_golden_aoi.py::TestLiDARPipeline::test_reproducibility PASSED
...
======================== 12 passed in 45.2s =========================
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'laspy'"

**Solution:** Environment not activated or dependencies not installed.

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### "Detection count differs from expected 802"

**Possible causes:**
1. Different data file (cloud3.las checksum mismatch)
2. Parameter changes not documented
3. Python/library version differences

**Solution:** Check provenance metadata:
```bash
cat data/interim/provenance_lidar.json
```

### "Permission denied: data/legacy_ro/"

**Expected behavior:** This directory is read-only by design.

**Solution:** Copy files to `data/intake/` instead:
```bash
cp data/legacy_ro/penguin-2.0/data/raw/LiDAR/cloud3.las data/intake/
```

### Thermal Processing Fails

**Error:** `ImportError: GDAL/rasterio not available`

**Solution:** Thermal requires GDAL. See `requirements-full.txt` for installation:
```bash
# Easiest: Use conda
conda install -c conda-forge gdal rasterio pyproj
```

---

## Performance Tips

### Speed Up Large Tile Processing

```bash
# Increase chunk size for faster streaming
python scripts/run_lidar_hag.py \
    --chunk-size 2000000 \
    --data-root large_tiles/

# Skip plot generation for batch processing
python scripts/run_lidar_hag.py \
    --data-root batch_tiles/ \
    --emit-csv  # CSV only, no plots
```

### Parallel Processing (Future)

```bash
# Process multiple tiles in parallel (not yet implemented)
# Coming in v0.2
```

---

## Getting Help

**For Issues:**
1. Check [STATUS.md](STATUS.md) for known limitations
2. Review [RUNBOOK.md](RUNBOOK.md) for tested commands
3. Check provenance files in output directories

**For Questions:**
- Technical: See PRD.md for design rationale
- Field operations: See docs/FIELD_SOP.md
- Thermal status: See docs/THERMAL_INVESTIGATION_FINAL.md

---

## Contributing

This pipeline follows DORA principles:
- Work in small batches
- Test on golden AOI before production
- Track provenance for all outputs
- Document honestly (working vs. aspirational)

See [AI_POLICY.md](AI_POLICY.md) for AI collaboration guidelines.

---

## Current Status (As of 2025-12-11)

**Production Ready:**
- ✅ LiDAR detection pipeline (802 detections on golden AOI, reproducible)
- ✅ Automated testing (12 tests passing)
- ✅ Interactive web maps (Folium)
- ✅ Provenance tracking

**In Progress:**
- 🔄 Argentina ground truth integration (~3,705 penguins, GPS waypoints extracted)
- 🔄 Visualization strategy (see `docs/planning/VISUALIZATION_STRATEGY.md`)

**Research Phase:**
- ⚠️ Thermal detection (~9°C calibration offset unresolved)
- ⚠️ Ground truth georeferencing (GPS → pixel coordinates)

**Not Implemented:**
- ❌ Fusion pipeline (spatial join of LiDAR + thermal)

See [CLAUDE.md](CLAUDE.md) for detailed project context and current priorities.

---

## License

Internal project - contact project owner for usage permissions.

---

## Version History

- **v0.2** (2025-12-11): Argentina field data integration
  - GPS waypoint extraction from field notes
  - Interactive Folium web maps for detection QC
  - Visualization strategy documentation
  - Updated ground truth: ~3,705 penguins across 9 sites

- **v0.1** (2025-10-14): Initial production release
  - LiDAR HAG detection validated (802 on golden AOI)
  - Golden AOI test suite (12 tests)
  - Thermal orthorectification infrastructure

---

**Questions?** See [CLAUDE.md](CLAUDE.md) for project context or check `docs/reports/STATUS.md` for current state.
