# LiDAR Pipeline: Research + Audit Synthesis (Implementation Checklist)

This document synthesizes the *LiDAR Best Practices* research report with the current repository implementation (primarily `scripts/run_lidar_hag.py`) and flags conflicts/risks. It is intended as a work plan for hardening the LiDAR detection stage for 2025 field data and downstream fusion.

## Status Update (Recent LiDAR Script Hardening)

Recent updates to `scripts/run_lidar_hag.py` (pending merge/rollout) addressed several checklist items:
- CRS-aware GeoJSON flags (`--crs-epsg/--crs-wkt`) + optional WGS84 transform (`--geojson-wgs84`) and output metadata for CRS/units.
- Fixed watershed relabeling write-through bug (removed chained indexing; now clears via a view).
- Added `--top-quantile-lr` and expanded `summary["params"]` to include all CLI args.
- Plot scaling defaults to per-tile; optional global scaling via `--plots-global-scale`, `--plot-sample-n`, `--plot-vmax`.
- Added `--max-grid-mb` pre-allocation estimate to skip oversized tiles; added arg validation and import cleanup.
- GeoJSON/CSV write errors are now surfaced (stderr + output fields) with optional `--strict-outputs`.

This means some previously “confirmed” conflicts (silent output failures, missing CRS metadata) are now **partially or fully mitigated**, but several policy decisions and downstream updates remain.

## Serious Conflicts / Concerns to Resolve

1) **GeoJSON standards vs current outputs (high risk)**
- Research report: GeoJSON should be WGS84 lon/lat (RFC 7946) or you should use a projection-preserving format (GeoPackage/Shapefile).
- Current pipeline (updated): supports CRS-aware output via `--crs-epsg/--crs-wkt`, includes CRS/unit metadata in the output, and can optionally write WGS84 GeoJSON via `--geojson-wgs84`.
- Remaining risk: when CRS is unknown or WGS84 transform is not used, projected-meter coordinates may still be emitted in a `.geojson` file (even if accompanied by metadata). Downstream consumers that ignore metadata can still mis-plot.
- Implication: this is now a **policy/format** decision more than a pure bug: either enforce WGS84 GeoJSON, or prefer GeoPackage for projected CRS deliverables.

2) **“Cross-tile deduplication implemented” is incomplete (output-integrity gap)**
- Research report: recommends deterministic overlap/buffer ownership rules and/or dedupe that yields a final *set* of detections.
- Status (updated): `--dedupe-radius-m` now emits `lidar_hag_detections_deduped.csv` and `lidar_hag_detections_deduped.json`, plus a `dedupe_index` mapping original IDs → kept ID/cluster.
- Remaining gap: tile overlap/buffer “ownership” policy is still not explicit; dedupe is centroid-distance based and should be documented as such.

3) **Determinism claims need nuance (chunking + online quantiles)**
- Research report: stresses exact reproducibility across re-runs (sorted outputs, stable IDs, guardrail tests, version pinning).
- Current pipeline: default `top_method=p95` uses an online quantile estimator which can be sensitive to chunking/ordering; a new `--top-quantile-lr` makes this explicit/configurable.
- Implication: treat `p95` as “approximate” unless proven stable across the 2025 datasets and environments.

4) **Ground model robustness is likely the largest scientific failure mode**
- Research report: highest priority is a robust DTM/ground filter (CSF/progressive filters; at minimum use low percentiles vs min).
- Current pipeline: default ground method is `min` (`scripts/run_lidar_hag.py:229`), with a `p05` option but no robust ground classifier.
- Implication: a biased ground surface can suppress HAG (false negatives) or create artificial HAG (false positives), especially in dense colonies and rocky terrain.

5) **Downstream consumers must handle WGS84 vs projected outputs**
- `scripts/create_detection_map.py` currently assumes projected GeoJSON (default `EPSG:32720`) and transforms to WGS84 for Folium basemaps.
- If `--geojson-wgs84` is used, the map script must be invoked with `--source-crs EPSG:4326` or updated to read CRS metadata from the new GeoJSON output.

