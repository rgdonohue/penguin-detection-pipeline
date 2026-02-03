# LiDAR Detection Assessment — January 2026

Prepared for the Conservation Technology Alliance

## 1. Executive Summary

The LiDAR penguin detection pipeline processes drone-collected point cloud data to identify Magellanic penguin candidates using Height Above Ground (HAG) analysis. After tuning for Argentina 2025 field data, the pipeline achieves near-unity detection rates on well-defined island sites (Caleta Tiny: 0.98 ratio, Caleta Small: 0.81) and lower but expected rates on complex terrain sites with approximate boundaries (San Lorenzo Caves: 0.29, Plains: 0.19).

The dominant factors limiting detection rates are:
- **Burrow occlusion (~43% ceiling):** Penguins deep in burrows are invisible to overhead LiDAR, setting a theoretical maximum detection rate of ~57%.
- **AOI boundary uncertainty:** San Lorenzo site boundaries are approximate from GPS waypoints; actual detection rates within correct boundaries may be higher.
- **Candidate semantics:** Detections are blob centroids, not validated individual penguins.

The pipeline is deterministic, reproducible, and runs on 7 sensor/site combinations across two sensor types (DJI L2, TrueView 515).

## 2. What Works

### Per-Site Detection Rates

| Site | Ground Truth | Candidates | Ratio | Confidence |
|------|------------:|----------:|------:|------------|
| Caleta Tiny Island | 321 | 315 | 0.98 | High — LiDAR-derived AOI, closed boundary |
| Caleta Small Island | 1,557 | 1,255 | 0.81 | High — LiDAR-derived AOI |
| San Lorenzo Caves | 908 | 263 | 0.29 | Low — approximate AOI, burrow-dominated |
| San Lorenzo Plains | 453 | 86 | 0.19 | Low — approximate AOI, sparse transect |

### Pipeline Reliability

- **Reproducibility:** Golden AOI test produces exactly 776 detections (SHA256-verified signature) across all runs.
- **Multi-sensor support:** Validated on both DJI L2 (Caleta) and TrueView 515 (San Lorenzo) point clouds.
- **CRS handling:** Auto-detection from LAS headers with explicit override capability.
- **Scalability:** Streaming architecture handles files up to 22 GB (754M points total) with configurable memory limits.

## 3. Known Limitations

### Burrow Occlusion (~43% Ceiling)

Analysis of 84 thermal-labeled penguins found 36 (43%) classified as "deep in burrow." These penguins have no above-ground signature visible to LiDAR, establishing a fundamental detection ceiling of approximately 57% even with perfect parameters.

### AOI Boundary Uncertainty

San Lorenzo AOIs are derived from sparse GPS waypoints recorded during field transects:
- **Caves:** Convex hull of 8 waypoints gives 0.60 ha (matches reported area).
- **Plains:** Perimeter winding of 33 waypoints gives 0.73 ha (vs reported 0.98 ha).
- **Road:** 359 penguins counted but no boundary waypoints documented.
- **Bushes Box:** GPS corners from PDF appear mislabeled (fall inside Caves tile, not Bushes). Client clarification requested.

### Candidate vs. Individual Semantics

Each detection is the centroid of a connected-component blob in the HAG threshold mask. This means:
- Adjacent penguins may merge into a single detection.
- Large blobs may contain multiple individuals (watershed splitting partially addresses this).
- Detections near rocks, vegetation, or burrow edges may be false positives.

Precision estimation (TP/FP classification) is pending manual labeling of detection samples.

## 4. Research Paths Explored

### Intensity Analysis (Phase 3)

LiDAR return intensity (905nm NIR) was extracted per detection. The pipeline now supports `--extract-intensity` to build a per-cell mean intensity grid and enrich detections with `intensity_mean`, `intensity_min`, and `intensity_max` features. Analysis scripts can plot intensity distributions per site and evaluate whether 905nm reflectance discriminates penguins from rock/vegetation/guano.

