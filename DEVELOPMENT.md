# Development Guide

## Project Structure

```
penguins-4.0/
├── scripts/               # Command-line tools for each pipeline stage
├── pipelines/             # Core detection and analysis modules
├── tests/                 # Automated regression and validation tests
├── data/
│   ├── 2025/              # Argentina field survey data (LiDAR + thermal)
│   ├── interim/           # Intermediate processing artifacts
│   └── processed/         # Final outputs (GeoJSON, CSV, JSON)
├── docs/                  # Planning, status reports, research notes
├── qc/panels/             # Quality control maps and visualizations
├── manifests/             # Data provenance tracking (SHA256 checksums)
└── verification_images/   # Manual ground truth annotations
```

## Setup

Requires Python 3.12. LiDAR processing uses laspy, scipy, and scikit-image. Thermal processing additionally requires GDAL, rasterio, and pyproj.

```bash
make env && source .venv/bin/activate   # Create environment
make golden                             # Run LiDAR regression test
pytest tests/                           # Run full test suite
```

Hardware: 16 GB RAM minimum (32 GB recommended for large LiDAR files), 50 GB free disk per survey site.

## Reproducibility

The pipeline produces deterministic results — the same input always gives the same output:

- **Golden AOI baseline:** Running `make golden` produces exactly 776 detections on the test tile, verified by SHA256 hash
- **Test suite:** 108 automated tests including regression baselines
- **Provenance tracking:** Outputs include metadata recording parameters, CRS, and input files
- All algorithms are deterministic; there are no stochastic components

## Outputs

The pipeline produces several output types, stored in `data/processed/` and `qc/panels/`:

- **Detection summaries** (JSON) — Per-site candidate counts with coordinates, heights, and areas
- **Spatial layers** (GeoJSON, GeoPackage) — Candidate locations and AOI polygons in UTM Zone 20S (EPSG:32720) for use in GIS software
- **Interactive maps** (HTML) — Folium web maps with candidate markers and AOI overlays, viewable in any browser
- **Static maps** (PNG) — Detection overlay maps with processing metadata
- **QC reports** — Validation summaries comparing candidate counts to field counts by site

## Key References

| Document | Purpose |
|----------|---------|
| [RUNBOOK.md](RUNBOOK.md) | Tested pipeline commands |
| [docs/reports/STATUS.md](docs/reports/STATUS.md) | Current implementation state |
| [docs/reports/LIDAR_METHODOLOGY.md](docs/reports/LIDAR_METHODOLOGY.md) | Algorithm documentation |
| [docs/reports/LIDAR_VALIDATION.md](docs/reports/LIDAR_VALIDATION.md) | AOI-clipped validation results |
| [docs/reports/FEATURE_ANALYSIS.md](docs/reports/FEATURE_ANALYSIS.md) | Per-detection feature analysis and parameter sensitivity |
| [docs/reports/THERMAL_LIDAR_CROSSREF.md](docs/reports/THERMAL_LIDAR_CROSSREF.md) | Thermal georeferencing, LiDAR cross-reference, thermal discrimination POC |
| [docs/process/LABELING_PROTOCOL.md](docs/process/LABELING_PROTOCOL.md) | Manual labeling protocol for precision estimation |
