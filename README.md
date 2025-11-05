# Penguin Detection Pipeline

**Production-ready LiDAR-based penguin detection system for penguin colony field surveys.**

Version 0.1 | Last Updated: 2025-10-14

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
- Processes LiDAR point clouds to detect penguin-sized objects
- Uses Height-Above-Ground (HAG) analysis with morphological filtering
- Outputs: GeoJSON, JSON summaries, QC plots
- **Proven accuracy:** 879 detections on test data, reproducible across runs

**Thermal Processing (Research/Documentation 📊)**
- Orthorectifies thermal imagery using LiDAR DSM
- Extracts 16-bit radiometric temperature data
- Status: Infrastructure validated, detection challenges characterized (see docs/THERMAL_INVESTIGATION_FINAL.md)

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
├── PRD.md                     # Product requirements
├── RUNBOOK.md                 # Command reference (tested only)
├── STATUS.md                  # Honest project status
├── DEPLOYMENT_CHECKLIST.md    # Pre-deployment guide
│
├── data/
│   ├── legacy_ro/             # Read-only legacy data
│   ├── intake/                # Harvested inputs
│   ├── interim/               # Temporary processing outputs
│   └── processed/             # Final outputs
│
├── scripts/
│   ├── run_lidar_hag.py       # ⭐ Main LiDAR detection script
│   ├── run_thermal_ortho.py   # Thermal orthorectification
│   └── validate_environment.sh # Setup validation
│
├── pipelines/
│   ├── thermal.py             # Thermal processing library
│   └── utils/                 # Shared utilities
│
├── tests/
│   ├── test_golden_aoi.py     # Core integration tests
│   └── test_thermal.py        # Thermal processing tests
│
├── docs/
│   ├── FIELD_SOP.md           # Field procedures
│   ├── equipment.md           # Equipment specifications
│   └── THERMAL_*.md           # Thermal investigation reports
│
└── qc/
    └── panels/                # QC visualizations
```

---

## Documentation

**For Users:**
- [RUNBOOK.md](RUNBOOK.md) - Only tested commands, no aspirational targets
- [docs/FIELD_SOP.md](docs/FIELD_SOP.md) - Field procedures and capture settings

**For Developers:**
- [PRD.md](PRD.md) - Product requirements and acceptance criteria
- [STATUS.md](STATUS.md) - Current implementation state (honest assessment)
- [AI_POLICY.md](AI_POLICY.md) - AI collaboration guidelines

**Technical Reports:**
- [docs/THERMAL_INVESTIGATION_FINAL.md](docs/THERMAL_INVESTIGATION_FINAL.md) - Thermal signal analysis
- [validation_results.md](validation_results.md) - Validation test results

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

### "Detection count differs from expected 879"

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
cp data/legacy_ro/penguin-2.0/sample/cloud3.las data/intake/
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

## Current Status (As of 2025-10-14)

**Production Ready:**
- ✅ LiDAR detection pipeline (879 detections, reproducible)
- ✅ Automated testing (12 tests passing)
- ✅ Provenance tracking
- ✅ QC visualization
- ✅ Field deployment guide

**Investigation Complete:**
- 📊 Thermal characterization study (detection constraints quantified, infrastructure validated)
- 📚 Comprehensive documentation (field procedures, equipment specs, technical reports)

**Future Development:**
- 🔬 Thermal research opportunities with advanced instrumentation
- ⏳ Harvest automation (manual process works)

See [STATUS.md](STATUS.md) for detailed current state and [docs/FIELD_DEPLOYMENT_GUIDE.md](docs/FIELD_DEPLOYMENT_GUIDE.md) for deployment procedures.

---

## License

Internal project - contact project owner for usage permissions.

---

## Version History

- **v0.1** (2025-10-14): Initial production release
  - LiDAR HAG detection validated
  - Golden AOI test suite
  - Thermal orthorectification infrastructure

---

**Questions?** Review the documentation above or check STATUS.md for honest assessment of current capabilities.

