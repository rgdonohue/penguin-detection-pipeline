# Penguin Detection Pipeline

Automated detection of Magellanic penguins from drone LiDAR surveys, developed with the [Conservation Technology Alliance](https://www.conservationta.org/).

**Bottom line:** LiDAR detection works well at open island colony sites. At Caleta Tiny Island, the pipeline detected 315 candidates against a field count of 321 (0.98 ratio), and feature analysis suggests precision is likely 85–95%. At mainland burrow-heavy sites, LiDAR alone detects only 19–29% of penguins — most are underground and invisible to overhead sensing.

## Results

Detection counts compared to field observations at four Argentina 2025 sites:

| Site | Type | Field Count | LiDAR Candidates | Detection Rate | Notes |
|------|------|-----------|-------------------|---------------|-------|
| Caleta Tiny Island | Open island | 321 | 315 | **0.98** | Best-validated site; AOI from island boundary |
| Caleta Small Island | Open island | 1,557 | 1,255 | **0.81** | Some shoreline edge effects in AOI |
| San Lorenzo Caves | Burrow-heavy | 908 | 263 | 0.29 | ~43% of penguins in burrows; theoretical ceiling ~57% |
| San Lorenzo Plains | Burrow-heavy | 453 | 86 | 0.19 | AOI boundary uncertain (0.73 ha vs reported 0.98 ha) |

**Detection rate** = LiDAR candidates / field count. Values below 1.0 mean under-detection (the pipeline finds fewer candidates than field teams counted). The San Lorenzo under-detection is primarily a physics problem: overhead LiDAR cannot see penguins inside burrows.

**Estimated precision (island sites): 85–95%.** Feature analysis of 315 Caleta Tiny detections found 86% form a tight spectral core — consistent NIR intensity, warm RGB, near-zero greenness — with only 2.5% showing multi-feature anomalies (the strongest false positive candidates). Manual labeling of 80-sample bundles is in progress to confirm this estimate. See [`docs/reports/FEATURE_ANALYSIS.md`](docs/reports/FEATURE_ANALYSIS.md).

## How It Works

Point clouds are normalized to height above ground (HAG), rasterized to a 0.25 m grid, and filtered to the 0.2–0.6 m height band (standing Magellanic penguin height). Connected-component analysis extracts blob candidates, and morphological filters remove objects outside the 0.125–5.0 m² size range. The pipeline is deterministic and regression-tested against a baseline dataset.

Thermal detection and LiDAR–thermal fusion were explored but are not operational. Thermal extraction infrastructure works (16-bit radiometric), but a discrimination proof of concept showed that oblique thermal views at burrow sites do not distinguish penguins from empty burrows (Cohen's d = 0.04). Temperature calibration has unresolved offsets and detection F1 is 0.02–0.30. These are not being developed further in the current project phase.

## Study Sites

Field data collected across San Lorenzo and Caleta sites in Patagonia during 2025, covering ~3,705 penguins at densities from 15 to 1,518 per hectare.

| Site | Field Count | Area (ha) | Density (/ha) | Sensors |
|------|------------|-----------|---------------|---------|
| San Lorenzo Caves | 908 | 0.60 | 1,518 | TrueView 515, H30T |
| San Lorenzo Plains | 453 | 0.98 | 464 | TrueView 515, H30T |
| San Lorenzo Road | 359 | — | — | TrueView 515, H30T |
| San Lorenzo Box Counts | 87 | 4.95 | 15–28 | H30T |
| Caleta Small Island | 1,557 | 4.0 | 389 | DJI L2, H30T |
| Caleta Tiny Island | 321 | 0.7 | 459 | DJI L2, H30T |
| Caleta Box Counts | 20 | — | — | H30T |

## Known Limitations

| Limitation | Impact |
|------------|--------|
| Burrow occlusion | ~43% of penguins invisible to overhead LiDAR at cave sites. Not solvable by parameter tuning. |
| Candidate ≠ individual | Detections are blob centroids; false positives from rocks, vegetation, burrow rims. Precision audit in progress. |
| Adjacent penguin merging | Close-standing penguins may produce a single detection at 0.25 m resolution |
| Sensor-specific tuning | DJI L2 and TrueView 515 require different parameters |
| AOI boundary sensitivity | Site-level counts change significantly depending on clipping polygon |

## What's Needed

1. **Precision confirmation** — Manual labeling of 80-sample crop bundles (Caleta Tiny + Small Islands) to get a measured precision number with confidence intervals.
2. **San Lorenzo AOI boundaries** — Field team confirmation of polygon boundaries for Road site and box count areas. We cannot produce validated counts without confirmed AOIs.
3. **Box count validation** — Detection on smaller sub-areas where ground truth boundaries are tighter.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for project structure, setup, reproducibility, and technical references.

## License

Internal project. Contact the project owner for usage permissions.
