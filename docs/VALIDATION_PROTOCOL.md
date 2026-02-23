# Validation Protocol (Subset QA + Stratified Audit)

## Scope Statement

This protocol separates two activities:

- **Subset QA metrics**: TP/FP/FN precision/recall on labeled subsets only.
- **Stratified manual audit**: defensible precision estimation when exhaustive labels are unavailable.

Subset QA results are **not** site-wide accuracy and **not** a full census.

## 1) Subset QA (Existing Labeled Plot)

Use `scripts/validate_lidar_labeled_subset.py` against the labeled plot only.

Required reporting language:

- "Evaluation subset: labeled plot only."
- "Not representative of full-site recall without exhaustive labels."
- "Matching radius sensitivity was evaluated; see per-radius metrics."

Minimum outputs:

- `metrics_summary_table` by radius (`tp`, `fp`, `fn`, `precision`, `recall`, `f1`)
- `radius_sensitivity_note`

## 2) Stratified Manual Audit Template

When labels are sparse, estimate precision with stratified review.

### Strata Definition

Define strata before sampling (example set):

1. Terrain context: open ground, burrow-dense, mixed vegetation.
2. Candidate confidence bin: high (`>=0.8`), medium (`0.5-0.8`), low (`<0.5`).
3. Scan quality proxy: high density vs low density tiles.

Document exact field names and thresholds used for each stratum.

### Sampling Plan

1. Sample without replacement within each stratum.
2. Target minimum `n >= 30` candidates per stratum where possible.
3. If a stratum has fewer than 30 candidates, audit all of them.
4. Record audited IDs and random seed in a manifest.

### Reviewer Rubric

Each sampled candidate must be labeled by a reviewer as one of:

- `true_penguin`
- `false_positive_burrow`
- `false_positive_rock`
- `false_positive_shadow_or_void`
- `uncertain`

Record reviewer ID, timestamp, and evidence panel path for each decision.

### Aggregation

For each stratum:

- Precision = `true_penguin / (true_penguin + false_positive_*)`
- Report Wilson 95% CI.

Aggregate overall precision using stratum-weighted mean:

- Weight = `stratum_candidate_count / total_candidate_count`.

Report:

- Per-stratum precision + CI
- Weighted overall precision + CI
- `uncertain` rate

## 3) Deliverable Checklist

- Subset QA JSON with per-radius table + sensitivity note
- Stratified audit sample manifest
- Reviewer labels CSV/GeoJSON
- Precision report with stratified + weighted estimates and confidence intervals