## Decision Log (Pick policies explicitly)

These decisions affect compatibility, outputs, and scientific defensibility. Record the chosen policy in `RUNBOOK.md` and implement as CLI defaults or site profiles.

1) **CRS + geospatial output policy**
- Preferred for fusion/engineering: projected CRS (meters) as canonical.
- Preferred for “web/lightweight”: optional WGS84 deliverable.
- Decide:
  - A) Replace GeoJSON with GeoPackage (GPKG) as the default GIS artifact (stores CRS and attributes).
  - B) If keeping GeoJSON: either (i) transform to EPSG:4326, or (ii) change extension/naming and embed explicit projected CRS metadata to avoid misinterpretation.
  - C) Define how CRS is sourced: read LAS VLR/WKT when available, else require `--crs-epsg/--crs-wkt`, else fail fast (recommended) or emit outputs with an explicit “CRS unknown” marker + warnings (not recommended for production).

2) **Determinism policy for “top surface” estimator**
- Decide:
  - A) Default to deterministic `--top-method max` (and treat `p95` as opt-in), or
  - B) Keep `p95` default for continuity but explicitly document it as approximate and make stability a tested contract across representative 2025 datasets (and expose learning-rate parameters).

3) **Watershed default policy**
- Decide:
  - A) enable by default for dense-colony profiles only (recommended), or
  - B) enable by default globally, with conservative tuning to avoid over-splitting.

4) **Ground filtering policy**
- Decide:
  - A) keep “simple” min/p05 mode for field-only runs but add a “robust ground” mode (PDAL CSF) for production processing, or
  - B) flip default to p05 and add a roadmap to CSF when dependencies are available.

## Implementation Checklist (ordered by impact)

### P0 — Output Integrity + CRS Discipline (do first)

1) **Make geospatial artifacts self-describing**
- Status: partial. GeoJSON now supports explicit CRS metadata and optional WGS84 transform, but projected `.geojson` remains a standards footgun.
- Next: implement a projection-preserving output option (GeoPackage strongly preferred) and/or enforce WGS84 when extension is `.geojson`.
- Acceptance:
  - Every detection file includes CRS metadata in a machine-readable way (file format supports it, or a sidecar file is written).
  - `summary["crs"]` is set when known (and never silently omitted for known-site runs).

2) **Fail loudly (or at least log) when requested outputs are not written**
- Status: implemented in the updated script (stderr warnings + output error fields; optional `--strict-outputs`).
- Acceptance:
  - If `--emit-geojson` or `--emit-csv` is set and writing fails, the run result explicitly indicates failure.

3) **Make dedupe operational, not just a number**
- Status: implemented (batch `lidar_hag_detections_deduped.{csv,json}` + `dedupe_index`).
- Next: document the centroid-distance clustering semantics and consider adding a projection-preserving GIS output (GeoPackage) for deduped artifacts.
- Acceptance:
  - `--dedupe-radius-m` produces a deduped output artifact and the count matches that artifact.

### P0 — Determinism Contracts (do first)

4) **Stable ordering + stable IDs**
- Ensure detections are sorted deterministically per tile (e.g., by x/y/area) and assign a stable ID:
  - `tile_id + rank`, or
  - hash of quantized coordinates + tile.
- Status: per-tile detections are now sorted deterministically and assigned `id`, `tile`, and `file` fields.
- Acceptance:
  - Re-running a tile produces the same detection order and IDs.
  - Golden AOI signature remains stable; add additional signatures for representative 2025 tiles.

5) **Explicitly define whether `p95` is allowed to drift**
- Status: `--top-quantile-lr` is implemented; remaining work is policy + tests (vary `--chunk-size` and confirm acceptable invariance).
- If switching default to `max`: update baselines and document rationale (determinism > robustness).
- Acceptance:
  - A documented determinism policy exists (including “what can drift”).
  - Tests cover the chosen policy.

6) **Dependency version pinning for field deployments**
- Ensure field runs use pinned versions (`requirements.txt` already constrains, but may need tighter pinning for numpy/scipy/skimage if drift is observed).
- Acceptance:
  - `RUNBOOK.md` documents the supported Python + package versions used for baselines.

