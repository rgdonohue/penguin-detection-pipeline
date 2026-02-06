# Project Status — Honest Assessment

Last updated: 2026-02-02 UTC

**Current focus:** Argentina 2025 **LiDAR processing + AOI verification** (client deliverables). Thermal and fusion work is **paused** (research-only) pending calibration/georeferencing.

---

## ✅ What Actually Works

### 1. LiDAR Detection Pipeline
**Status:** RUNS SUCCESSFULLY; VALIDATION IN PROGRESS (FEATURE ANALYSIS COMPLETE, MANUAL LABELING IN PROGRESS)

- **Script:** `scripts/run_lidar_hag.py` (620+ lines, streaming architecture)
- **Dependencies:** `pipelines/utils/provenance.py`, laspy, scipy, scikit-image
- **Golden AOI baseline:** 776 candidates on cloud3.las (guardrail test, `--top-method max`)
- **Outputs:** JSON, GeoJSON, QC plots, provenance tracking
- **Makefile target:** `make test-lidar`

**Argentina Data Processed (2025-12-21):**
- 24 LiDAR files catalogued
- 754M points total (100% processed)
- 25.8 GB across DJI L2 and TrueView 515 sensors

**Validation Progress (2026-02-02):**
- AOI-clipped evaluation complete for Caleta sites (341 total at Tiny Island with `--top-method max --skip-copc`; 1,255/1,473 at Small Island)
- Per-detection feature extraction done for 3 sites (Caleta Tiny, Caleta Small, San Lorenzo box count) — RGB, intensity, greenness, morphological features
- Cross-sensor comparison (DJI L2 vs TrueView 515): intensity scales incompatible; greenness index transfers across sensors
- Parameter sweep on 2 tiles: hag_max is dominant sensitivity parameter at both sites
- 86% of Caleta Tiny inside-AOI detections form tight spectral core (consistent with high precision)
- **Label sample bundles generated** for Caleta Tiny Island (80 samples) and Caleta Small Island (80 samples) with RGB+HAG dual-panel crops
- **Manual labeling in progress** — precision estimation via `scripts/estimate_precision.py` will follow
- See `docs/reports/FEATURE_ANALYSIS.md` for full analysis

**VALIDATION CAVEATS (see `docs/reports/LIDAR_ASSESSMENT_2025-12-21.md`):**
- Previous "+6% / +1% error" claims were based on box count comparisons where tile extents ≠ counted areas
- Top-surface estimator (`p95`) is an approximate streaming quantile sensitive to order/chunking
- Detection semantics are now explicitly encoded as **candidates (blob centroids), not guaranteed individuals** (see `pipelines/contracts.py`)
- AOI-clipped precision pending manual labeling (label samples generated, labeling in progress)

### 2. Foundation Infrastructure
**Status:** WORKING

- **Legacy data mounts:** Read-only symlinks to 4 projects ✅
- **Directory structure:** scripts/, pipelines/, data/, manifests/, tests/ ✅
- **Environment spec:** `requirements.txt` (Python 3.12.x baseline) ✅
- **Makefile:** Working targets for env, test, test-lidar, clean ✅

**Test Suite (core):**
- `tests/test_golden_aoi.py` ✅ (guardrail baseline: 776)
- `tests/test_lidar_dem_hag_unit.py` ✅
- `tests/test_thermal.py` ✅ (GDAL-dependent tests may skip)
- `tests/test_thermal_radiometric.py` ✅ (data-dependent tests may skip)
- `tests/test_data_2025_invariants.py` ✅
- `tests/test_end_to_end_contract_qc.py` ✅ (schema/CRS contract harness; synthetic fixtures)

### 3. Thermal Extraction Infrastructure
**Status:** INFRASTRUCTURE COMPLETE, CALIBRATION UNRESOLVED

- **Script:** `scripts/run_thermal_ortho.py` with `--radiometric` flag ✅
- **Core library:** `pipelines/thermal.py` with `extract_thermal_data()` ✅
- **16-bit extraction:** Working — extracts ThermalData blob, outputs float32 Celsius ✅
- **Supported sensors:** H20T (640×512), H30T (1280×1024) ✅
- **Test suite:** `tests/test_thermal_radiometric.py` — 5/5 passing ✅

**CALIBRATION ISSUES (unresolved):**

| Issue | Description | Source |
|-------|-------------|--------|
| Ambient offset (~9°C) | Metadata ambient 21°C vs computed max 12.16°C | `thermal_extraction_progress.md:91-105` |
| Biological offset (~30°C) | Expected penguin temps 25-30°C vs observed ~-5°C | `RADIOMETRIC_INTEGRATION.md:62-76` |

**Scale Heuristics:** Sensor profiles are centralized in `THERMAL_SENSOR_PROFILES` in `pipelines/thermal.py`.

