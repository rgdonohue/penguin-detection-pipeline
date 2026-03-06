# Thermal Analyst Meeting Brief (2026-03-06)

Purpose: fast reference for today’s thermal meeting with clear technical position, GIS/remote-sensing context, and direct code + artifact receipts.

## 1) Meeting TL;DR

- We have built a full LiDAR detection system, not just "HAG + intensity".
- The stack includes ground/top modeling options, morphology + shape filtering, watershed splitting, slope gating, dedupe, confidence scoring, AOI gating, and reproducibility controls.
- For the new Box2 package, we can extract labels and do coarse spatial cross-reference now, but defensible per-label georeferencing is blocked by missing referenced raw frames.
- AOI geometry authority is still a major validation risk; blocked AOIs are intentionally enforced in official mode.

## 2) What Is Implemented (with GIS/RS context, code links, and receipts)

| Capability | GIS/Remote Sensing explanation | Code receipts | Output receipts |
|---|---|---|---|
| Ground surface modeling (`min`/`p05`/`csf`) | In LiDAR, object height only makes sense after normalizing against terrain. Ground DEM quality directly controls HAG quality. | [`run_lidar_hag.py`](../../scripts/run_lidar_hag.py) (`--ground-method`, CSF + fallback; around lines 829, 1866-1901, 2489+) | [`data/interim/ground_model_comparison_caleta.json`](../../data/interim/ground_model_comparison_caleta.json), [`data/interim/ground_model_comparison_san_lorenzo.json`](../../data/interim/ground_model_comparison_san_lorenzo.json) |
| Top surface modeling (`max`/`p95` variants) | Top-of-canopy/target surface estimate determines the upper part of HAG. Different top estimators change sensitivity to spikes/noise. | [`run_lidar_hag.py`](../../scripts/run_lidar_hag.py) (`--top-method`; branches around lines 1904-1932, CLI around 2506+) | Summary JSON contains effective method + counts, e.g. [`data/interim/san_lorenzo_full.json`](../../data/interim/san_lorenzo_full.json); detection-rate tracking in [`DETECTION_RATE_SUMMARY.md`](./DETECTION_RATE_SUMMARY.md) |
| HAG threshold + morphology + shape filtering | Rasterized HAG is treated like an image; thresholding and morphology remove speckle, connected-components isolate targets, shape filters suppress non-penguin blobs. | [`run_lidar_hag.py`](../../scripts/run_lidar_hag.py) (`detect_penguins_from_hag`, lines ~1430-1610; CLI thresholds around 2530-2626) | QC and detections: [`data/interim/lidar_hag_plots`](../../data/interim/lidar_hag_plots), [`data/interim/lidar_hag_detections.csv`](../../data/interim/lidar_hag_detections.csv) |
| Terrain slope gating | Steep terrain often creates geometric false positives; slope gating masks implausible detections on cliffs/walls. | [`run_lidar_hag.py`](../../scripts/run_lidar_hag.py) (slope grid + rejection around 1987-1993 and 1585-1591; CLI `--slope-max-deg`) | Code path is implemented and parameterized; use a run summary with non-null `params.slope_max_deg` as the execution receipt rather than [`data/interim/san_lorenzo_full.json`](../../data/interim/san_lorenzo_full.json), which was not slope-gated |
| Watershed split for merged blobs | Nearby individuals can merge in raster space; watershed uses local peaks to split likely merged components. | [`run_lidar_hag.py`](../../scripts/run_lidar_hag.py) (watershed logic around 1467-1556; stats around 2193-2217), [`watershed_sweep.py`](../../scripts/experiments/watershed_sweep.py) | [`data/interim/watershed_sweep_caleta_tiny.json`](../../data/interim/watershed_sweep_caleta_tiny.json), optional `watershed` section in run summaries |
| Intensity and feature enrichment | Radiometric/intensity and per-blob features add discriminative signal beyond geometry alone. | [`run_lidar_hag.py`](../../scripts/run_lidar_hag.py) (`--extract-intensity`, enrichment pass around 1994-2055) | Enriched detections include intensity-derived fields; current receipt [`data/interim/caleta_small_enriched.json`](../../data/interim/caleta_small_enriched.json) shows `intensity_mean` and companion blob features |
| Confidence scoring | Confidence combines height, area, and shape plausibility into a 0-1 score for triage and stratified auditing. | [`run_lidar_hag.py`](../../scripts/run_lidar_hag.py) (`compute_confidence_scores` around 555-603; call around 2075-2077; CLI `--compute-confidence`) | Detections contain `confidence`, `confidence_hag`, `confidence_area`, `confidence_shape` in run outputs |
| Cross-tile dedupe + official count basis | Seam overlap can double-count objects; dedupe clusters nearby centroids, then official mode reports deduped counts with audit trail. | [`run_lidar_hag.py`](../../scripts/run_lidar_hag.py) (`_dedupe_detections` around 635+, official mode around 2568+, dedupe outputs around 3148-3215, reporting counts around 3264-3279) | [`data/interim/lidar_hag_detections_deduped.csv`](../../data/interim/lidar_hag_detections_deduped.csv), [`data/interim/lidar_hag_detections_deduped.json`](../../data/interim/lidar_hag_detections_deduped.json), per-run manifest at `<out_dir>/lidar_run_manifest.json` |
| AOI authority + gating | AOI polygons are part of measurement definition; wrong geometry means wrong counts. Official mode blocks known bad AOIs. | [`run_lidar_hag.py`](../../scripts/run_lidar_hag.py) (AOI registry checks around 2796-2816, blocked/degraded handling around 2901-2916), [`aoi_registry.json`](../../manifests/aoi_registry.json) | Blocked entries: `san_lorenzo_box_bushes`, `sl_box_bushes`; policy in [`BLOCKED_AOIS.md`](../process/BLOCKED_AOIS.md) |
| AOI-clipped evaluation + subset QA | In GIS terms, this is spatial filtering + point matching in projected CRS; useful for QA, but not full-census truth unless labels are exhaustive. | [`evaluate_lidar_aoi.py`](../../scripts/evaluate_lidar_aoi.py), [`validate_lidar_labeled_subset.py`](../../scripts/validate_lidar_labeled_subset.py) (metrics and radius sensitivity around 319-387, 552-561) | [`data/processed/san_lorenzo_aoi_eval.json`](../../data/processed/san_lorenzo_aoi_eval.json), [`data/interim/validation`](../../data/interim/validation), protocol: [`VALIDATION_PROTOCOL.md`](../VALIDATION_PROTOCOL.md) |
| DTM/DSM export + thermal ortho support | LiDAR terrain/surface rasters provide the elevation reference needed to orthorectify thermal imagery into map space. | [`export_dtm.py`](../../scripts/export_dtm.py), [`run_thermal_ortho.py`](../../scripts/run_thermal_ortho.py) (`ortho-one`, `verify-grid`, `boresight`) | [`data/processed/san_lorenzo_full_dtm.tif`](../../data/processed/san_lorenzo_full_dtm.tif), [`data/processed/san_lorenzo_full_dsm.tif`](../../data/processed/san_lorenzo_full_dsm.tif); current repo also contains thermal processing outputs under [`data/processed/thermal`](../../data/processed/thermal), but checked-in ortho GeoTIFF examples are not present |

