# Penguin Detection Pipeline

Automated detection of Magellanic penguins from drone survey data, developed in collaboration with the [Conservation Technology Alliance](https://www.conservationta.org/). The pipeline processes LiDAR point clouds and thermal imagery collected by drone to identify and count penguins across breeding colonies in Patagonia, Argentina.

## Current Focus (Feb 2026)

**LiDAR detection is the active workstream.** Thermal processing and LiDAR–thermal fusion are paused while we resolve AOI boundary definitions and complete LiDAR validation for the 2025 Argentina surveys.

## Project Goal

Manual counting of penguin colonies is labor-intensive and limited in scale. This project develops a reproducible method to detect penguin candidates from aerial LiDAR surveys. The pipeline identifies penguin-sized above-ground objects in LiDAR height data and compares candidate counts to field observations. Thermal detection and sensor fusion were explored but are not yet operational (see [Current Status](#current-status)).

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

The pipeline was designed as a three-stage workflow. As of Feb 2026, only the LiDAR stage is tested and in active use.

**LiDAR Detection.** Point clouds are normalized to height above ground (HAG), rasterized to a 0.25 m grid, and filtered to the 0.2–0.6 m height band (the expected standing height of Magellanic penguins). Connected-component analysis extracts blob candidates, and morphological filters remove objects outside the 0.125–5.0 m² size range. This stage is deterministic — the same input always produces the same output — and is regression-tested against a baseline dataset.

**Thermal Processing (paused).** Full 16-bit radiometric temperatures can be extracted from DJI thermal JPEG files, and single-frame orthorectification utilities exist. However, temperature calibration and field-valid georeferencing are not yet sufficient for operational counting; treat this as research-only.

**Fusion (paused).** A spatial join exists for combining LiDAR and thermal detections, but it requires thermal data to be georeferenced into the same coordinate system as LiDAR, which is not yet done.

## Results So Far

LiDAR detection has been compared against field counts at four sites. Results are expressed as candidate-to-field-count ratios — the number of pipeline candidates divided by the field count within a defined area of interest (AOI). These ratios are not precision or recall in the statistical sense; a precision audit (manual labeling of candidate samples) has not yet been completed.

| Site | Field Count | LiDAR Candidates | Ratio | AOI Source | AOI Quality |
|------|------------|-------------------|-------|------------|-------------|
| Caleta Tiny Island | 321 | 315 | 0.98 | LiDAR footprint (Otsu threshold) | Good — island boundary; AOI area 0.53 ha vs reported 0.7 ha |
| Caleta Small Island | 1,557 | 1,255 | 0.81 | LiDAR footprint | Moderate — some shoreline edge effects |
| San Lorenzo Caves | 908 | 263 | 0.29 | GPS waypoints (convex hull) | Uncertain — see below |
| San Lorenzo Plains | 453 | 86 | 0.19 | GPS waypoints (perimeter winding) | Uncertain — see below |

**Interpreting these numbers:**

The **Caleta island results (0.81–0.98)** are the most reliable comparisons because the AOI boundaries are derived from LiDAR coverage of physically isolated islands, though both have caveats: Tiny Island's AOI area (0.53 ha) is smaller than the reported 0.7 ha due to Otsu thresholding of sparse water returns, and Small Island has some shoreline edge effects that may affect the boundary.

The **San Lorenzo results (0.19–0.29)** are lower for two documented reasons:

1. **Burrow occlusion:** Analysis of 84 thermal-labeled penguins at the legacy site found 36 (43%) positioned deep in burrows where they have no above-ground signature. If this proportion holds at other cave sites, it would set a theoretical detection ceiling of approximately 57% for overhead LiDAR. This is an estimate from a small sample, not a confirmed site-wide figure.

2. **AOI boundary uncertainty:** San Lorenzo polygons were constructed from sparse GPS waypoints. The Plains polygon area (0.73 ha) is smaller than reported (0.98 ha), and several boundary coordinates require field team clarification.

These are candidate counts, not confirmed penguin identifications. Precision estimation (what fraction of candidates are actually penguins) requires manual spot-checking of detection samples.

## Feature Analysis

Beyond geometric filtering, per-detection spectral features were extracted to assess detection quality and provide evidence for the question "how do we know these are penguins?"

**Key finding:** Inside-AOI detections have a remarkably consistent spectral signature — 86% of Caleta Tiny Island detections form a tight core with consistent NIR intensity, warm-toned RGB, and near-zero greenness. This homogeneity is not explained by the pipeline's geometric filters (morphological features show no inside/outside difference) and provides supporting evidence that detections represent a single object class. Confirmation that the core consists of true penguins requires manual labeling, which is in progress.

| Feature | Discriminative Power | Cross-site / Cross-sensor |
|---------|---------------------|--------------------------|
| Intensity (NIR) | Strong within-site | Poor — site-specific and sensor-locked |
| Greenness (G−R)/(G+R) | Moderate | Good — consistent near-zero across sites and sensors |
| Color warmth (R−B) | Moderate | Unknown |
| Multi-return fraction | Weak | Median 0%, mean <1% on TrueView 515; 18% of detections >1% |

Parameter sensitivity analysis shows **hag_max is the dominant parameter** — detection counts vary 3–4× more with the upper height bound than with any other parameter at Caleta (DJI L2). At San Lorenzo (TrueView 515), hag_min also shows moderate sensitivity (36% variation). Full analysis in `docs/reports/FEATURE_ANALYSIS.md`.

## Current Status

| Component | Status | Summary |
|-----------|--------|---------|
| LiDAR detection | Working | Deterministic pipeline with regression tests; compared against Argentina field data |
| AOI evaluation | Working | Tools for clipping detections to survey boundaries and computing site-level counts |
| Feature analysis | Complete | RGB, intensity, greenness for 3 sites across 2 sensors; parameter sweeps |
| Precision estimation | In progress | 80-sample label bundles generated for 2 sites; manual labeling underway |
| Thermal extraction | Paused | 16-bit radiometric extraction works; temperature calibration unresolved |
| Thermal-LiDAR fusion | Paused | Spatial join exists; blocked on thermal georeferencing |
| Ground truth | Incomplete | ~3,705 field counts available; AOI boundary confirmation needed from field team |

### What's Needed Next

1. **Precision estimation** — Manual labeling of 80-sample bundles (Caleta Tiny and Small Islands) is in progress. Each sample has RGB+HAG dual-panel crop images for visual classification. Protocol: `docs/process/LABELING_PROTOCOL.md`. Precision estimation via `scripts/estimate_precision.py` will follow.
2. **AOI boundary confirmation** — The field team needs to provide or confirm digitized polygon boundaries for San Lorenzo sites. A detailed clarification request is available in `notes/client_aoi_clarifications.md`.
3. **Box count validation** — Running LiDAR detection on the smaller box count areas (San Lorenzo: 32 and 55 penguins; Caleta: 8 and 12 penguins) where ground truth boundaries are more precise.

### Future Work (Deprioritized)

- **Thermal calibration** — A ~9°C calibration offset remains unresolved. The extraction infrastructure is complete, but thermal detection is research-quality only.
- **Sensor fusion** — Combining LiDAR and thermal detections. Blocked on thermal calibration.

## Known Limitations

| Limitation | Impact | Status |
|------------|--------|--------|
| Burrow occlusion | Estimated ~43% of penguins invisible to overhead LiDAR at cave sites (based on 84 thermal-labeled samples at one site) | Documented; not solvable by parameter tuning |
| Candidate ≠ individual | Detections are blob centroids, not confirmed penguins; false positives from rocks, vegetation, burrow rims | Precision audit defined but not yet run |
| Adjacent penguin merging | Close-standing penguins may produce a single detection at 0.25 m resolution | Watershed splitting helps in some cases |
| Sensor-specific tuning | DJI L2 and TrueView 515 require different parameters for best results | Per-sensor parameters documented |
| AOI boundary sensitivity | Site-level counts change significantly depending on clipping polygon | Awaiting field team clarification on San Lorenzo boundaries |

## Outputs

The pipeline produces several output types, stored in `data/processed/` and `qc/panels/`:

- **Detection summaries** (JSON) — Per-site candidate counts with coordinates, heights, and areas
- **Spatial layers** (GeoJSON, GeoPackage) — Candidate locations and AOI polygons in UTM Zone 20S (EPSG:32720) for use in GIS software
- **Interactive maps** (HTML) — Folium web maps with candidate markers and AOI overlays, viewable in any browser
- **Static maps** (PNG) — Detection overlay maps with processing metadata
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

## Reproducibility

The pipeline produces deterministic results — the same input always gives the same output:

- **Golden AOI baseline:** Running `make golden` produces exactly 802 detections on the test tile, verified by SHA256 hash
- **Test suite:** 108 automated tests including regression baselines
- **Provenance tracking:** Outputs include metadata recording parameters, CRS, and input files
- All algorithms are deterministic; there are no stochastic components

## Key References

| Document | Purpose |
|----------|---------|
| [RUNBOOK.md](RUNBOOK.md) | Tested pipeline commands |
| [docs/reports/STATUS.md](docs/reports/STATUS.md) | Current implementation state |
| [docs/reports/LIDAR_METHODOLOGY.md](docs/reports/LIDAR_METHODOLOGY.md) | Algorithm documentation |
| [docs/reports/LIDAR_VALIDATION.md](docs/reports/LIDAR_VALIDATION.md) | AOI-clipped validation results |
| [docs/reports/FEATURE_ANALYSIS.md](docs/reports/FEATURE_ANALYSIS.md) | Per-detection feature analysis and parameter sensitivity |
| [docs/process/LABELING_PROTOCOL.md](docs/process/LABELING_PROTOCOL.md) | Manual labeling protocol for precision estimation |

## License

Internal project. Contact the project owner for usage permissions.
