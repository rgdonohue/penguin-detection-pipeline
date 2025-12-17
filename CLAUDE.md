# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the Penguin Detection Pipeline project (v4.0) - a production-oriented system for detecting penguins using LiDAR and thermal imaging data from drone surveys in Argentina. The pipeline implements a three-stage workflow:

1. **LiDAR HAG (Height Above Ground) Detection** - Identifies penguin candidates from LiDAR point clouds
2. **Thermal Orthorectification** - Projects thermal imagery onto DSM (Digital Surface Model)
3. **Data Fusion** - Combines LiDAR and thermal detections with statistical analysis

### Ground Truth Benchmarks
- **Legacy (Punta Tombo):** ~1,533 penguins (established through manual ground truth)
- **Argentina 2025:** ~3,705 penguins across San Lorenzo and Caleta sites (field counts; GPS→pixel projection NOT yet implemented)

## Current Implementation Status (2025-12)

### What Works

| Stage | Status | Notes |
|-------|--------|-------|
| **LiDAR Detection** | ✅ Production-ready | 802 detections on golden AOI (guardrail); `scripts/run_lidar_hag.py` proven |
| **Thermal Extraction** | ⚠️ Research phase | 16-bit radiometric extraction working; ~9°C calibration offset unresolved |
| **Thermal Detection** | ⚠️ Research phase | F1 scores 0.02-0.30 depending on frame contrast; 60/137 ground truth validated |
| **Fusion** | ❌ Not implemented | `pipelines/fusion.py` is a stub; spatial join logic pending |
| **Ground Truth** | 🔄 In progress | Argentina field counts (~3,705 penguins); GPS→pixel projection needed |

### Active Development Priorities
1. **Argentina Data Integration** - Boundary/route waypoints (48) in `data/processed/san_lorenzo_waypoints.csv`; penguin counts (~3,705) in `san_lorenzo_analysis.json`; GPS→pixel projection pending
2. **Visualization Strategy** - See `docs/planning/VISUALIZATION_STRATEGY.md` for requirements
3. **Thermal Calibration** - Resolving the ~9°C offset issue
4. **Fusion Pipeline** - Implementing spatial join between LiDAR and thermal detections

## Critical Development Principles

1. **Read-Only Legacy Data**: NEVER modify files in `data/legacy_ro/`. All legacy data must be harvested to `data/intake/` with checksums recorded in `manifests/harvest_manifest.csv`
2. **Deterministic Outputs**: All pipeline runs must produce identical results for the same inputs
3. **Provenance Tracking**: Every imported artifact requires SHA256 hash, size, and source path in the harvest manifest
4. **Single Source of Truth**:
   - Tasks: `notes/pipeline_todo.md`
   - Current state: `docs/reports/STATUS.md`
   - Commands: `RUNBOOK.md`

## Project Structure

```
penguins-4.0/
├── scripts/               # Entry point scripts for each pipeline stage
│   ├── run_lidar_hag.py   # ✅ PROVEN - LiDAR detection (802 candidates)
│   ├── run_thermal_ortho.py  # ⚠️ Orthorectification (needs validation)
│   ├── create_detection_map.py  # Folium web map from GeoJSON
│   ├── analyze_san_lorenzo_counts.py  # Argentina ground truth analysis
│   └── experiments/       # Prototype/experimental scripts
├── pipelines/             # Core pipeline implementations (library-style)
│   ├── lidar.py           # LidarParams dataclass + subprocess wrapper
│   ├── thermal.py         # Camera model, pose extraction, orthorectification
│   ├── fusion.py          # Spatial join (requires CRS x/y inputs)
│   └── utils/provenance.py  # Provenance tracking utilities
├── data/
│   ├── legacy_ro/         # Read-only mount to 4 legacy projects (NEVER MODIFY)
│   │   ├── penguin-2.0/   # Working LiDAR scripts + data
│   │   ├── penguin-3.0/   # Most recent project
│   │   ├── thermal-lidar-fusion/
│   │   └── penguin-thermal-og/
│   ├── intake/            # Harvested copies with checksums
│   │   └── h30t/          # H30T thermal test flights (symlinked)
│   ├── interim/           # Temporary processing artifacts
│   └── processed/         # Final outputs (COG, VRT, GPKG, CSV)
├── docs/
│   ├── planning/          # Argentina integration plans, visualization strategy
│   ├── reports/           # STATUS.md, session reports, assessments
│   └── supplementary/     # Thermal investigation, field SOPs
├── manifests/             # Provenance tracking and QC reports
│   └── harvest_manifest.csv
├── verification_images/   # Ground truth annotations (60/137 complete)
├── tests/
│   ├── test_golden_aoi.py # 12 LiDAR reproducibility tests
│   └── test_thermal_radiometric.py  # 5 thermal extraction tests
└── qc/panels/             # Quality control visualization outputs
```

