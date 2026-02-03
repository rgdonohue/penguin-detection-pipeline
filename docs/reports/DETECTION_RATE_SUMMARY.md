# Detection Rate Summary — LiDAR Pipeline (February 2026)

## Per-Site Detection Rates

**Note:** Counts below use `--top-method max` (CLI default since Feb 2026). Previous counts (340/315) used a broken `p95` estimator that produced near-max behavior. See Key Caveats §5.

| Site | Ground Truth | Candidates (AOI) | Total (all tiles) | Ratio (AOI) | AOI Source | AOI Area (ha) | Notes |
|------|------------:|----------:|----------:|------:|------------|-------------:|-------|
| Caleta Tiny Island | 321 | ~315 | 317 | ~0.98 | LiDAR footprint (Otsu) | 0.53 | Best-validated site; near-unity ratio |
| Caleta Small Island | 1,557 | 1,255 | 1,473 | 0.81 | LiDAR footprint | 4.07 | Good coverage; some shoreline edge effects |
| San Lorenzo Caves | 908 | 263 | — | 0.29 | GPS waypoints (convex hull) | 0.60 | AOI approximate; burrow occlusion ~43% ceiling |
| San Lorenzo Plains | 453 | 86 | — | 0.19 | GPS waypoints (perimeter winding) | 0.73 | AOI approximate; low density, sparse detections |
| San Lorenzo Bushes Box | 55 | TBD | — | TBD | GPS corners (PDF) | 0.02 | **CAVEAT:** GPS corners may be mislabeled (see validation doc) |
| San Lorenzo Caves Box | 32 | N/A | — | N/A | Missing | — | No GPS corners provided |
| San Lorenzo Road | 359 | N/A | — | N/A | Missing | — | No waypoints documented |
| Caleta Box Count 1 | ~20 | TBD | — | TBD | Missing | — | Needs digitized polygon |
| Caleta Box Count 2 | ~20 | TBD | — | TBD | Missing | — | Needs digitized polygon |

**Total accountable ground truth:** ~3,705 penguins across all sites.
**Currently evaluable:** ~2,786 penguins (Caleta Tiny + Small + San Lorenzo Caves + Plains).

## Key Caveats

1. **"Candidates" are not "penguins."** Each detection is a HAG-threshold blob centroid. A single candidate may contain 0, 1, or multiple penguins depending on clustering and occlusion.

2. **Burrow occlusion ceiling.** Thermal label analysis shows ~43% of penguins are "deep in burrow" and invisible to overhead LiDAR. This sets a theoretical detection ceiling of ~57% even with perfect parameters.

3. **AOI boundary uncertainty.** San Lorenzo AOIs are approximate — derived from sparse GPS waypoints. The Plains perimeter-winding polygon (0.73 ha) is smaller than the reported survey area (0.98 ha). Caleta island AOIs are more reliable (derived from LiDAR footprint).

4. **Cross-site parameter differences.** DJI L2 sensors (Caleta) use HAG 0.28-0.48m, cell 0.25m. TrueView 515 (San Lorenzo) uses HAG 0.28-0.48m, cell 0.30m. Legacy (cloud3.las) uses HAG 0.20-0.60m, cell 0.25m.

5. **`top_method` correction (Feb 2026).** The CLI default changed from `p95` to `max`. The online p95 quantile estimator (rewritten at commit `76b01fc`) does not converge properly, producing ~3.4x over-detection. With `max`, Caleta Tiny gives 317 total (vs 321 field = 0.99 ratio). The golden baseline updated from 802 to 776 detections accordingly.

## Precision (Pending Label Audit)

Precision estimates require manual labeling of detection samples. See `docs/process/LABELING_PROTOCOL.md`.

| Site | Sample Size | Precision | 95% CI | Adjusted Count |
|------|----------:|--------:|------:|---------------:|
| — | — | Pending | — | — |

## Interpretation Guide

- **Ratio > 0.9:** Pipeline performing well for this site/AOI combination.
- **Ratio 0.5-0.9:** Expected range given burrow occlusion and parameter sensitivity.
- **Ratio < 0.3:** Likely dominated by AOI boundary error, parameter mismatch, or terrain complexity.
