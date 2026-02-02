# Client Status Report — LiDAR Deliverables (Argentina 2025)

Date: 2026-02-02  
Project: Penguin Detection Pipeline v4.0

## Executive Summary

- **LiDAR detection is the current focus.** The repo contains a reproducible LiDAR candidate detection pipeline, tested commands, and QC outputs for the 2025 Argentina datasets.
- **Feature analysis provides independent evidence that detections represent a consistent object class** — 86% of inside-AOI detections at Caleta Tiny Island share a tight spectral signature (NIR intensity, RGB color, greenness index) that is not explained by the pipeline's geometric filters alone.
- **Precision estimation is in progress** — 80-sample label bundles with RGB+HAG crop images have been generated for two sites; manual labeling is underway.
- **Thermal processing and fusion are paused** pending calibration and thermal georeferencing.
- The **main open issue** for comparing candidate counts to field counts is **AOI boundary definition** for several San Lorenzo and box-count sites.

## What’s Ready Now (Deliverables)

### 1) LiDAR candidate detection
- Pipeline that produces repeatable results from LAS/LAZ input, outputting:
  - Candidate detections (points with per-candidate height, area, and shape features)
  - GIS layers (GeoJSON / GeoPackage)
  - QC plots and provenance metadata
- Commands are documented in `RUNBOOK.md`.

### 2) AOI-clipped evaluation
- Tools to clip candidates to AOI polygons and compute site-level counts and densities.
- Comparison to field counts is only meaningful when the AOI polygon matches the actual field-counted area.

### 3) Current results (candidate/field ratios)
These are **candidate counts** (not confirmed individuals), clipped to the best-available AOIs:

| Site | Field Count | LiDAR Candidates | Candidate/Field Ratio | Notes |
| --- | ---:| ---:| ---:| --- |
| Caleta Tiny Island | 321 | 315 | 0.98 | AOI from LiDAR footprint (Otsu); AOI area 0.53 ha vs reported 0.7 ha |
| Caleta Small Island | 1,557 | 1,255 | 0.81 | AOI from LiDAR footprint; some shoreline edge effects |
| San Lorenzo Caves | 908 | 263 | 0.29 | AOI from GPS waypoints (convex hull); burrow-heavy site |
| San Lorenzo Plains | 453 | 86 | 0.19 | AOI from GPS waypoints; AOI area 0.73 ha vs reported 0.98 ha |

Full context, AOI status, and caveats are in:
- `docs/reports/LIDAR_ASSESSMENT_2026-01.md`
- `docs/reports/LIDAR_VALIDATION.md`
- `docs/reports/DETECTION_RATE_SUMMARY.md`

## Feature Analysis — "How Do We Know These Are Penguins?"

Per-detection spectral features were extracted from the LiDAR point clouds (RGB color, 905 nm NIR intensity, derived indices) for 3 sites across 2 sensors (DJI L2 and TrueView 515). The goal was to test whether features beyond height and size can distinguish penguins from false positives.

**Key findings:**

1. **Inside-AOI detections are spectrally homogeneous.** At Caleta Tiny Island, 86% of 315 inside-AOI detections form a tight core — consistent intensity (~18,000), warm-toned RGB, near-zero greenness. The 25 outside-AOI detections (water/rock) have a very different signature (intensity ~6,600, higher greenness). This consistency is not caused by the pipeline's geometric filters and provides independent evidence that the detections represent a single object class.

2. **Greenness index is the most portable feature** — near-zero signature transfers across sites and sensors. Intensity values are site-specific and completely sensor-locked (DJI L2 vs TrueView 515 scales are incompatible).

3. **Parameter sensitivity is dominated by hag_max** (upper height bound). Other parameters have minimal effect on detection count.

4. **San Lorenzo shows wider feature spreads**, consistent with more diverse ground cover and higher false positive contamination at mainland sites.

Full analysis with plots: `docs/reports/FEATURE_ANALYSIS.md`

## Precision Estimation (In Progress)

80-sample label bundles have been generated for Caleta Tiny Island and Caleta Small Island. Each sample includes an RGB + height-above-ground crop image for visual classification. Manual labeling is underway using a documented protocol (`docs/process/LABELING_PROTOCOL.md`). Once labeling is complete, Wilson score confidence intervals will be computed for per-site precision.

## Known Limitations (Important for Interpretation)

- **"Candidate" ≠ "penguin."** Each detection is a centroid of a penguin-sized above-ground blob in a HAG threshold mask. Nearby penguins may merge; rocks/vegetation/burrow rims can create false positives. Precision estimation (above) will quantify the false positive rate.
- **Burrow occlusion limits detection.** Analysis of 84 thermal-labeled penguins at the legacy site found ~43% deep in burrows and invisible to overhead LiDAR. If this proportion holds at cave sites, it sets an approximate detection ceiling of ~57%. This is an estimate from a small sample.
- **AOI sensitivity:** site-level ratios are highly sensitive to the exact polygon used for clipping (boundary placement can change counts materially at edges).

## AOI Clarifications Needed (Client Action Requested)

To compare candidates against all reported field counts (~3,705), we need confirmed boundaries for the field-counted areas:

1) **San Lorenzo Road (359 penguins)**: boundary waypoints/polygon not provided in notes.  
2) **San Lorenzo Caves box count (32 penguins)**: need the 4 corner coordinates/polygon.  
3) **San Lorenzo “Bushes” box count (55 penguins)**: the 4 “box” coordinates in the PDF appear inconsistent (polygon falls in the wrong tile and is far smaller than expected). We need confirmation/correction.  
4) **Caleta box count polygons** (small sub-areas): boundaries needed to include these in AOI-clipped validation.

Preferred formats (any one is fine):
- A polygon layer in **GeoJSON**, **KML**, or **shapefile**, or
- A simple table of corner coordinates per AOI (4 corners), or
- A screenshot/annotation on a basemap where we can digitize polygons (with confirmation).

## Next Steps

- **Complete precision labeling** — finish manual review of 80-sample bundles for Caleta Tiny and Small Islands; compute precision estimates with confidence intervals.
- **AOI boundary confirmation** (items above) — once boundaries are confirmed, we regenerate clipped counts and produce an updated per-site comparison table.
- **Feature-by-label analysis** — after labeling, compare feature distributions for true positives vs false positives to quantify which features best identify false detections.

## Repo Quick Start

- Commands: `RUNBOOK.md`
- Current state: `docs/reports/STATUS.md`
- LiDAR methodology: `docs/reports/LIDAR_METHODOLOGY.md`
- Feature analysis: `docs/reports/FEATURE_ANALYSIS.md`
- Labeling protocol: `docs/process/LABELING_PROTOCOL.md`

