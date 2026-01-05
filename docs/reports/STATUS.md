# Project Status — Honest Assessment

Last updated: 2025-12-21 UTC

---

## ✅ What Actually Works

### 1. LiDAR Detection Pipeline
**Status:** RUNS SUCCESSFULLY; VALIDATION IN PROGRESS (SEMANTICS LOCKED, AOI EVAL NEXT)

- **Script:** `scripts/run_lidar_hag.py` (620+ lines, streaming architecture)
- **Dependencies:** `pipelines/utils/provenance.py`, laspy, scipy, scikit-image
- **Golden AOI baseline:** 802 candidates on cloud3.las (guardrail test)
- **Outputs:** JSON, GeoJSON, QC plots, provenance tracking
- **Makefile target:** `make test-lidar`

**Argentina Data Processed (2025-12-21):**
- 24 LiDAR files catalogued
- 754M points total (100% processed)
- 25.8 GB across DJI L2 and TrueView 515 sensors

**VALIDATION CAVEATS (see `docs/reports/LIDAR_ASSESSMENT_2025-12-21.md`):**
- Previous "+6% / +1% error" claims were based on box count comparisons where tile extents ≠ counted areas
- Top-surface estimator (`p95`) is an approximate streaming quantile sensitive to order/chunking
- Detection semantics are now explicitly encoded as **candidates (blob centroids), not guaranteed individuals** (see `pipelines/contracts.py`)
- AOI-clipped precision not yet computed for any site

### 2. Foundation Infrastructure
**Status:** WORKING

- **Legacy data mounts:** Read-only symlinks to 4 projects ✅
- **Directory structure:** scripts/, pipelines/, data/, manifests/, tests/ ✅
- **Environment spec:** `requirements.txt` (Python 3.12.x baseline) ✅
- **Makefile:** Working targets for env, test, test-lidar, clean ✅

**Test Suite (core):**
- `tests/test_golden_aoi.py` ✅ (guardrail baseline: 802)
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
- **GPS waypoints:** 48 boundary/route waypoints extracted to `data/processed/san_lorenzo_waypoints.csv`
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
**Status:** 44% COMPLETE (legacy), NOT STARTED (Argentina)

**Legacy (Punta Tombo):**
- Completed: 60 penguins across 3 frames (0353, 0355, 0356)
- Remaining: 77 penguins across 4 frames (0354, 0357, 0358, 0359)
- CSVs in `verification_images/`

**Argentina:**
- GPS waypoints extracted but NOT projected to pixel coordinates
- No per-image ground truth CSVs exist yet

### 3. Thermal Detection
**Status:** RESEARCH PHASE

- F1 scores: 0.02-0.30 depending on frame contrast
- Parameter optimization scripts exist but not validated
- Batch processing not implemented
- Calibration must be resolved before production use

---

## 📊 Component Maturity Summary

| Component | Status | Confidence | Blocker |
|-----------|--------|------------|---------|
| LiDAR Detection | Runs, unvalidated | Medium | AOI alignment, detection semantics |
| LiDAR Tests | Passing | High | None |
| Thermal Extraction | Working | Medium | Calibration offset |
| Thermal Detection | Research | Low | F1 < 0.1 on most frames |
| Thermal Tests | Passing | Medium | Data/GDAL availability |
| Fusion | Partial | Medium | Thermal detections need CRS `x/y` |
| Ground Truth (legacy) | 44% | Medium | Manual annotation needed |
| Ground Truth (Argentina) | 0% | — | Georeferencing needed |

---

## 🎯 Critical Path

## ✅ Readiness Framing (QC vs Scientific)

This repo tracks two kinds of progress:

- **QC / Engineering readiness:** deterministic, CRS-aware artifacts that let us validate geometry and pipeline contracts.
- **Scientific / Field-valid readiness:** calibration + validation that makes thermal-derived counts trustworthy.

Policy: `docs/process/WORKSTREAMS_QC_VS_SCIENCE.md`

### Immediate Blockers (fix before any other work)

1. **Define detection semantics** — what does one LiDAR detection represent? (individual penguin, blob center, occupied cell)
2. **Implement AOI-clipped evaluation** — build precise polygon boundaries for each counted area; no count comparisons without AOI clipping
3. **Lock top-surface estimator** — use `max` (deterministic) or implement true per-cell quantile
4. **Make fusion inputs compatible** — ensure thermal detections are produced with CRS `x/y` to join with LiDAR
5. **Resolve thermal calibration** — address the documented offsets before operational use

### Short-term

6. Manual labeling of ~50-100 LiDAR detections (within AOI) to compute precision
7. Complete legacy ground truth (4 frames, 77 penguins)
8. Implement thermal→CRS georeferencing / ortho detection outputs for fusion
9. Run full legacy LiDAR dataset (35 GB, cloud0-4.las)

### Medium-term

10. Georeference Argentina GPS waypoints
11. Resolve thermal calibration (investigate 9°C and 30°C offsets)
12. Ground model experiment — compare `min` vs `p05` vs CSF on same data with AOI clipping

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
| Detailed review | `docs/reports/PROJECT_STATUS_REVIEW_2025-12-17.md` |
| Tile overlap evidence | `data/interim/tile_overlap_analysis.json` |

---

## ✅ Argentina LiDAR Parameters (Working, Pending Validation)

### DJI L2 (Caleta sites)
```bash
python3 scripts/run_lidar_hag.py \
  --data-root "data/2025/Caleta Small Island" \
  --out data/interim/caleta.json \
  --cell-res 0.25 --hag-min 0.28 --hag-max 0.48 \
  --min-area-cells 3 --max-area-cells 60 \
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
