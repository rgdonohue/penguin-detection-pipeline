# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the Penguin Detection Pipeline project (v4.0) - a production-oriented system for detecting penguins using LiDAR and thermal imaging data. The pipeline implements a three-stage workflow:

1. **LiDAR HAG (Height Above Ground) Detection** - Identifies penguin candidates from LiDAR point clouds
2. **Thermal Orthorectification** - Projects thermal imagery onto DSM (Digital Surface Model)
3. **Data Fusion** - Combines LiDAR and thermal detections with statistical analysis

## Critical Development Principles

1. **Read-Only Legacy Data**: NEVER modify files in `data/legacy_ro/`. All legacy data must be harvested to `data/intake/` with checksums recorded in `manifests/harvest_manifest.csv`
2. **Deterministic Outputs**: All pipeline runs must produce identical results for the same inputs
3. **Provenance Tracking**: Every imported artifact requires SHA256 hash, size, and source path in the harvest manifest

## Project Structure

```
penguins-pipeline/
├── scripts/           # Entry point scripts for each pipeline stage
├── pipelines/         # Core pipeline implementations (library-style)
├── data/
│   ├── legacy_ro/     # Read-only mount to legacy folders (NEVER MODIFY)
│   ├── intake/        # Harvested copies from legacy with checksums
│   ├── interim/       # Temporary processing artifacts
│   └── processed/     # Final outputs (COG, VRT, GPKG, CSV)
├── manifests/         # Provenance tracking and QC reports
├── qc/panels/         # Quality control visualization outputs
└── tests/            # Golden AOI tests for reproducibility
```

## Development Commands

### Environment Setup
```bash
# Create/update virtual environment
make env
source .venv/bin/activate

# Or manually:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Main Pipeline Commands

```bash
# Full pipeline on golden AOI
make golden

# Individual stages
make harvest   # Import legacy artifacts with checksums
make lidar     # Run LiDAR HAG detection
make thermal   # Run thermal orthorectification (pilot subset)
make fusion    # Run fusion join with statistics
make qc        # Run golden AOI tests
```

### Stage-Specific Commands

#### LiDAR HAG Detection
```bash
python scripts/run_lidar_hag.py \
  --tiles data/intake/lidar/tile_A.laz \
  --cell-res 0.5 --hag-min 0.3 --hag-max 0.7 \
  --min-area-cells 2 --max-area-cells 30 \
  --emit-geojson --plots --rollup \
  --out-dir data/processed/lidar
```

#### Thermal Orthorectification (Pilot)
```bash
python scripts/run_thermal_ortho_pilot.py \
  --frames data/intake/thermal/subset/*.tif \
  --poses data/intake/thermal/poses.csv \
  --dsm data/intake/lidar/dsm.tif \
  --max-tiepoints 12 --rmse-threshold 2.0 \
  --out-dir data/processed/thermal
```

#### Fusion Join
```bash
python scripts/run_fusion_join.py \
  --candidates data/processed/lidar/candidates.gpkg \
  --thermal-vrt data/processed/thermal/thermal.vrt \
  --px-window 2 --out data/processed/fusion/fusion.csv \
  --qc-panel qc/panels/fusion_aoi.png
```

### Testing
```bash
# Run golden AOI reproducibility tests
python -m pytest -q tests/test_golden_aoi.py
```

## Key Technical Parameters

### LiDAR Processing
- Cell resolution: 0.5m
- HAG range: 0.3-0.7m (penguin height)
- Area constraints: 2-30 cells (~0.2-1.0 m²)
- Target density: ≥150-300 pts/m²

### Thermal Processing
- Radiometric mode: ON (16-bit)
- Emissivity: 0.98
- Overlap: 70% forward / 60% side
- RMSE threshold: ≤ 2 pixels
- Warm-up time: 5-10 minutes

**CRITICAL:** Full radiometric data IS encoded in thermal images, even when it appears lost. Use proper thermal image processing tools to extract it. Previous assumptions about missing radiometric data were incorrect.

## Quality Control Gates

1. **LiDAR**: Reproducible counts across runs; valid GPKG output
2. **Thermal**: Control/tie-point RMSE ≤ 2 px on subset
3. **Fusion**: Complete rows matching candidate count with valid labels (Both/LiDAROnly/ThermalOnly)

## Data Harvest Rules

### Allowed Artifact Types
- Code: `*.py`, `*.ipynb`
- Geospatial: `*.tif`, `*.vrt`, `*.gpkg`, `*.geojson`, `*.json`
- Documentation: `*.md`, flight logs
- Point clouds: `*.laz`, `*.las`

### Confidence Scoring
- `field`: Observed in real data run (highest priority)
- `vendor/peer`: External documentation
- `LLM`: AI-only claim (quarantine until replicated)

## Implementation Status

The project follows a two-track approach based on initial validation:
- **Track A**: Full pipeline if LiDAR HAG and DSM/pose data are reliable
- **Track B**: LiDAR-only baseline if thermal pose/DSM issues exist

## Dependencies

Core dependencies (pinned versions in `requirements.txt`):
- Python 3.11+
- laspy >= 2.4.0 (LiDAR processing)
- numpy >= 1.24.0, scipy >= 1.10.0 (numerical computing)
- scikit-image >= 0.20.0 (image processing)
- matplotlib >= 3.7.0 (visualization)
- pytest >= 7.3.0 (testing)

Additional dependencies for thermal/fusion (see `requirements-full.txt`):
- GDAL, rasterio, geopandas, shapely, fiona (geospatial operations)
- Note: GDAL can be tricky to install via pip; system install recommended

## Critical Files

- `PRD.md`: Product requirements and implementation plan
- `RUNBOOK.md`: Authoritative commands for each stage
- `manifests/harvest_manifest.csv`: Provenance tracking for all imported artifacts
- `manifests/qc_report.md`: Single source of QC truth

## Timeline Targets

- **48h Zoo Readout**: LiDAR counts + thermal RMSE + fusion labels
- **72h Argentina Readout**: First-pass analysis on full dataset