### P1 — Ground Model Improvements (high scientific impact)

7) **Flip ground default or add robust ground mode**
- Short-term: consider making `--ground-method p05` the default for 2025 runs if it reduces outlier sensitivity.
- Medium-term: add a robust ground extraction option:
  - PDAL `filters.csf` (if available in full environment), or
  - progressive morphological filtering / TIN densification approach.
- Acceptance:
  - Ground method is explicitly recorded in outputs.
  - A small validation set shows reduced bias (e.g., HAG histogram stability and fewer missed detections in dense clusters).

8) **Add a grid-size/memory guardrail**
- Status: `--max-grid-mb` is implemented (skips tiles exceeding estimate); decide whether production runs should “skip” or “fail fast”.
- Acceptance:
  - Runs fail fast with an actionable message suggesting larger `--cell-res` or tiling.

### P1 — Instance Separation + Dense-Colony Handling

9) **Make watershed marker-controlled and tuneable**
- Current approach uses `h_maxima` markers + watershed for large blobs; validate marker distance / h-depth rules as described in the report.
- Add an explicit “valley depth” split rule if needed to prevent over-segmentation in noisy HAG.
- Acceptance:
  - Dense-colony tiles show improved counts without obvious over-splitting.
  - QC artifacts make merges/splits auditable.

10) **Support “declustering” / over-split detection**
- Post-process very-close centroids (e.g., < 0.15 m) as possible over-splits; either merge or flag.
- Acceptance:
  - Provides a flag/score for uncertain splits and does not silently change counts without traceability.

### P2 — QA/QC Artifact Expansion (for field trust + debugging)

11) **Add histograms and distribution summaries**
- Emit per-tile histograms for:
  - HAG values, blob area distribution, optional height stats.
- Acceptance:
  - Histograms are generated for `--plots` mode and reference the same params as the run.

12) **Add spatial density heatmaps**
- Produce a coarse detection-density raster/PNG (e.g., detections per 5 m cell) to highlight colony clusters and outliers.
- Acceptance:
  - Generated artifacts are consistent and fast enough for field use.

13) **Multi-panel “report card” per tile**
- Recommended panels: DTM, HAG, threshold mask, outlines, final detections overlay.
- Acceptance:
  - Single artifact per tile supports rapid human scanning.

### P2 — Resolution + Parameter Profiling (site/sensor configuration)

14) **Evaluate smaller `--cell-res` profiles**
- Research suggests 5–10 cm where point density supports it; evaluate 0.10 m on representative 2025 tiles (mind memory).
- Acceptance:
  - Documented tradeoff (runtime, memory, accuracy) and a recommended profile per sensor/site.

15) **Formalize site/sensor profiles**
- Create a small config layer (e.g., per-site JSON/YAML) that locks parameters for each site after calibration (avoid ad-hoc CLI tuning).
- Acceptance:
  - Profiles are versioned, documented, and referenced in provenance.

## Validation + Monitoring Checklist (2025 readiness)

1) **Stratified manual sampling plan**
- Define strata: dense colony, sparse edge, rocky terrain, sloped terrain.
- Produce a checklist for reviewers and a format for recording TP/FP/FN.

2) **Precision/recall computation**
- Add scripts/notebooks to compute precision/recall from verified samples; track per site/sensor.

3) **Performance tracking log**
- Maintain a table: field count vs LiDAR count vs delta, plus sample-based precision/recall and key run signatures.

## Notes on Claims in the “Summary” Table

- “Deterministic output ✅”: deterministic file ordering is necessary but not sufficient; online quantiles and tile-edge effects must be explicitly covered by tests and policies.
- “Cross-tile deduplication ✅”: currently only a derived count exists; outputs are not deduped and cannot be used directly for fusion without further work.
- “UTM CRS ✅ EPSG:32720”: this may be a *site default* but not universally safe; mixed CRS across sensors/sites must be handled explicitly and recorded per dataset.