### 4. Argentina Data Integration
**Status:** PARTIALLY COMPLETE

- **LiDAR catalogue:** ✅ 24 files, 754M points, 25.8 GB documented
- **Sensor tuning:** ✅ DJI L2 and TrueView 515 parameters validated
- **GPS waypoints:** 45 boundary/route waypoints extracted to `data/processed/san_lorenzo_waypoints.csv`
- **Ground truth counts:** ~3,705 penguins documented across sites (in `san_lorenzo_analysis.json`)

**IMPORTANT:** The 3,705 figure is total penguin COUNT, not georeferenced locations. GPS→pixel projection has NOT been implemented.

---

## ❌ What Doesn't Work

### 1. Fusion Pipeline
**Status:** PARTIALLY COMPLETE

- ✅ `pipelines/fusion.py` implements a nearest-neighbor spatial join (KD-tree) between LiDAR and thermal detections.
- ⚠️ Fusion currently assumes both inputs already contain `x`/`y` in the same projected CRS (meters). It does **not** georeference thermal pixel detections.
- ✅ `pipelines/golden.py` is now a QC harness wrapper over `tests/test_golden_aoi.py` (use `make golden`).

### 2. Ground Truth Annotation
**Status:** 44% COMPLETE (legacy), LABELING IN PROGRESS (Argentina)

**Legacy (Punta Tombo):**
- Completed: 60 penguins across 3 frames (0353, 0355, 0356)
- Remaining: 77 penguins across 4 frames (0354, 0357, 0358, 0359)
- CSVs in `verification_images/`

**Argentina:**
- GPS waypoints extracted but NOT projected to pixel coordinates
- No per-image ground truth CSVs exist yet
- **Label sample bundles generated** for precision estimation:
  - Caleta Tiny Island: 80 stratified samples with RGB+HAG crops (`data/processed/label_samples/caleta_tiny_island/`)
  - Caleta Small Island: 80 stratified samples with RGB+HAG crops (`data/processed/label_samples/caleta_small_island/`)
- Manual labeling in progress using `docs/process/LABELING_PROTOCOL.md`

### 3. Thermal Detection
**Status:** RESEARCH PHASE — DISCRIMINATION POC NEGATIVE

