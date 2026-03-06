# Penguin Detection Pipeline

Automated detection of Magellanic penguins from drone LiDAR surveys, developed with the [Conservation Technology Alliance](https://www.conservationta.org/). See the [latest status report](docs/reports/CLIENT_STATUS_REPORT_2026-02-02.md) for detection results.

## How It Works

Point clouds are normalized to height above ground (HAG), rasterized to a configurable grid, and filtered to a height band tuned for standing Magellanic penguins. Connected-component analysis extracts blob candidates, and morphological filters remove objects outside the target size range. Parameters are tuned per site and sensor. All outputs use EPSG:32720 (UTM Zone 20S). The pipeline is deterministic and regression-tested.

| Parameter | DJI L2 (Caleta) | TrueView 515 (San Lorenzo) |
|-----------|-----------------|----------------------------|
| Cell resolution | 0.25 m | 0.30 m |
| HAG band | 0.28–0.48 m | 0.28–0.48 m |
| Min area | 3 cells (0.19 m²) | 3 cells (0.27 m²) |
| Max area | 60 cells (3.75 m²) | 50 cells (4.5 m²) |
| Connectivity | 8-connected | 8-connected |

The legacy Punta Tombo benchmark uses different defaults (0.25 m cell, 0.2–0.6 m HAG, 2–80 cells). For the full parameter reference and per-site validation, see [LIDAR_METHODOLOGY.md](docs/reports/LIDAR_METHODOLOGY.md).

## Quick Start

```bash
# Setup
make env && source .venv/bin/activate

# Run LiDAR detection (proven — 776 detections on golden AOI)
make test-lidar

# Run regression tests
make golden
.venv/bin/python -m pytest -q
```

See [RUNBOOK.md](RUNBOOK.md) for full command reference and [DEVELOPMENT.md](DEVELOPMENT.md) for project structure and setup details.

## Study Sites

Field data from San Lorenzo and Caleta sites in Patagonia (Argentina 2025).

| Site | Type | Sensors |
|------|------|---------|
| San Lorenzo Caves | Mainland, burrow-heavy | TrueView 515, H30T |
| San Lorenzo Plains | Mainland, mixed terrain | TrueView 515, H30T |
| San Lorenzo Road | Mainland, mixed | TrueView 515, H30T |
| Caleta Small Island | Open island colony | DJI L2, H30T |
| Caleta Tiny Island | Open island colony | DJI L2, H30T |

For detection results and validation status, see the [client status report](docs/reports/CLIENT_STATUS_REPORT_2026-02-02.md) and [feature analysis](docs/reports/FEATURE_ANALYSIS.md).

## Documentation

### Reports & Analysis

- [STATUS.md](docs/reports/STATUS.md) — Current implementation state
- [Client Status Report](docs/reports/CLIENT_STATUS_REPORT_2026-02-02.md) — Detection results and deliverables
- [LIDAR_METHODOLOGY.md](docs/reports/LIDAR_METHODOLOGY.md) — Algorithm documentation
- [FEATURE_ANALYSIS.md](docs/reports/FEATURE_ANALYSIS.md) — Spectral feature analysis and parameter sensitivity
- [THERMAL_LIDAR_CROSSREF.md](docs/reports/THERMAL_LIDAR_CROSSREF.md) — Thermal georeferencing and cross-sensor analysis
- [THERMAL_LIDAR_FUSION_INTERFACE_SPEC.md](docs/reports/THERMAL_LIDAR_FUSION_INTERFACE_SPEC.md) — Fusion-ready CRS/data contract and QA gates
- [LIDAR_VALIDATION.md](docs/reports/LIDAR_VALIDATION.md) — AOI-clipped validation

### Process & Protocols

- [LABELING_PROTOCOL.md](docs/process/LABELING_PROTOCOL.md) — Precision estimation labeling
- [WORKSTREAMS_QC_VS_SCIENCE.md](docs/process/WORKSTREAMS_QC_VS_SCIENCE.md) — QC vs scientific milestones
- [BLOCKED_AOIS.md](docs/process/BLOCKED_AOIS.md) — AOI authority gating for official reporting
- [VALIDATION_PROTOCOL.md](docs/VALIDATION_PROTOCOL.md) — Subset QA + stratified audit protocol

### Development

- [DEVELOPMENT.md](DEVELOPMENT.md) — Project structure, setup, reproducibility
- [RUNBOOK.md](RUNBOOK.md) — Tested commands
- [DJI_CAMERA_MODEL_RESEARCH_BRIEF.md](docs/research/DJI_CAMERA_MODEL_RESEARCH_BRIEF.md) — Camera model conventions

## Known Limitations

| Constraint | Details |
|------------|---------|
| Burrow occlusion | Overhead LiDAR cannot detect penguins inside burrows (~43% at cave sites). This is a physics constraint, not a pipeline deficiency. |
| Blob ≠ individual | Detections are blob centroids; rocks, vegetation, and burrow rims can produce false positives. Precision labeling is [in progress](docs/process/LABELING_PROTOCOL.md). |
| Adjacent merging | Close-standing penguins may merge into a single detection at 0.25 m resolution. |
| Sensor-specific tuning | DJI L2 and TrueView 515 point clouds require different processing parameters. |
| AOI boundary sensitivity | Detection counts depend on the clipping polygon; boundary confirmation is needed for some sites. |
| Thermal discrimination | Oblique thermal views do not reliably distinguish penguins from empty burrows. See [cross-sensor analysis](docs/reports/THERMAL_LIDAR_CROSSREF.md). |

## License

Internal project. Contact the project owner for usage permissions.