## Development Commands

### Environment Setup
```bash
# Automated validation (recommended)
./scripts/validate_environment.sh

# Manual setup
make env && source .venv/bin/activate

# Verify installation
python3 -c "import laspy, scipy, skimage, pytest; print('✓ Core dependencies OK')"
```

### Working Commands (Tested)

```bash
# LiDAR detection on golden AOI (PROVEN - 802 detections)
make test-lidar
# Or: pytest tests/test_golden_aoi.py -v

# Run golden AOI tests (12 tests)
pytest tests/test_golden_aoi.py -v

# Thermal smoke test (requires GDAL)
make thermal
```

### Commands Not Yet Working
```bash
# These targets exist but scripts are incomplete:
# make harvest   # No scripts/harvest_legacy.py
# make fusion    # Needs a CLI wrapper for pipelines/fusion.py
# make golden    # Golden harness not yet ported to pipelines/golden.py
```

## Key Technical Parameters

### LiDAR Processing (Tuned for Magellanic Penguins)
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Cell resolution | 0.25m | Higher resolution for penguin-sized objects |
| HAG min | 0.2m | Minimum penguin height |
| HAG max | 0.6m | Maximum penguin height |
| Min area cells | 2 | ~0.125 m² minimum |
| Max area cells | 80 | ~5 m² maximum (excludes rocks/vegetation) |
| Connectivity | 2 | 8-connectivity for blob detection |

### Thermal Processing (H30T / H20T Sensors)
| Parameter | Value | Notes |
|-----------|-------|-------|
| Radiometric mode | ON (16-bit) | Full thermal data encoded in RJPEG |
| Emissivity | 0.98 | Penguin feather emissivity |
| Overlap | 70%/60% | Forward/side overlap for mosaic |
| RMSE threshold | ≤ 2 pixels | Orthorectification quality gate |
| Transfer function | (DN >> 2) * 0.0625 - 273.15 | DJI radiometric conversion |

**CRITICAL:** Full radiometric data IS encoded in thermal images, even when it appears lost. Use `pipelines/thermal.py:extract_thermal_data()` to properly decode 16-bit thermal values.

### Coordinate Reference System
- **EPSG:32720** - UTM Zone 20S (Argentina)
- All outputs should maintain this CRS for consistency

## Quality Control Gates

| Gate | Criteria | Status |
|------|----------|--------|
| LiDAR | Reproducible 802 ± tolerance on cloud3.las | ✅ Passing |
| Thermal Ortho | RMSE ≤ 2 px on control points | ⚠️ Needs validation |
| Thermal Detection | Total count within 20% of 1533 | ❌ Not yet achieved |
| Fusion | Complete rows with Both/LiDAROnly/ThermalOnly labels | ❌ Not implemented |

## Argentina Field Data (2025)

### Available Ground Truth (~3,705 penguins)
| Site | Count | Area | Density | Sensors |
|------|-------|------|---------|---------|
| San Lorenzo Caves | 908 | 0.60 ha | 1,518/ha | TrueView 515, H30T |
| San Lorenzo Plains | 453 | 0.98 ha | 464/ha | TrueView 515, H30T |
| San Lorenzo Road | 359 | - | - | TrueView 515, H30T |
| San Lorenzo Box Counts | 87 | 4.95 ha | 15-28/ha | H30T |
| Caleta Small Island | 1,557 | 4.0 ha | 389/ha | L2, H30T |
| Caleta Tiny Island | 321 | 0.7 ha | 459/ha | L2, H30T |
| Caleta Box Counts | 20 | - | - | H30T |

**Key observation:** Density varies 100x across sites (15 to 1,518 penguins/ha).

### Data Files
- `data/processed/san_lorenzo_waypoints.csv` - 48 boundary/route waypoints (NOT penguin locations)
- `data/processed/san_lorenzo_analysis.json` - Penguin counts (~3,705) and density analysis by site
- `docs/GPS Ground Truthing Notes 2025 - RD.pdf` - Original field notes

**IMPORTANT:** The ~3,705 figure is total penguin COUNT from field observations, NOT georeferenced pixel locations. The `san_lorenzo_waypoints.csv` contains survey boundary points, not individual penguin positions.

