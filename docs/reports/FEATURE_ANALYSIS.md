# LiDAR Detection Feature Analysis

Date: 2026-02-02

## Purpose

Assess whether LiDAR point cloud features beyond geometric filtering can discriminate penguins from false positives. The pipeline currently accepts detections based on height (0.28–0.48 m HAG) and size (0.19–3.75 m²) only. This analysis tests whether RGB color, NIR intensity, and derived indices add discriminative signal.

## Method

Per-detection features were extracted from a 0.5 m radius around each detection centroid by streaming the source LAS files. Features computed: mean RGB (16-bit), mean intensity (905 nm NIR), and derived indices (greenness, brightness, color warmth). Analysis was performed on two Caleta island sites where AOI boundaries are well-defined.

The primary comparison is inside-AOI vs outside-AOI detections. Inside-AOI detections are a mix of true penguins and false positives; outside-AOI detections (off-island) are almost certainly non-penguins (water, rocks, edge artifacts). Both sites use DJI L2 LiDAR with onboard 20 MP RGB camera.

## Data

| Site | Inside AOI | Outside AOI | Sensor |
|------|-----------|-------------|--------|
| Caleta Tiny Island | 315 | 25 | DJI L2 |
| Caleta Small Island | 1,473 | 0 | DJI L2 |

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

## Feature Ranking

| Feature | Within-site discriminative power | Cross-site transferability |
|---------|--------------------------------|---------------------------|
| Intensity (NIR) | Strong | Poor — absolute values site-specific |
| Greenness index | Moderate | Good — consistent near-zero signature |
| Color warmth (R−B) | Moderate | Unknown — needs more sites |
| RGB brightness | Weak | Poor — highly flight-dependent |
| Morphological (HAG, area, shape) | None | N/A — pre-filtered by pipeline |

## Implications

1. **For the client question "how do we know these are penguins?"** — The feature analysis shows that inside-AOI detections have a remarkably consistent spectral signature (tight intensity, warm RGB, near-zero greenness). This consistency is not guaranteed by the pipeline's geometric filters; it provides independent evidence that the detections represent a single object class.

2. **A per-site anomaly detector is feasible.** Flagging detections that are outliers in intensity, greenness, or color could identify likely false positives without labeled training data. This would not replace manual precision auditing, but could prioritize candidates for review.

3. **A cross-site classifier would need normalization.** Raw feature values differ substantially between sites. Relative features (greenness, color ratios) transfer better than absolute values (intensity, brightness).

4. **Return count is not useful.** The DJI L2 was flown in single-return mode — all detections have single_return_fraction = 1.0. This feature is uninformative for this dataset.

## Outputs

- Feature plots: `qc/panels/caleta_tiny_feature_analysis.png`, `qc/panels/caleta_cross_site_features.png`
- Enriched detection JSONs: `data/interim/tiny_best_enriched.json`, `data/interim/caleta_small_enriched.json`
- Label sample bundle (80 detections, RGB+HAG crops): `data/processed/label_samples/caleta_tiny_island/`

## Next Steps

1. **Manual labeling** of the 80-sample bundle (Caleta Tiny Island) using the updated protocol (`docs/process/LABELING_PROTOCOL.md`). This provides the ground truth needed to compute actual precision.
2. **Feature-by-label analysis** after labeling: plot feature distributions for TP vs FP classes to quantify discriminative power and test whether the multi-flag outliers are indeed false positives.
3. **Per-site anomaly scoring** (optional): flag detections >2σ from site mean in intensity or greenness, compare against labels.
