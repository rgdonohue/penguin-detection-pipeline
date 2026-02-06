# Client Status Report — LiDAR Penguin Detection (Argentina 2025)

Date: 2026-02-02 (updated 2026-02-04)
Project: Penguin Detection Pipeline v4.0

> **Update 2026-02-04:** San Lorenzo Road AOI resolved — client provided 34 GPS waypoints, convex hull polygon created (1.08 ha, 281 detections, 0.78 rate). Added AOI inventory report. Added Caleta nested box count clarification.

## The Short Version

**LiDAR detection works well at open island sites.** At Caleta Tiny Island, the pipeline found 329 candidates against a field count of 321 — a 1.02 detection rate (with the AOI extended to the full shoreline per client request). Feature analysis suggests 85–95% of these candidates are real penguins. We are running a precision audit now to confirm that number.

**LiDAR alone is insufficient at mainland burrow sites.** San Lorenzo Caves and Plains detection rates are 0.19–0.29. This is primarily a physics problem: ~43% of penguins at cave sites are inside burrows with no above-ground signature, setting a theoretical detection ceiling of ~57%. The San Lorenzo Road site (open terrain) achieves 0.78 — better than the burrow sites, consistent with less occlusion.

**We need confirmed AOI boundaries from the field team to finalize San Lorenzo counts.** Without them, we cannot determine whether the low detection rates are due to burrow occlusion, AOI mismatch, or both.

## Results

| Site | Type | Field Count | Candidates | Detection Rate | Estimated Precision |
|------|------|-----------|------------|---------------|-------------------|
| Caleta Tiny Island | Open island | 321 | 329 | **1.02** | 85–95% (pending labeling) |
| Caleta Small Island | Open island | 1,557 | 1,255 | **0.81** | Similar expected |
| San Lorenzo Road | Open mainland | 359 | 281 | **0.78** | Unknown (open terrain) |
| San Lorenzo Caves | Burrow-heavy | 908 | 263 | 0.29 | Unknown |
| San Lorenzo Plains | Mixed terrain | 453 | 86 | 0.19 | Unknown |

**Detection rate** = candidates / field count. Below 1.0 means under-detection — the pipeline finds fewer candidates than field teams counted penguins.

**Where does the 85–95% precision estimate come from?** Per-detection spectral features (NIR intensity, RGB color, greenness index) were extracted for all 315 inside-AOI detections at Caleta Tiny. 86% (272/315) form a tight spectral core with no anomalous features. Only 8 detections (2.5%) show anomalies in multiple features simultaneously — these are the strongest false positive candidates. Even if every non-core detection is a false positive (worst case), precision would be 86%. The true value is likely higher because many non-core detections are probably penguins with slightly atypical features. Full analysis: `docs/reports/FEATURE_ANALYSIS.md`.

## What This Means for Operations

**Island colony monitoring is viable now.** At detection rates of 0.81–0.98 and expected precision of 85–95%, LiDAR can produce penguin count estimates for open island colonies that are comparable to manual field counts. Once the precision audit is complete, candidate counts can be adjusted by the measured precision to produce calibrated estimates with confidence intervals.

**Mainland burrow sites need a different approach.** LiDAR detects visible (above-ground) penguins reliably, but physically cannot detect penguins inside burrows. We tested whether thermal imaging could fill this gap — it cannot, at least not with oblique camera angles at burrow sites (see "Thermal–LiDAR Cross-Reference" below). For sites like San Lorenzo Caves, operational counting would require either:
- LiDAR count × burrow correction factor (derived from field observations of burrow occupancy rates)
- Nadir thermal collection targeting burrow openings (untested — would require a separate data collection)
- Direct field counts at burrow-heavy sites, with LiDAR covering open areas

**The greenness index transfers across sites and sensors.** This is relevant for scaling: the (G−R)/(G+R) signature of penguin detections is consistent across both DJI L2 and TrueView 515 sensors and across all tested sites. Intensity values are sensor-locked and do not transfer.

## Precision Audit Status

80-sample label bundles have been generated for Caleta Tiny Island and Caleta Small Island. Each sample includes a dual-panel crop image (RGB + height-above-ground) for visual classification. The labeling protocol is documented in `docs/process/LABELING_PROTOCOL.md`.

**Expected completion:** Labeling takes approximately 1–2 hours per site. Once complete, `scripts/estimate_precision.py` produces Wilson score confidence intervals. Precision numbers and adjusted count estimates will follow immediately.

## Coordinate Clarifications Needed

We've been working from the GPS coordinates and annotated map screenshots in the field notes PDF. Most of the boundaries have been digitized and converted to AOI polygons. A few need clarification before we can produce validated counts:

