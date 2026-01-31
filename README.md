# Penguin Detection Pipeline

This pipeline estimates penguin presence from drone survey data, supporting population monitoring of Magellanic penguin colonies in Patagonia. It processes LiDAR point clouds to detect penguin-sized objects by height above ground, with optional thermal imagery fusion for validation. The system is designed for field researchers conducting aerial surveys with DJI drones equipped with LiDAR (L2, TrueView 515) and thermal (H30T, H20T) sensors.

Outputs are candidate detections (blob centroids), not confirmed individuals. Validation against ground truth requires AOI clipping and spot-check labeling, which is not yet automated.

## Quick Start

```bash
git clone https://github.com/rgdonohue/penguin-detection-pipeline.git
cd penguin-detection-pipeline
make env && source .venv/bin/activate
make validate

# Process LiDAR tiles
python scripts/run_lidar_hag.py \
    --data-root data/intake/lidar/ \
    --out results/detections.json \
    --emit-geojson --plots
```

Outputs appear in `results/`: JSON summaries, GeoJSON spatial layers, and PNG plots for visual QC.

## How It Works

The pipeline has three stages, currently at different levels of maturity.

**LiDAR detection** computes height above ground (HAG) for each point, rasterizes to a 0.25m grid, and extracts connected components within the 0.2-0.6m height band. Morphological filters remove objects outside the expected penguin size range (0.125-5 m²). This stage is deterministic and regression-tested against a golden AOI baseline.

**Thermal processing** extracts 16-bit radiometric temperatures from DJI RJPEG files and orthorectifies frames using camera pose metadata. The camera model applies DJI's NED gimbal conventions with proper Euler ZYX rotation. This stage works mechanically but has an unresolved calibration offset (~9°C) that prevents reliable biological detection.

**Fusion** performs a spatial join between LiDAR and thermal detections using a KD-tree nearest-neighbor search within a configurable radius. It labels each detection as LiDAR-only, thermal-only, or both. This stage requires both inputs to already have projected CRS coordinates; thermal pixel-to-CRS georeferencing is not yet implemented.

## Key Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run_lidar_hag.py` | LiDAR HAG detection with GeoJSON/CSV/GPKG output |
| `scripts/run_thermal_ortho.py` | Thermal orthorectification (requires GDAL) |
| `scripts/run_fusion_join.py` | Spatial join of LiDAR and thermal detections |
| `scripts/create_detection_map.py` | Interactive Folium web maps |

Core logic lives in `pipelines/`: `lidar.py`, `thermal.py`, `fusion.py`.

## Current Status

| Stage | Status | Notes |
|-------|--------|-------|
| LiDAR detection | Production | 802-candidate baseline on golden AOI; 59 tests passing |
| Thermal extraction | Research | 16-bit radiometric works; calibration offset unresolved |
| Fusion | Partial | Spatial join works; blocked on thermal georeferencing |
| Ground truth | In progress | Argentina 2025: ~3,705 field counts; GPS-to-pixel projection pending |

Detection counts are not yet validated against AOI-clipped ground truth. The 802 baseline is a regression guardrail, not an accuracy claim.

## Documentation

| Document | Purpose |
|----------|---------|
| [RUNBOOK.md](RUNBOOK.md) | Tested commands only |
| [docs/reports/STATUS.md](docs/reports/STATUS.md) | Current implementation state |
| [docs/supplementary/FIELD_SOP.md](docs/supplementary/FIELD_SOP.md) | Field deployment procedures |
| [PRD.md](PRD.md) | Product requirements |
| [CLAUDE.md](CLAUDE.md) | AI assistant context and project conventions |

## Requirements

Python 3.12 with dependencies in `requirements.txt`. LiDAR processing uses laspy, scipy, and scikit-image. Thermal processing additionally requires GDAL, rasterio, and pyproj; install via conda or see `requirements-full.txt`.

Hardware: 16GB RAM minimum (32GB recommended), 50GB free disk per survey site.

## Testing

```bash
make golden          # Fast guardrail (802 detections on cloud3.las)
make test-lidar      # Full LiDAR test suite
pytest tests/        # All 59 tests (some skip without GDAL/fixtures)
```

## Ground Truth

Argentina 2025 field collection covers ~3,705 penguins across San Lorenzo and Caleta sites, with densities ranging from 15 to 1,518 penguins per hectare. GPS waypoints are in `data/processed/san_lorenzo_waypoints.csv`. These are regional totals from field counts, not per-penguin pixel locations; georeferencing to image coordinates is pending.

## License

Internal project. Contact project owner for usage permissions.