## 3) Techniques We Ran and What They Tell Us

- Resolution sensitivity: [`resolution_sweep.py`](../../scripts/experiments/resolution_sweep.py) with receipts in [`data/interim/resolution_sweep_caleta.json`](../../data/interim/resolution_sweep_caleta.json) and [`data/interim/resolution_sweep_san_lorenzo.json`](../../data/interim/resolution_sweep_san_lorenzo.json).
- Parameter sensitivity: [`lidar_parameter_sweep.py`](../../scripts/lidar_parameter_sweep.py).
- Ground-model comparison: receipts in [`data/interim/ground_model_comparison_caleta.json`](../../data/interim/ground_model_comparison_caleta.json) and [`data/interim/ground_model_comparison_san_lorenzo.json`](../../data/interim/ground_model_comparison_san_lorenzo.json).
- HAG distribution analysis: [`data/interim/hag_histogram_caleta.json`](../../data/interim/hag_histogram_caleta.json), [`data/interim/hag_histogram_san_lorenzo.json`](../../data/interim/hag_histogram_san_lorenzo.json).
- Watershed sweep: [`data/interim/watershed_sweep_caleta_tiny.json`](../../data/interim/watershed_sweep_caleta_tiny.json).

Reference syntheses:
- [`LIDAR_METHODOLOGY.md`](./LIDAR_METHODOLOGY.md)
- [`LIDAR_VALIDATION.md`](./LIDAR_VALIDATION.md)
- [`DETECTION_RATE_SUMMARY.md`](./DETECTION_RATE_SUMMARY.md)