### Integration Status
See `docs/planning/ARGENTINA_DATA_INTEGRATION_SUMMARY.md` for full georeferencing workflow.

- [x] Extract site boundary waypoints from PDF → structured format (48 waypoints)
- [x] Extract penguin counts by site → JSON format (~3,705 total)
- [ ] Implement GPS→pixel projection using camera model in `thermal.py`
- [ ] Generate per-image ground truth CSVs
- [ ] Validate accuracy (<5 pixel error for RTK GPS)

## Dependencies

### Core (LiDAR stage only)
```
laspy>=2.6.1      # LiDAR I/O
numpy>=2.0.2
scipy>=1.13.1
scikit-image>=0.24.0
matplotlib>=3.9.4
pytest>=8.4.2
```

### Full (Thermal/Fusion) - see `requirements-full.txt`
```
# Requires GDAL - install via conda or system package
conda install -c conda-forge gdal rasterio pyproj geopandas
```

## Critical Files Reference

| File | Purpose |
|------|---------|
| `PRD.md` | Product requirements and success criteria |
| `RUNBOOK.md` | Authoritative tested commands |
| `docs/reports/STATUS.md` | Current implementation state |
| `docs/planning/VISUALIZATION_STRATEGY.md` | Visualization requirements and approach |
| `notes/pipeline_todo.md` | Single task tracker |
| `manifests/harvest_manifest.csv` | Provenance for imported artifacts |
| `verification_images/` | Ground truth CSVs (frame_0353-0359_locations.csv) |
| `qc/panels/` | QC visualizations including detection maps |

## MCP Tool Integration Recommendations

For enhanced GIS/remote sensing capabilities, consider integrating these MCP servers:

### Recommended MCP Servers

1. **GDAL-MCP** ([Wayfinder-Foundry/gdal-mcp](https://github.com/Wayfinder-Foundry/gdal-mcp))
   - Rasterio/GeoPandas/PyProj operations via Claude
   - Raster metadata, CRS transforms, format conversion
   - Vector clipping, buffer operations
   - Install: `uvx --from gdal-mcp gdal --transport stdio`

2. **GIS-MCP** ([mahdin75/gis-mcp](https://github.com/mahdin75/gis-mcp))
   - 89 geospatial functions (Shapely, GeoPandas, PySAL)
   - Geometric operations, coordinate transforms
   - Spatial statistics and analysis

3. **QGIS-MCP** ([jjsantos01/qgis_mcp](https://github.com/jjsantos01/qgis_mcp))
   - Control QGIS Desktop from Claude
   - Visualization and cartography
   - PyQGIS code execution

### Configuration Example
```json
// ~/.claude/mcp_servers.json
{
  "mcpServers": {
    "gdal-mcp": {
      "command": "uvx",
      "args": ["--from", "gdal-mcp", "gdal", "--transport", "stdio"],
      "env": {
        "GDAL_MCP_WORKSPACES": "/Users/richard/Documents/projects/penguins-4.0/data"
      }
    }
  }
}
```

## AI Collaboration Guidelines

### Allowed Actions
- Propose harvest regex rules; summarize field findings
- Draft documentation; suggest parameter sweeps
- Generate plots from pipeline outputs
- Implement scripts following existing patterns

### Forbidden Actions
- Modifying files in `data/legacy_ro/`
- Silent parameter changes outside `RUNBOOK.md`
- Non-deterministic transforms on geodata
- Adding features beyond what is explicitly requested

### When Uncertain
1. Check `notes/pipeline_todo.md` for current priorities
2. Verify commands in `RUNBOOK.md` before suggesting new ones
3. Reference `docs/reports/STATUS.md` for implementation state
4. Ask clarifying questions rather than assuming

## Glossary

| Term | Definition |
|------|------------|
| HAG | Height Above Ground (DEM-normalized point heights) |
| DSM | Digital Surface Model (terrain + objects) |
| DTM | Digital Terrain Model (bare earth) |
| COG | Cloud-Optimized GeoTIFF |
| VRT | GDAL Virtual Raster Mosaic |
| RMSE | Root Mean Square Error (pixels) |
| RJPEG | Radiometric JPEG (DJI thermal format with embedded 16-bit data) |
| LRF | Laser Range Finder (for boresight calibration) |
| RTK | Real-Time Kinematic (cm-accuracy GPS) |
| PPK | Post-Processed Kinematic |

---

**Last Updated:** 2025-12-11
**Principle:** One blessed path, hard gates, perfect provenance.
