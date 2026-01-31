# Detection Rate Summary — LiDAR Pipeline (January 2026)

## Per-Site Detection Rates

| Site | Ground Truth | Candidates | Ratio | AOI Source | AOI Area (ha) | Notes |
|------|------------:|----------:|------:|------------|-------------:|-------|
| Caleta Tiny Island | 321 | 315 | 0.98 | LiDAR footprint (Otsu) | 0.53 | Best-validated site; near-unity ratio |
| Caleta Small Island | 1,557 | 1,255 | 0.81 | LiDAR footprint | 4.07 | Good coverage; some shoreline edge effects |
| San Lorenzo Caves | 908 | 263 | 0.29 | GPS waypoints (convex hull) | 0.60 | AOI approximate; burrow occlusion ~43% ceiling |
| San Lorenzo Plains | 453 | 86 | 0.19 | GPS waypoints (perimeter winding) | 0.73 | AOI approximate; low density, sparse detections |
| San Lorenzo Bushes Box | 55 | TBD | TBD | GPS corners (PDF) | 0.02 | **CAVEAT:** GPS corners may be mislabeled (see validation doc) |
| San Lorenzo Caves Box | 32 | N/A | N/A | Missing | — | No GPS corners provided |
| San Lorenzo Road | 359 | N/A | N/A | Missing | — | No waypoints documented |
| Caleta Box Count 1 | ~20 | TBD | TBD | Missing | — | Needs digitized polygon |
| Caleta Box Count 2 | ~20 | TBD | TBD | Missing | — | Needs digitized polygon |

**Total accountable ground truth:** ~3,705 penguins across all sites.
**Currently evaluable:** ~2,786 penguins (Caleta Tiny + Small + San Lorenzo Caves + Plains).

## Key Caveats

1. **"Candidates" are not "penguins."** Each detection is a HAG-threshold blob centroid. A single candidate may contain 0, 1, or multiple penguins depending on clustering and occlusion.

2. **Burrow occlusion ceiling.** Thermal label analysis shows ~43% of penguins are "deep in burrow" and invisible to overhead LiDAR. This sets a theoretical detection ceiling of ~57% even with perfect parameters.

3. **AOI boundary uncertainty.** San Lorenzo AOIs are approximate — derived from sparse GPS waypoints. The Plains perimeter-winding polygon (0.73 ha) is smaller than the reported survey area (0.98 ha). Caleta island AOIs are more reliable (derived from LiDAR footprint).

4. **Cross-site parameter differences.** DJI L2 sensors (Caleta) use HAG 0.28-0.48m, cell 0.25m. TrueView 515 (San Lorenzo) uses HAG 0.28-0.48m, cell 0.30m. Legacy (cloud3.las) uses HAG 0.20-0.60m, cell 0.25m.

## Precision (Pending Label Audit)

Precision estimates require manual labeling of detection samples. See `docs/process/LABELING_PROTOCOL.md`.

| Site | Sample Size | Precision | 95% CI | Adjusted Count |
|------|----------:|--------:|------:|---------------:|
| — | — | Pending | — | — |

## Interpretation Guide

- **Ratio > 0.9:** Pipeline performing well for this site/AOI combination.
- **Ratio 0.5-0.9:** Expected range given burrow occlusion and parameter sensitivity.
- **Ratio < 0.3:** Likely dominated by AOI boundary error, parameter mismatch, or terrain complexity.
