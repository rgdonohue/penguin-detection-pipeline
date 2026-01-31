# Penguin Detection Pipeline

Automated detection of Magellanic penguins from drone survey data, developed in collaboration with the [Conservation Technology Alliance](https://www.conservationta.org/). The pipeline processes LiDAR point clouds and thermal imagery collected by drone to identify and count penguins across breeding colonies in Patagonia, Argentina.

## Project Goal

Manual counting of penguin colonies is labor-intensive and limited in scale. This project develops a reproducible, sensor-fusion approach to estimate penguin populations from aerial surveys. The pipeline identifies penguin-sized objects in LiDAR height data, extracts thermal signatures from infrared imagery, and combines both sources for validated counts. The aim is a field-deployable tool that conservation teams can run on standard survey data to produce population estimates with documented precision.

## Study Sites (Argentina 2025)

Field data was collected across San Lorenzo and Caleta sites in Patagonia during 2025, covering approximately 3,705 penguins with densities ranging from 15 to 1,518 penguins per hectare.

| Site | Field Count | Area (ha) | Density (/ha) | Sensors |
|------|------------|-----------|---------------|---------|
| San Lorenzo Caves | 908 | 0.60 | 1,518 | TrueView 515, H30T |
| San Lorenzo Plains | 453 | 0.98 | 464 | TrueView 515, H30T |
| San Lorenzo Road | 359 | — | — | TrueView 515, H30T |
| San Lorenzo Box Counts | 87 | 4.95 | 15–28 | H30T |
| Caleta Small Island | 1,557 | 4.0 | 389 | DJI L2, H30T |
| Caleta Tiny Island | 321 | 0.7 | 459 | DJI L2, H30T |
| Caleta Box Counts | 20 | — | — | H30T |

Surveys used DJI drones with LiDAR sensors (DJI L2, TrueView 515) and thermal cameras (DJI H30T). Field counts were recorded by ground teams walking transects and counting penguins within marked boundaries.

## How It Works

The pipeline has three stages.

**LiDAR Detection.** Point clouds are normalized to height above ground (HAG), rasterized to a 0.25 m grid, and filtered to the 0.2–0.6 m height band (the expected standing height of Magellanic penguins). Connected-component analysis extracts blob candidates, and morphological filters remove objects outside the 0.125–5.0 m² size range. This stage is deterministic — the same input always produces the same output — and is regression-tested against a baseline dataset.

**Thermal Processing.** Full 16-bit radiometric temperatures are extracted from DJI thermal JPEG files. Frames are orthorectified (projected onto terrain) using camera pose metadata and a digital surface model. This stage is functional but has an unresolved temperature calibration offset that prevents reliable biological detection thresholds.

**Fusion.** LiDAR and thermal detections are spatially joined using nearest-neighbor matching. Each detection is labeled as LiDAR-only, thermal-only, or confirmed by both sensors. This stage is partially implemented; full integration depends on resolving thermal georeferencing.

## Results So Far

LiDAR detection has been validated against field counts at four sites. Results are expressed as candidate-to-field-count ratios — the proportion of field-counted penguins that the pipeline produces candidate detections for within a defined area of interest (AOI).

| Site | Field Count | LiDAR Candidates | Ratio | AOI Source |
|------|------------|-------------------|-------|------------|
| Caleta Tiny Island | 321 | 315 | 0.98 | LiDAR footprint |
| Caleta Small Island | 1,557 | 1,255 | 0.81 | LiDAR footprint |
| San Lorenzo Caves | 908 | 263 | 0.29 | GPS waypoints (approximate) |
| San Lorenzo Plains | 453 | 86 | 0.19 | GPS waypoints (approximate) |

**Interpreting these numbers:** The Caleta island results are the most reliable because the AOI boundaries come directly from LiDAR coverage of isolated islands with natural coastline boundaries. The San Lorenzo ratios are lower primarily because the AOI polygons were approximated from GPS waypoint notes and may not match the actual areas that field teams counted. Additionally, many San Lorenzo penguins nest in caves and burrows where they are not visible to LiDAR.

These are candidate counts, not confirmed penguin identifications. Precision estimation (what fraction of candidates are actually penguins) requires manual spot-checking, which is underway.

## Current Status

| Component | Status | Summary |
|-----------|--------|---------|
| LiDAR detection | Production | Deterministic pipeline with regression tests; validated on Argentina data |
| AOI evaluation | Production | Tools for clipping detections to survey boundaries and computing site-level counts |
| Thermal extraction | Research | Radiometric data extraction works; temperature calibration unresolved |
| Thermal-LiDAR fusion | Partial | Spatial join implemented; blocked on thermal georeferencing |
| Ground truth | In progress | ~3,705 field counts available; AOI boundary confirmation needed from field team |

### What's Needed Next

1. **AOI boundary confirmation** — The field team needs to provide or confirm digitized polygon boundaries for San Lorenzo sites. Current AOIs are approximated from GPS waypoint notes and show area mismatches with reported survey areas.
2. **Precision estimation** — Manual labeling of 50–100 candidate detections within a validated AOI to quantify what fraction are true penguins vs. rocks or vegetation.
3. **Thermal calibration** — Resolving the temperature offset to enable thermal-based detection and sensor fusion.
4. **Box count validation** — Running LiDAR detection on the smaller box count areas (San Lorenzo: 32 and 55 penguins; Caleta: 8 and 12 penguins) where ground truth boundaries are more precise.

## Outputs

The pipeline produces several output types, stored in `data/processed/` and `qc/panels/`:

- **Detection summaries** (JSON) — Per-site candidate counts with coordinates, heights, and areas
- **Spatial layers** (GeoJSON, GeoPackage) — Candidate locations and AOI polygons in UTM Zone 20S (EPSG:32720) for use in GIS software
- **Interactive maps** (HTML) — Folium web maps with candidate markers and AOI overlays, viewable in any browser
- **Static maps** (PNG) — Publication-ready detection maps with processing metadata and provenance embedded
- **QC reports** — Validation summaries comparing candidate counts to field counts by site

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

## Technical Setup

Requires Python 3.12. LiDAR processing uses laspy, scipy, and scikit-image. Thermal processing additionally requires GDAL, rasterio, and pyproj.

```bash
make env && source .venv/bin/activate   # Create environment
make golden                             # Run LiDAR regression test
pytest tests/                           # Run full test suite
```

Hardware: 16 GB RAM minimum (32 GB recommended for large LiDAR files), 50 GB free disk per survey site.

## Key References

| Document | Purpose |
|----------|---------|
| [RUNBOOK.md](RUNBOOK.md) | Tested pipeline commands |
| [docs/reports/STATUS.md](docs/reports/STATUS.md) | Detailed implementation state |
| [docs/reports/LIDAR_VALIDATION.md](docs/reports/LIDAR_VALIDATION.md) | AOI-clipped validation results |
| [docs/supplementary/FIELD_SOP.md](docs/supplementary/FIELD_SOP.md) | Field deployment procedures |

## License

Internal project. Contact the project owner for usage permissions.