### Confidence Scoring (Phase 4)

A per-detection confidence score was implemented (`--compute-confidence`) combining:
- **HAG score:** Gaussian membership centered on 0.35m (sigma 0.08m)
- **Area score:** Gaussian membership centered on expected penguin footprint
- **Shape score:** Weighted combination of circularity and solidity

Scores are [0, 1] geometric means that can be used for thresholding or ranking.

### Parameter Sensitivity (Phase 4)

A sweep framework (`scripts/lidar_parameter_sweep.py`) varies detection parameters systematically:
- 1D sweeps: hag_min, hag_max, min_area_cells, max_area_cells
- 2D heatmap: hag_min x hag_max interaction
- Output: CSV results + sensitivity plots

## 5. Research Paths Available

### ML Classification

With labeled detection samples (TP/FP), a binary classifier could be trained on HAG, area, shape, and intensity features to improve precision beyond rule-based thresholding.

### Multi-Scale Detection

Current detection uses a single cell resolution (0.25m). Multi-scale approaches (e.g., 0.15m + 0.30m) could improve detection of both small individual penguins and larger groups.

### Temporal Tracking

Repeated surveys of the same site could enable change detection and population dynamics analysis. The pipeline's deterministic output and CRS contracts support this.

### Fusion with Thermal

The fusion pipeline (`pipelines/fusion.py`) implements CRS-aware spatial joins between LiDAR and thermal detections. Thermal calibration (~9 C offset) is the current blocker.

## 6. Recommendations for Next Phase

1. **Resolve AOI boundaries:** Obtain digitized polygons or annotated imagery for San Lorenzo sites. This is the highest-impact action for improving detection rate comparisons.

2. **Complete precision audit:** Label 80+ detection samples per site to quantify TP/FP rate and produce adjusted count estimates.

3. **Run intensity analysis:** Process Caleta Tiny and Bushes box with `--extract-intensity` to evaluate whether 905nm intensity improves classification.

4. **Run parameter sensitivity:** Execute sweep on Caleta Tiny (best-validated site) to quantify detection count stability across parameter choices.

5. **Focus on Caleta for publication-quality results:** Caleta Tiny (0.98 ratio) and Small (0.81 ratio) have the most reliable AOIs and closest match to ground truth.

## 7. Appendix

### Parameter Settings

| Parameter | Legacy (cloud3) | DJI L2 (Caleta) | TrueView 515 (San Lorenzo) |
|-----------|-----------------|------------------|---------------------------|
| Cell resolution | 0.25m | 0.25m | 0.30m |
| HAG range | 0.20-0.60m | 0.28-0.48m | 0.28-0.48m |
| Min area cells | 2 | 3 | 3 |
| Max area cells | 80 | 60 | 50 |
| Dedupe radius | — | 0.5m | 0.5m |

### CRS Mapping

| Dataset | Native CRS | Pipeline CRS | Notes |
|---------|-----------|-------------|-------|
| Legacy (Punta Tombo) | EPSG:32720 (UTM 20S) | EPSG:32720 | Direct |
| Caleta (DJI L2) | EPSG:32720 | EPSG:32720 | Direct |
| San Lorenzo (TrueView 515) | EPSG:5345 (POSGAR) | EPSG:32720 (via PDAL reprojection) | Requires preprocessing |

### Data Catalogue

| Dataset | Files | Points | Size |
|---------|------:|-------:|-----:|
| San Lorenzo Full LiDAR | 1 | ~600M | 22.6 GB |
| San Lorenzo Box Count 11.9 | 1 | ~10M | 345 MB |
| San Lorenzo Box Count 11.10 | 1 | ~36M | 1.2 GB |
| Caleta Small Island | 17 | ~21.7M | ~2.5 GB |
| Caleta Tiny Island | 2 | ~8.4M | ~940 MB |
| Caleta Box Count 1 | 1 | — | — |
| Caleta Box Count 2 | 1 | — | — |
| Total | 24 | ~754M | 25.8 GB |
