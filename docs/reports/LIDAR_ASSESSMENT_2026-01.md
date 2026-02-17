# LiDAR Detection Assessment — January 2026

This document summarises where the pipeline stands after tuning for the Argentina 2025 field data. It is written for the Conservation Technology Alliance.

## Detection rates by site

| Site | Ground truth | Candidates | Ratio | Notes |
|------|------------:|----------:|------:|-------|
| Caleta Tiny Island | 321 | 315 | 0.98 | LiDAR-derived AOI, closed boundary — highest confidence |
| Caleta Small Island | 1,557 | 1,255 | 0.81 | LiDAR-derived AOI |
| San Lorenzo Caves | 908 | 263 | 0.29 | Approximate AOI, burrow-dominated |
| San Lorenzo Plains | 453 | 86 | 0.19 | Approximate AOI, sparse transect |

The island sites perform well. The mainland sites do not, and two factors explain most of the gap.

**Burrow occlusion.** Thermal labels from San Lorenzo show 36 of 84 penguins (43%) classified as "deep in burrow." These animals have no above-ground signature. Even with perfect parameters, the detection ceiling at burrow-heavy sites is roughly 57%.

**AOI boundary uncertainty.** San Lorenzo boundaries come from sparse GPS waypoints walked during field transects. The Caves convex hull (8 waypoints, 0.60 ha) matches the reported area, but Plains (33 waypoints, 0.73 ha) falls short of the reported 0.98 ha. Road has 359 counted penguins but no boundary waypoints were originally documented. Bushes box coordinates appear mislabelled in the field notes. Until boundaries are confirmed, the low mainland ratios may partly reflect AOI mismatch rather than missed penguins.

## Pipeline reliability

The golden AOI test produces exactly 776 detections (SHA256-verified) on every run. The pipeline handles both DJI L2 and TrueView 515 point clouds, auto-detects CRS from LAS headers, and streams files up to 22 GB (754M points total) with configurable memory limits.

## Detection semantics

Each detection is the centroid of a connected-component blob in the HAG threshold mask. Adjacent penguins may merge into one detection; large blobs may contain multiple individuals (watershed splitting partially addresses this); and objects near rocks, vegetation, or burrow edges can produce false positives. Precision estimation from manual labelling of detection samples is in progress.

## Experiments completed

**Intensity analysis.** The pipeline now extracts per-detection 905 nm NIR intensity (`--extract-intensity`), building a per-cell mean intensity grid and enriching detections with intensity statistics. This allows plotting intensity distributions per site and evaluating whether NIR reflectance discriminates penguins from background.

**Confidence scoring.** A per-detection confidence score (`--compute-confidence`) combines HAG membership (Gaussian centred on 0.35 m), area membership, and shape metrics (circularity + solidity) into a [0, 1] geometric mean.

**Parameter sensitivity.** A sweep framework (`scripts/lidar_parameter_sweep.py`) runs 1D and 2D sweeps over hag_min, hag_max, min_area_cells, and max_area_cells. The consistent finding across both sensors is that hag_max is the dominant sensitivity parameter.

## Open research paths

- **ML classification.** With labelled TP/FP samples, a binary classifier on HAG, area, shape, and intensity features could improve precision.
- **Multi-scale detection.** Running at two cell resolutions (e.g. 0.15 m + 0.30 m) might improve detection of both small individuals and clustered groups.
- **Temporal tracking.** Repeated surveys at the same site would support change detection and population dynamics.
- **Thermal fusion.** The fusion pipeline implements CRS-aware spatial joins between LiDAR and thermal detections. Thermal calibration (~9 C offset) is the current blocker.

## Recommendations

The highest-impact action is to resolve AOI boundaries — digitised polygons or annotated imagery for San Lorenzo would immediately clarify whether the low mainland rates reflect real under-detection or boundary mismatch.

Second, complete the precision audit: label 80+ detection samples per site, compute TP/FP rates, and produce adjusted count estimates with confidence intervals.

For publication-quality results, focus on Caleta: Tiny Island (0.98 ratio) and Small Island (0.81) have the most reliable AOIs and the closest match to ground truth.

## Appendix: parameters and data

### Parameter settings

| Parameter | Legacy (cloud3) | DJI L2 (Caleta) | TrueView 515 (San Lorenzo) |
|-----------|-----------------|------------------|---------------------------|
| Cell resolution | 0.25m | 0.25m | 0.30m |
| HAG range | 0.20-0.60m | 0.28-0.48m | 0.28-0.48m |
| Min area cells | 2 | 3 | 3 |
| Max area cells | 80 | 60 | 50 |
| Dedupe radius | — | 0.5m | 0.5m |

### CRS mapping

| Dataset | Native CRS | Pipeline CRS | Notes |
|---------|-----------|-------------|-------|
| Legacy (Punta Tombo) | EPSG:32720 (UTM 20S) | EPSG:32720 | Direct |
| Caleta (DJI L2) | EPSG:32720 | EPSG:32720 | Direct |
| San Lorenzo (TrueView 515) | EPSG:5345 (POSGAR) | EPSG:32720 (via PDAL reprojection) | Requires preprocessing |

### Data catalogue

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