## 4) Current Box2 Thermal Label Status (This Week)

### What we have now
- Extracted PDF labels to structured CSV using [`extract_lydia_pdf_labels.py`](../../scripts/extract_lydia_pdf_labels.py).
- Class totals extracted: 122 points (`48` Penguin in Burrow, `11` Penguin Deep in Burrow, `63` Empty Burrow).
- Receipts:
  - [`data/interim/lydia_box2/labels_extracted_meta.csv`](../../data/interim/lydia_box2/labels_extracted_meta.csv)
  - [`data/interim/lydia_box2/labels_extracted_legacy.csv`](../../data/interim/lydia_box2/labels_extracted_legacy.csv)
  - [`data/interim/lydia_box2/README.md`](../../data/interim/lydia_box2/README.md)

### What is blocked
- Per-label georeferencing is currently not defensible because the annotation PDF references raw IDs not present in the delivered set/repo (example: `...0064_T`).
- Implemented coarse fallback (RTK center + estimated footprint) in [`crossref_lydia_box2_to_lidar.py`](../../scripts/crossref_lydia_box2_to_lidar.py) with explicit notes in code.
- Receipts:
  - [`data/interim/lydia_box2/spatial_crossref_summary.md`](../../data/interim/lydia_box2/spatial_crossref_summary.md)
  - [`data/interim/lydia_box2/spatial_crossref_report.json`](../../data/interim/lydia_box2/spatial_crossref_report.json)

### Practical interpretation for meeting
- We can script georeferencing internally; there is no visible hard dependency on OpenAthena tooling in this repo.
- We already have reusable georeferencing and validation components in the repo, but the Box2 path is not yet wired into a single end-to-end harness.
- Current blocker is dataset traceability/completeness, not missing engineering capability.

## 5) AOI Validation Roadblocks (Current Position)

1. AOI authority is the main risk to defensible reporting.
- Bushes AOI is formally blocked in registry pending authoritative client geometry.
- Receipts: [`manifests/aoi_registry.json`](../../manifests/aoi_registry.json), [`BLOCKED_AOIS.md`](../process/BLOCKED_AOIS.md).

2. Approximate AOIs can distort ratios.
- Waypoint-derived polygons may not match true sampled extents, which changes AOI-clipped counts directly.
- Receipts: [`LIDAR_VALIDATION.md`](./LIDAR_VALIDATION.md), [`san_lorenzo_aoi_eval.json`](../../data/processed/san_lorenzo_aoi_eval.json).

3. Subset QA scope must stay explicit.
- Labeled-subset precision/recall is valid QA, not full-site census truth without exhaustive labels.
- Receipt/policy: [`VALIDATION_PROTOCOL.md`](../VALIDATION_PROTOCOL.md).

## 6) Pending requests

1. Establish or provide the missing raw thermal frames referenced by the annotation sequence (notably `...0064_T`).
2. Establish or provide authoritative AOI polygon(s) for blocked/uncertain zones with explicit CRS metadata.
3. If available, provide original raw-frame label export (`image_filename`, `x`, `y`, `class`) instead of screenshot/PDF overlay coordinates.

If those are provided, we can complete defensible per-label georeferencing and then run AOI-clipped LiDAR-vs-thermal validation using the repo's existing georeferencing, subset-QA, and (eventually) fusion components.