- F1 scores: 0.02-0.30 depending on frame contrast
- **Thermal discrimination proof of concept (2026-02-02):** Tested whether relative thermal brightness (without absolute calibration) can separate penguins from empty burrows at the San Lorenzo Bushes box count site. Used direct pixel sampling from 4 labeled H30T thermal images (111 labels across 3 categories, all at -45° oblique pitch).
  - **Result: negligible discrimination.** Cohen's d = 0.035 (penguin vs empty burrow), d = 0.22 (shallow penguin vs empty burrow). Empty burrows are also warmer than background (+0.37°C), confounding the signal.
  - **Shallow penguins** ("Penguin in Burrow"): +0.6°C above background, but std 1.2°C — not individually reliable
  - **Deep penguins** ("Penguin Deep in Burrow"): +0.13°C, indistinguishable from background
  - **Physical reason:** At 45° oblique pitch, the camera sees burrow rims and openings, not penguin bodies. Thermal signature is dominated by cavity geometry.
  - **LiDAR-thermal fusion test:** LiDAR detections projected into thermal frames show no enrichment for warm pixels (Cohen's d = -0.17 vs unmatched). Top 10% hottest LiDAR detections contain 0 penguin-matched points.
  - Full results: `data/interim/thermal_discrimination_poc.json`
- **Implication:** Thermal fusion is not viable at oblique-view burrow sites. Nadir thermal views or open-colony sites (standing penguins on rock) might show stronger signal — untested.
- Calibration must be resolved before any production thermal use

---

## 📊 Component Maturity Summary

| Component | Status | Confidence | Blocker |
|-----------|--------|------------|---------|
| LiDAR Detection | Runs, AOI-clipped, features extracted | Medium-High | Precision pending manual labeling |
| LiDAR Feature Analysis | Complete (3 sites, 2 sensors) | High | None |
| LiDAR Label Samples | Generated (2 × 80 samples) | High | Manual labeling in progress |
| LiDAR Tests | Passing | High | None |
| Thermal Extraction | Working | Medium | Calibration offset |
| Thermal Detection | Research (POC negative) | Low | Oblique views lack discrimination; F1 < 0.1 |
| Thermal Tests | Passing | Medium | Data/GDAL availability |
| Thermal Discrimination POC | Complete (negative) | High | Oblique views at burrow sites do not discriminate |
| Fusion | Partial | Medium | Thermal detections need CRS `x/y`; discrimination POC negative |
| Ground Truth (legacy) | 44% | Medium | Manual annotation needed |
| Ground Truth (Argentina) | Thermal labels georeferenced | Medium | LiDAR cross-ref done; 43% recall at 2m |

---

## 🎯 Critical Path

## ✅ Readiness Framing (QC vs Scientific)

This repo tracks two kinds of progress:

- **QC / Engineering readiness:** deterministic, CRS-aware artifacts that let us validate geometry and pipeline contracts.
- **Scientific / Field-valid readiness:** calibration + validation that makes thermal-derived counts trustworthy.

Policy: `docs/process/WORKSTREAMS_QC_VS_SCIENCE.md`

### Completed (this sprint)

1. ~~**Define detection semantics**~~ — ✅ Done (`pipelines/contracts.py`): candidates (blob centroids), not guaranteed individuals
2. ~~**Implement AOI-clipped evaluation**~~ — ✅ Done (`pipelines/aoi_eval.py`): Caleta Small 1255/1473; Caleta Tiny AOI eval pending re-run with `--top-method max`
3. ~~**Lock top-surface estimator**~~ — ✅ Using `max` (deterministic) for all validation work
4. ~~**Feature analysis**~~ — ✅ Done: RGB, intensity, greenness, morphological for 3 sites across 2 sensors
5. ~~**Label sample generation**~~ — ✅ Done: 80-sample bundles for Caleta Tiny + Caleta Small with RGB+HAG crops

6. ~~**Top-method bug fix**~~ — ✅ Done: CLI default changed from `p95` to `max`; golden baseline updated 802→776; Caleta Tiny 341 total with `--top-method max --skip-copc` (vs 321 field = 1.06 ratio). Previous "317" claim not reproducible.
7. ~~**Pipeline experiments**~~ — ✅ Done (Feb 2026): resolution sweep, ground model comparison, HAG histogram, watershed sweep on 2 sensors/sites. See `docs/reports/LIDAR_METHODOLOGY.md` §5.
8. ~~**Thermal discrimination POC**~~ — ✅ Done (negative result): oblique thermal at burrow sites does not discriminate penguins from empty burrows

### Immediate (in progress)

9. **Manual labeling** of label sample bundles → precision estimation via `scripts/estimate_precision.py`
10. **Feature-by-label analysis** — after labels, plot TP vs FP feature distributions

### Short-term

11. Complete legacy ground truth (4 frames, 77 penguins)
12. Run full legacy LiDAR dataset (35 GB, cloud0-4.las)

### Medium-term

13. Georeference Argentina GPS waypoints
14. Resolve thermal calibration (investigate 9°C and 30°C offsets) — lower priority after negative discrimination POC

---

## 📁 Key Files Reference

| Purpose | File |
|---------|------|
| Product requirements | `PRD.md` |
| Tested commands | `RUNBOOK.md` |
| Task tracking | `notes/pipeline_todo.md` |
| Argentina tuning | `docs/reports/SESSION_2025-12-10_LIDAR_TUNING.md` |
| This status | `docs/reports/STATUS.md` |
| LiDAR honest assessment | `docs/reports/LIDAR_ASSESSMENT_2025-12-21.md` |
| Feature analysis | `docs/reports/FEATURE_ANALYSIS.md` |
| Labeling protocol | `docs/process/LABELING_PROTOCOL.md` |
| Detailed review | `docs/reports/PROJECT_STATUS_REVIEW_2025-12-17.md` |
| Tile overlap evidence | `data/interim/tile_overlap_analysis.json` |

---

## ✅ Argentina LiDAR Parameters (Working, Pending Validation)

### DJI L2 (Caleta sites)
```bash
# Validated baseline (hag_max most sensitive; see FEATURE_ANALYSIS.md parameter sweep)
python3 scripts/run_lidar_hag.py \
  --data-root "data/2025/Caleta Small Island" \
  --out data/interim/caleta.json \
  --cell-res 0.25 --hag-min 0.20 --hag-max 0.60 \
  --min-area-cells 2 --max-area-cells 80 \
  --dedupe-radius-m 0.5 --emit-geojson --plots
```

### TrueView 515 (San Lorenzo)
```bash
# Reproject first (POSGAR → UTM 20S)
pdal translate input.las output.las \
  --filters.reprojection.in_srs="EPSG:5345" \
  --filters.reprojection.out_srs="EPSG:32720" \
  -f filters.reprojection

# Then detect
python3 scripts/run_lidar_hag.py \
  --data-root "data/2025/San_Lorenzo_UTM" \
  --out data/interim/san_lorenzo.json \
  --cell-res 0.3 --hag-min 0.28 --hag-max 0.48 \
  --min-area-cells 3 --max-area-cells 50 \
  --dedupe-radius-m 0.5 --emit-geojson --plots
```

---

## Next Review

After test suite is fixed and fusion pipeline is implemented.

---

*For detailed fact-checked analysis, see `docs/reports/PROJECT_STATUS_REVIEW_2025-12-17.md`*
