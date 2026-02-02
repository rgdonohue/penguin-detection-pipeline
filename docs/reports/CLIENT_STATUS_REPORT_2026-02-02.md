# Client Status Report — LiDAR Deliverables (Argentina 2025)

Date: 2026-02-02  
Project: Penguin Detection Pipeline v4.0

## Executive Summary

- **LiDAR detection is the current focus.** The repo contains a reproducible LiDAR candidate detection pipeline, tested commands, and QC outputs for the 2025 Argentina datasets.
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

## Known Limitations (Important for Interpretation)

- **“Candidate” ≠ “penguin.”** Each detection is a centroid of a penguin-sized above-ground blob in a HAG threshold mask. Nearby penguins may merge; rocks/vegetation/burrow rims can create false positives.
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

- **AOI boundary confirmation** (items above) — once boundaries are confirmed, we regenerate clipped counts and produce an updated per-site comparison table.
- **Precision audit** — labeling ~80 candidates per site as true positive / false positive / uncertain would give a precision estimate and allow adjusted count ranges. This has not been done yet.

## Repo Quick Start

- Commands: `RUNBOOK.md`  
- Current state: `docs/reports/STATUS.md`  
- LiDAR methodology: `docs/reports/LIDAR_METHODOLOGY.md`

