# LiDAR Detection Feature Analysis

Date: 2026-02-02

## Purpose

Assess whether LiDAR point cloud features beyond geometric filtering can discriminate penguins from false positives. The pipeline currently accepts detections based on height (0.28–0.48 m HAG) and size (0.19–3.75 m², DJI L2 Caleta parameters at 0.25 m cell with min_area=3 and max_area=60) only. This analysis tests whether RGB color, NIR intensity, and derived indices add discriminative signal.

## Method

Per-detection features were extracted from a 0.5 m radius around each detection centroid by streaming the source LAS files. Features computed: mean RGB (16-bit), mean intensity (905 nm NIR), and derived indices (greenness, brightness, color warmth). Analysis was performed on two Caleta island sites where AOI boundaries are well-defined, plus a San Lorenzo box-count tile for cross-sensor comparison.

The primary comparison is inside-AOI vs outside-AOI detections. Inside-AOI detections are a mix of true penguins and false positives; outside-AOI detections (off-island) are almost certainly non-penguins (water, rocks, edge artifacts). Caleta sites use DJI L2 LiDAR with onboard 20 MP RGB camera; San Lorenzo uses TrueView 515 with multi-return capability.

## Data

| Site | Detections | Inside AOI | Outside AOI | Sensor |
|------|-----------|-----------|-------------|--------|
| Caleta Tiny Island | 317 | ~315 | ~2 | DJI L2 |
| Caleta Small Island | 1,473 | 1,473 | 0 | DJI L2 |
| San Lorenzo Box Count | 2,011 | — | — | TrueView 515 |

Note: San Lorenzo detections lack AOI polygons for inside/outside comparison; they are included for cross-sensor feature comparison only.

## Results

### 1. Intensity (905 nm NIR)

Strongest discriminator. At Caleta Tiny Island, inside-AOI detections cluster tightly at 15,000–22,000 (mean 18,025), while outside-AOI detections are bimodal with most below 5,000 (mean 6,644). A simple threshold at ~10,000 would reject most off-island artifacts.

However, **intensity values are site-specific**. Caleta Small Island inside-AOI mean is 14,717 with a broader distribution extending to ~5,000. The absolute values differ enough that a threshold calibrated on one site does not transfer directly to another.

### 2. RGB Color

Moderate discriminative signal, primarily through derived indices:

- **Greenness (G−R)/(G+R)**: Inside-AOI detections cluster tightly near zero (slightly negative = warm-toned). Outside-AOI detections include higher-greenness values (vegetation patches). Consistent across both sites.
- **Brightness (R+G+B)/3**: Inside-AOI mean is 97 (Tiny) and 67 (Small) in 8-bit scale. The large difference between sites suggests RGB values are sensitive to flight conditions (altitude, time of day, sun angle) or post-processing. Not reliable as a cross-site threshold.
- **Color warmth (R−B)**: Inside-AOI detections are consistently warm-toned (R > B). Some outside-AOI detections show cold tones (blue).

### 3. Morphological Features

HAG, area, circularity, and solidity show **no difference** between inside-AOI and outside-AOI groups. This is expected — the pipeline already filters on these features, so all detections have similar values by construction.

### 4. Within-Site Homogeneity

At Caleta Tiny Island, 272/315 (86%) of inside-AOI detections form a tight core with no outlier flags in any feature. The 8 multi-flag outliers (anomalous in ≥2 features simultaneously) are the strongest false positive candidates; two have intensity below 5,000.

This level of homogeneity is consistent with a high-precision detection set where most candidates are the same type of object (penguins). Confirmation requires manual labeling (sample bundle generated; see below).

### 5. Cross-Sensor Comparison (DJI L2 vs TrueView 515)

San Lorenzo (TrueView 515) detections were extracted from a single box-count tile (box_count_11.9.las, 2,011 detections) to compare sensor behavior.

**Intensity is sensor-locked.** DJI L2 intensity ranges 14,000–18,000 for penguin-like detections; TrueView 515 ranges 4,000–6,000. The scales are incompatible — a threshold trained on one sensor would reject all detections from the other.

**Greenness transfers across sensors.** Both DJI L2 and TrueView 515 detections cluster near zero greenness (slightly negative). This is the most portable feature.

**San Lorenzo has wider feature spreads.** All features (intensity, RGB, greenness) show broader distributions at San Lorenzo, consistent with higher false positive contamination in an environment with more diverse ground cover (vegetation, rock, bare soil) compared to the simpler island topography at Caleta.

**Multi-return fraction is low on average but has a non-trivial tail.** TrueView 515 supports multi-return; the median multi-return fraction per detection is 0% and the mean is 0.6%, but 18.4% of detections exceed 1% and the maximum is ~10%. DJI L2 is single-return only. The low central tendency and high zero-inflation make this feature a weak discriminator overall, though the tail warrants investigation after labels are available.

## Parameter Sensitivity

Parameter sweeps were run on representative tiles from both sensors.

### Caleta Tiny Island (DJI L2, cloud0.las)

| Parameter | Range Tested | Detection Count Range | Most Sensitive? |
|-----------|-------------|----------------------|-----------------|
| hag_min | 0.10–0.35 m | 332–357 | No (7% variation) |
| hag_max | 0.35–0.70 m | 108–390 | **Yes** (261% variation) |
| min_area_cells | 1–5 | 347 (constant) | No |
| max_area_cells | 30–100 | 317–349 | No (10% variation) |