1. **"Bushes" box count (55 penguins):** The four GPS coordinates on p.4 of the field notes (42.085273 S / 63.866958 W, etc.) produce a ~200 m² polygon that falls inside LiDAR tile 11.9, which covers the Plains area — not where we'd expect the Bushes count. The reported area is 3.8 ha (~190x larger). Are these coordinates for a different box count, or internal waypoints within a larger area?
2. **Caves box count (32 penguins):** We don't have corner coordinates for this one. Is it a sub-area within the larger Caves survey zone?
3. **San Lorenzo Road (359 penguins):** **RESOLVED.** Client provided 34 GPS waypoints (Nov 08, 2025). Convex hull polygon created (1.08 ha, 11 vertices). 281 detections inside AOI = 0.78 detection rate. Open road corridor terrain explains the higher rate vs other San Lorenzo sites.
4. **Caleta box count sub-areas (8 + 12 penguins):** Box Count 1 (8 penguins) appears to be spatially nested inside Box Count 2 (12 penguins) based on the Google Maps screenshots. If confirmed, these 8 are a subset of 12 — not additional — and the grand total should be 3,697 (not 3,705). Can you confirm nesting?
5. **Caleta box count tiles:** We have the Google Maps screenshots with polygons. Can you confirm which LiDAR tiles these correspond to?

We also noticed that LiDAR tiles `box_count_11.9` and `box_count_11.10` appear spatially swapped relative to the site zone names — 11.9 covers the Plains area and 11.10 covers Caves. Can you confirm which is which?

Detailed notes: `notes/client_aoi_clarifications.md`

## What's Delivered

| Deliverable | Status |
|-------------|--------|
| LiDAR detection pipeline (deterministic, regression-tested) | Complete |
| AOI-clipped evaluation tools | Complete |
| Per-detection feature analysis (3 sites, 2 sensors) | Complete |
| Parameter sensitivity analysis | Complete |
| Label sample bundles (2 sites, 80 samples each, RGB+HAG crops) | Complete |
| Precision estimates with confidence intervals | Pending labeling |
| Validated per-site count table | Pending labeling + AOI confirmation |

## Recent Engineering Work (December–January)

Between the initial detection results and this report, we ran a series of systematic experiments to validate parameter choices and explore improvement paths:

- **Resolution analysis:** Tested cell sizes from 0.10 m to 0.30 m on both sensors. Confirmed that the current production resolutions (0.25 m for DJI L2, 0.30 m for TrueView 515) are well-matched to point density (~9–14 points per cell). Finer resolutions degrade detection quality due to empty cells.
- **Ground model comparison:** Compared minimum-Z vs 5th-percentile ground estimation. Effect is site-dependent (+9% detections on open island, -1% on burrow terrain). Current method is appropriate.
- **Height band validation:** HAG histogram analysis identified a clear penguin-height signal at 0.555 m on the open island. Tested widening the detection band — overcounts by 2x. Current narrow band (0.28–0.48 m) is well-tuned.
- **Pipeline bug fix:** Identified and corrected a convergence issue in an internal estimator (`p95` → `max`). With corrected settings (`--top-method max --skip-copc`), Caleta Tiny produces 341 total candidates (vs 321 field count = +6%). Regression test suite updated (golden baseline: 776).

Full experiment results are documented in the methodology report (`docs/reports/LIDAR_METHODOLOGY.md` §5).

## Thermal–LiDAR Cross-Reference (San Lorenzo)

We georeferenced 28 thermal labels (12 "Penguin in Burrow", 9 "Penguin Deep in Burrow", 7 "Empty Burrow") from the San Lorenzo Bushes box count area and cross-referenced them against LiDAR detections. Key findings:

- **LiDAR recall at burrow sites:** 9/21 (43%) of thermally-labeled penguins have a LiDAR detection within 2 m. 6/12 shallow penguins detected vs 3/9 deep penguins — consistent with LiDAR detecting above-ground signatures only.
- **Precision in reference box:** 7/7 LiDAR detections inside the 14 m × 14 m reference box are within 2 m of a labeled penguin (100% local precision, n=7).
- **Empty burrows cause false positives:** 4/7 (57%) empty burrows have a nearby LiDAR detection, confirming burrow rims as a false positive source.

We also tested whether **thermal brightness** (without absolute calibration) could help discriminate penguins from empty burrows. It cannot — at least not with oblique thermal views at burrow sites. Shallow penguins are only +0.6°C above background with high variance, and empty burrows are also warmer than background (+0.4°C), confounding the signal. Cohen's d = 0.04 (negligible). The physical reason: at 45° oblique pitch, the camera sees burrow rims, not penguin bodies.

## What's Not Being Worked On

Thermal detection and LiDAR–thermal fusion are **not operational and not in active development** for this project phase. The thermal extraction infrastructure works (16-bit radiometric), but:
- Temperature calibration has unresolved offsets (~9°C)
- Thermal detection F1 is 0.02–0.30
- A discrimination proof of concept confirmed that oblique thermal views at burrow sites do not distinguish penguins from empty burrows (details above)

Thermal fusion might work at open-colony sites where penguins stand exposed on rock, but we have no labeled thermal data there to test. Pursuing this would require a separate focused effort with nadir thermal collection.

## Repo Quick Start

- Commands: `RUNBOOK.md`
- Current state: `docs/reports/STATUS.md`
- LiDAR methodology: `docs/reports/LIDAR_METHODOLOGY.md`
- Feature analysis: `docs/reports/FEATURE_ANALYSIS.md`
- Thermal–LiDAR cross-reference: `docs/reports/THERMAL_LIDAR_CROSSREF.md`
- Labeling protocol: `docs/process/LABELING_PROTOCOL.md`
