# Client Status Report — LiDAR Penguin Detection (Argentina 2025)

Date: 2026-02-02
Project: Penguin Detection Pipeline v4.0

## The Short Version

**LiDAR detection works well at open island sites.** At Caleta Tiny Island, the pipeline found 315 candidates against a field count of 321 — a 0.98 detection rate. Feature analysis suggests 85–95% of these candidates are real penguins. We are running a precision audit now to confirm that number.

**LiDAR alone is insufficient at mainland burrow sites.** San Lorenzo detection rates are 0.19–0.29. This is primarily a physics problem: ~43% of penguins at cave sites are inside burrows with no above-ground signature, setting a theoretical detection ceiling of ~57%. Even with perfect precision, LiDAR-only F1 cannot exceed ~0.45 at these sites.

**We need confirmed AOI boundaries from the field team to finalize San Lorenzo counts.** Without them, we cannot determine whether the low detection rates are due to burrow occlusion, AOI mismatch, or both.

## Results

| Site | Type | Field Count | Candidates | Detection Rate | Estimated Precision |
|------|------|-----------|------------|---------------|-------------------|
| Caleta Tiny Island | Open island | 321 | 315 | **0.98** | 85–95% (pending labeling) |
| Caleta Small Island | Open island | 1,557 | 1,255 | **0.81** | Similar expected |
| San Lorenzo Caves | Burrow-heavy | 908 | 263 | 0.29 | Unknown |
| San Lorenzo Plains | Burrow-heavy | 453 | 86 | 0.19 | Unknown |

**Detection rate** = candidates / field count. Below 1.0 means under-detection — the pipeline finds fewer candidates than field teams counted penguins.

**Where does the 85–95% precision estimate come from?** Per-detection spectral features (NIR intensity, RGB color, greenness index) were extracted for all 315 inside-AOI detections at Caleta Tiny. 86% (272/315) form a tight spectral core with no anomalous features. Only 8 detections (2.5%) show anomalies in multiple features simultaneously — these are the strongest false positive candidates. Even if every non-core detection is a false positive (worst case), precision would be 86%. The true value is likely higher because many non-core detections are probably penguins with slightly atypical features. Full analysis: `docs/reports/FEATURE_ANALYSIS.md`.

## What This Means for Operations

**Island colony monitoring is viable now.** At detection rates of 0.81–0.98 and expected precision of 85–95%, LiDAR can produce penguin count estimates for open island colonies that are comparable to manual field counts. Once the precision audit is complete, candidate counts can be adjusted by the measured precision to produce calibrated estimates with confidence intervals.

**Mainland burrow sites need a different approach.** LiDAR detects visible (above-ground) penguins reliably, but physically cannot detect penguins inside burrows. For sites like San Lorenzo Caves, operational counting would require either:
- LiDAR + thermal fusion (thermal can detect body heat through burrow openings — infrastructure exists but calibration is unresolved)
- LiDAR count × burrow correction factor (derived from thermal sampling or field observations)
- Thermal-only detection at burrow sites

**The greenness index transfers across sites and sensors.** This is relevant for scaling: the (G−R)/(G+R) signature of penguin detections is consistent across both DJI L2 and TrueView 515 sensors and across all tested sites. Intensity values are sensor-locked and do not transfer.

## Precision Audit Status

80-sample label bundles have been generated for Caleta Tiny Island and Caleta Small Island. Each sample includes a dual-panel crop image (RGB + height-above-ground) for visual classification. The labeling protocol is documented in `docs/process/LABELING_PROTOCOL.md`.

**Expected completion:** Labeling takes approximately 1–2 hours per site. Once complete, `scripts/estimate_precision.py` produces Wilson score confidence intervals. Precision numbers and adjusted count estimates will follow immediately.

## Action Required: AOI Boundary Confirmation

**We cannot produce validated counts for San Lorenzo until we receive confirmed AOI boundaries.** The current polygons were constructed from sparse GPS waypoints and have known issues:

1. **San Lorenzo Road (359 penguins):** No boundary waypoints provided. We have no polygon.
2. **San Lorenzo Caves box count (32 penguins):** Need the 4 corner coordinates.
3. **San Lorenzo "Bushes" box count (55 penguins):** The coordinates in the PDF appear inconsistent — the polygon falls in the wrong tile.
4. **Caleta box count sub-areas:** Boundaries needed.

**Please provide by Feb 14** in any of these formats:
- Polygon layer (GeoJSON, KML, or shapefile)
- Table of corner coordinates per AOI
- Annotated screenshot on a basemap (we can digitize from this)

Detailed request with specific coordinate questions: `notes/client_aoi_clarifications.md`

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

## What's Not Being Worked On

Thermal detection and LiDAR–thermal fusion are **not operational and not in active development** for this project phase. The thermal extraction infrastructure works (16-bit radiometric), but temperature calibration has unresolved offsets (~9°C) and thermal detection F1 is 0.02–0.30. Resolving this would require a separate focused effort.

## Repo Quick Start

- Commands: `RUNBOOK.md`
- Current state: `docs/reports/STATUS.md`
- LiDAR methodology: `docs/reports/LIDAR_METHODOLOGY.md`
- Feature analysis: `docs/reports/FEATURE_ANALYSIS.md`
- Labeling protocol: `docs/process/LABELING_PROTOCOL.md`