The 2D hag_min × hag_max sweep confirms hag_max dominates: count rises steeply from ~8 (tight band) to ~396 (wide band). The sweep baseline (0.20–0.60 m, the legacy golden range) yields 347 detections; the production Argentina parameters use 0.28–0.48 m.

### San Lorenzo Box Count (TrueView 515, box_count_11.9.las)

| Parameter | Range Tested | Detection Count Range | Most Sensitive? |
|-----------|-------------|----------------------|-----------------|
| hag_min | 0.10–0.35 m | 1,027–1,396 | Moderate (36% variation) |
| hag_max | 0.35–0.70 m | 517–1,436 | **Yes** (178% variation) |
| min_area_cells | 1–5 | 1,329 (constant) | No |
| max_area_cells | 30–100 | 1,247–1,331 | No (7% variation) |

San Lorenzo shows the same pattern: hag_max is the dominant parameter. But the overall detection range is much wider (18–1,610 across the full 2D sweep vs 8–396 at Caleta), reflecting the more complex terrain. The hag_min parameter also shows more sensitivity at San Lorenzo (36% vs 7%), suggesting ground model performance differs between sensors or terrain types.

## Feature Ranking

| Feature | Within-site discriminative power | Cross-site transferability | Cross-sensor transferability |
|---------|--------------------------------|---------------------------|------------------------------|
| Intensity (NIR) | Strong | Poor — absolute values site-specific | None — scales incompatible between DJI L2 and TrueView 515 |
| Greenness index | Moderate | Good — consistent near-zero signature | Good — similar distributions across sensors |
| Color warmth (R−B) | Moderate | Unknown — needs more sites | Unknown |
| RGB brightness | Weak | Poor — highly flight-dependent | Poor — sensor-dependent |
| Multi-return fraction | None (DJI L2 single-return) | N/A | Weak — median 0%, mean <1% on TrueView 515; 18% of detections >1% |
| Morphological (HAG, area, shape) | None | N/A — pre-filtered by pipeline | N/A |

## Implications

1. **For the client question "how do we know these are penguins?"** — The feature analysis shows that inside-AOI detections have a remarkably consistent spectral signature (tight intensity, warm RGB, near-zero greenness). This consistency is not guaranteed by the pipeline's geometric filters; it provides supporting evidence that the detections represent a single object class. However, this comparison is between inside-AOI (a TP/FP mix) and outside-AOI (presumed non-penguins) — confirmation that the inside-AOI core consists of true penguins requires manual labeling, which is in progress.

2. **A per-site anomaly detector is feasible.** Flagging detections that are outliers in intensity, greenness, or color could identify likely false positives without labeled training data. This would not replace manual precision auditing, but could prioritize candidates for review.

3. **A cross-site classifier would need normalization.** Raw feature values differ substantially between sites. Relative features (greenness, color ratios) transfer better than absolute values (intensity, brightness).

4. **Return count has limited utility.** The DJI L2 was flown in single-return mode (uninformative). TrueView 515 has multi-return capability, but the median per-detection multi-return fraction is 0% (mean 0.6%). An 18% tail exceeding 1% may correlate with vegetation or other non-penguin features — worth revisiting after labels are available.

## Outputs

- Feature plots: `qc/panels/caleta_tiny_feature_analysis.png`, `qc/panels/caleta_cross_site_features.png`, `qc/panels/cross_sensor_feature_comparison.png`
- Enriched detection JSONs (RGB, intensity, greenness_index; San Lorenzo also includes multi_return_fraction): `data/interim/tiny_best_enriched.json`, `data/interim/caleta_small_enriched.json`, `data/interim/san_lorenzo_box_enriched.json`
- Parameter sweep results: `qc/panels/parameter_sensitivity/` (Caleta Tiny), `qc/panels/parameter_sensitivity_san_lorenzo/` (San Lorenzo)
- Label sample bundles (80 detections each, RGB+HAG crops):
  - `data/processed/label_samples/caleta_tiny_island/`
  - `data/processed/label_samples/caleta_small_island/`

## Resolution and Point Density (February 2026 Experiments)

Resolution sweep experiments confirmed that the current cell sizes are well-matched to sensor point density:

| Sensor | Production Cell | Mean pts/cell | % Empty Cells |
|--------|:---------:|----------:|----------:|
| DJI L2 (Caleta) | 0.25 m | 9.1 | 59% |
| TrueView 515 (San Lorenzo) | 0.30 m | 13.9 | 47% |

Finer resolutions (0.10–0.15 m) produce 1.5–3.3 pts/cell with >60% empty cells, causing noise fragmentation and 5-12x over-detection. The production resolutions provide sufficient density for reliable blob detection while maintaining reasonable grid sizes.

Ground model choice (`min` vs `p05`) has a site-dependent effect: +9.4% detections with `p05` on the open Caleta island, -1.0% on burrow-heavy San Lorenzo terrain. The `min` method remains the default.

Full methodology details: `docs/reports/LIDAR_METHODOLOGY.md` §5.

## Next Steps

1. **Manual labeling** of the 80-sample bundles (Caleta Tiny and Small Islands) using the updated protocol (`docs/process/LABELING_PROTOCOL.md`). This provides the ground truth needed to compute actual precision.
2. **Run `scripts/estimate_precision.py`** after labeling to get Wilson score confidence intervals on precision.
3. **Feature-by-label analysis** after labeling: plot feature distributions for TP vs FP classes to quantify discriminative power and test whether the multi-flag outliers are indeed false positives.
4. **Per-site anomaly scoring** (optional): flag detections >2σ from site mean in intensity or greenness, compare against labels.
