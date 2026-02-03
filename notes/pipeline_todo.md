# Pipeline TODO — Single Source of Truth

**Last Updated:** 2025-12-17 UTC
**Purpose:** Single task tracker for penguin detection pipeline development

---

## 🎯 Project Context

**Goal:** Production penguin detection pipeline using LiDAR and thermal imagery

**Ground Truth Targets:**
- Legacy (Punta Tombo): ~1,533 penguins (manual ground truth)
- Argentina 2025: ~3,705 penguins (field counts, NOT georeferenced locations)

**Current State:** LiDAR production-ready; Thermal in research phase; Fusion not implemented

---

## 🧭 Workstreams (QC vs Scientific Validity)

We track progress in two parallel lanes:

1. **QC / Engineering milestones**: make the pipeline deterministic, CRS-aware, runnable, and contract-stable (no claims about temperature accuracy).
2. **Scientific / Field-valid milestones**: calibration + validation that make outputs numerically trustworthy for counting.

**Policy:** `docs/process/WORKSTREAMS_QC_VS_SCIENCE.md`

---

## 🚨 Critical Blockers (Fix First)

### 1. Test Suite Guardrails
**Status:** ✅ GREEN

| Test | Status | Notes |
|------|--------|-------|
| `tests/test_golden_aoi.py` | ✅ | Golden AOI baseline: 776 (guardrail, `--top-method max`) |
| `tests/test_lidar_dem_hag_unit.py` | ✅ | DEM/HAG edge cases + quantile invariance |
| `tests/test_thermal.py` | ✅ | GDAL-dependent tests may skip |
| `tests/test_thermal_radiometric.py` | ✅ | Data-dependent integration cases may skip |
| `tests/test_data_2025_invariants.py` | ✅ | 2025 catalogue + counts invariants |

**Impact:** Regression safety net is in place; keep these green.

### 2. Documentation Refresh
**Status:** ✅ DONE (2025-12-17)

- [x] `docs/reports/STATUS.md` — Updated 2025-12-17
- [x] `notes/pipeline_todo.md` — This file
- [x] `RUNBOOK.md` — Updated 2025-12-17

---

## ⏳ Active Development Tasks

### 3. Argentina LiDAR Integration
**Status:** ✅ VALIDATED (2025-12-10)

**Completed:**
- [x] Catalogue Argentina LiDAR data (24 files, 754M points, 25.8 GB)
- [x] Tune DJI L2 parameters (+6% error on Caleta Tiny Island)
- [x] Tune TrueView 515 parameters (+1% error on San Lorenzo Box Count)
- [x] Document in `SESSION_2025-12-10_LIDAR_TUNING.md`

**Remaining:**
- [ ] Process San Lorenzo Full (23 GB) — significant compute time required
- [ ] Run remaining Caleta box counts for validation

### 4. Ground Truth Completion
**Status:** ⏳ 44% COMPLETE (legacy)

**Legacy (Punta Tombo):**
- [x] Frame 0353: 13 penguins → `frame_0353_locations.csv`
- [x] Frame 0355: 21 penguins → `frame_0355_locations.csv`
- [x] Frame 0356: 26 penguins → `frame_0356_locations.csv`
- [ ] Frame 0354: ~23 penguins (from PDF page 6)
- [ ] Frame 0357: ~20 penguins (from PDF page 3)
- [ ] Frame 0358: ~15 penguins (from PDF page 2)
- [ ] Frame 0359: ~13 penguins (from PDF page 1)

**Argentina:**
- [x] Extract GPS waypoints from PDF → `san_lorenzo_waypoints.csv` (48 waypoints)
- [x] Extract penguin counts → `san_lorenzo_analysis.json` (~3,705 total)
- [ ] Implement GPS→pixel projection (camera model exists in `thermal.py`)
- [ ] Generate per-image ground truth CSVs

**IMPORTANT:** The 48 waypoints in `san_lorenzo_waypoints.csv` are boundary/route points, NOT the 3,705 penguin locations. Georeferencing is required to convert field counts to pixel coordinates.

---

## 📋 Pending Implementation

## ✅ QC / Engineering Milestones (do now; testable without new imagery)

### E1. Explicit Schemas + CRS Contracts
**Status:** ✅ MOSTLY COMPLETE (2026-01-30)

- [x] CRS auto-detection from LAS headers (run_lidar_hag.py)
- [x] CRS mismatch warning between CLI arg and auto-detected CRS
- [x] `crs_source` field in summary JSON (cli vs autodetect)
- [x] `aoi_from_lidar.py` requires explicit CRS (removed hardcoded default)
- [x] CRS audit script (`scripts/audit_crs.py`)
- [x] CRS unit tests (`tests/test_crs_autodetect.py` — 13 tests)
- [ ] Define versioned summary JSON schema for thermal / fusion
- [x] Enforce CRS mismatch rejection (fusion already rejects mismatches)

### E2. Thermal Pixel→CRS Scaffolding (for orthorectified outputs)
**Status:** ❌ NOT STARTED

- [ ] Implement a pixel→CRS conversion helper using raster geotransforms (no GDAL required)
- [ ] Add unit tests with synthetic transforms
- [ ] Define the expected “thermal CRS detections summary” format consumed by fusion

### E3. Fusion-as-QC (Geometry/Alignment)
**Status:** ✅ PARTIAL

- [x] `pipelines/fusion.py` KD-tree join + CRS mismatch rejection
- [x] `scripts/run_fusion_join.py` CLI wrapper
- [ ] Add explicit output labeling (`purpose=qc_alignment`, `temperature_calibrated=false`)

### E4. Golden Harness Decision (resolve ambiguity)
**Status:** ✅ DONE

- [x] `pipelines/golden.py` runs the golden AOI guardrail (`tests/test_golden_aoi.py`) as a QC harness
- [x] `make golden` added as the supported entrypoint for the guardrail

### E5. LiDAR Deep Dive (2026-01-30)
**Status:** ✅ IMPLEMENTED

- [x] CRS auto-detection + audit script (Phase 1)
- [x] San Lorenzo AOI fix: Plains perimeter winding, Bushes box addition (Phase 2)
- [x] AOI clarification memo in LIDAR_VALIDATION.md (Phase 2)
- [x] Intensity feature extraction: `--extract-intensity` flag, per-cell grid, per-detection features (Phase 3)
- [x] Intensity analysis script: `scripts/analyze_lidar_intensity.py` (Phase 3)
- [x] Parameter sweep framework: `scripts/lidar_parameter_sweep.py` with 1D+2D sweeps (Phase 4)
- [x] Confidence scoring: `--compute-confidence` flag, Gaussian membership scores (Phase 4)
- [x] Precision estimation: `scripts/estimate_precision.py` with Wilson CI (Phase 5)
- [x] Labeling protocol: `docs/process/LABELING_PROTOCOL.md` (Phase 5)
- [x] Detection rate summary: `docs/reports/DETECTION_RATE_SUMMARY.md` (Phase 6)
- [x] Client assessment: `docs/reports/LIDAR_ASSESSMENT_2026-01.md` (Phase 6)

**Remaining (requires data/labeling):**
- [ ] Run intensity-enriched pipeline on Caleta Tiny, Bushes box, Caleta Small
- [ ] Run parameter sweep on Caleta Tiny
- [ ] Label 80+ detection samples per site
- [ ] Compute precision estimates from labels
- [ ] Generate per-site detection maps with confidence coloring

---

## 🔬 Scientific / Field-Valid Milestones (blocked on calibration + new client imagery)

### S1. Thermal Calibration
**Status:** ❌ NOT STARTED

This is required before treating thermal-derived counts as trustworthy.

### S2. Camera Model Accuracy Harness (RMSE on control points)
**Status:** ❌ NOT STARTED

Add a validation harness that measures geometric accuracy of orthorectification against known control points (LRF targets / surveyed points).

### S3. Argentina Ground Truth Georeferencing Scope
**Status:** ❌ NOT STARTED

Argentina data currently provides **region totals** (~3,705 counts), not per-penguin pixel labels. Decide whether validation is region-based (polygons/density) or point-based (if new imagery enables per-object labeling).

### 5. Thermal Calibration Investigation
**Status:** ❌ NOT STARTED

**Problem:** Two documented calibration offsets:
1. **Ambient offset (~9°C):** Metadata says 21°C ambient, computed max is 12.16°C
   - Source: `docs/reports/thermal_extraction_progress.md:91-105`
2. **Biological offset (~30°C):** Expected penguin temps 25-30°C, observed ~-5°C
   - Source: `docs/supplementary/RADIOMETRIC_INTEGRATION.md:62-76`

**Investigation Options:**
- [ ] Option A: Decode ThermalCalibration blob (32KB binary data)
- [ ] Option B: Apply atmospheric correction (Planck law with emissivity)
- [ ] Option C: Empirical offset calibration (match to ambient metadata)

**Estimated time:** 4-6 hours

### 6. Thermal Parameter Optimization
**Status:** ⏳ BLOCKED by calibration + ground truth

**Dependencies:**
- Thermal calibration resolved (#5)
- Ground truth complete (#4)

**Tasks:**
- [ ] Run parameter sweep on all 7 ground truth frames
- [ ] Generate precision-recall curves
- [ ] Select optimal threshold (target F1 > 0.1, baseline is 0.043)
- [ ] Document in `data/interim/optimal_thermal_params.json`

### 7. Full Dataset Thermal Run
**Status:** ❌ NOT STARTED

**Dependencies:**
- Optimal parameters (#6)

**Tasks:**
- [ ] Create `scripts/run_thermal_detection_batch.py` with checkpointing
- [ ] Process ~1,533 thermal frames
- [ ] Validate total count within 20% of 1,533

### 8. Fusion Pipeline Implementation
**Status:** ✅ BASIC JOIN IMPLEMENTED (partial)

**Current state:**
- ✅ `pipelines/fusion.py` implements a nearest-neighbor spatial join (KD-tree) with `match_radius_m` thresholding and labels (`both` / `lidar_only` / `thermal_only`).
- ⚠️ Inputs must already include `x`/`y` in the same projected CRS; thermal pixel detections are not georeferenced here.
- ✅ Golden AOI guardrail is runnable via `make golden` (QC harness; `tests/test_golden_aoi.py`).

**Required implementation:**
- [x] Spatial join (LiDAR candidates + thermal detections)
- [x] Buffer matching (via `match_radius_m`)
- [x] Label classification (Both / LiDAR-only / Thermal-only)
- [ ] LiDAR-gated thermal scoring
- [x] `scripts/run_fusion_join.py` CLI
- [x] `tests/test_fusion_join.py` coverage

**Estimated time:** 6-8 hours

### 9. Full Legacy LiDAR Run
**Status:** ⏳ PENDING

**Tasks:**
- [ ] Process cloud0-4.las (~35 GB total)
- [ ] Compare count to ~1,533 target
- [ ] Generate full-dataset QC panels

---

## 🚧 Blocker Matrix

| Task | Blocked By | Blocks |
|------|------------|--------|
| #1 Test Suite Fix | — | All CI/validation |
| #2 Doc Refresh | — | User clarity |
| #3 Argentina LiDAR | — | — (validated) |
| #4 Ground Truth | Manual annotation | #6, #7 |
| #5 Thermal Calibration | Investigation | #6 |
| #6 Thermal Optimization | #4, #5 | #7 |
| #7 Full Thermal Run | #6 | #8 |
| #8 Fusion Pipeline | #7, #9 | Client delivery |
| #9 Full LiDAR Run | — | #8 |

**Critical Path:** #1 → #4 → #5 → #6 → #7 → #8

---

## ✅ Completed Tasks (Archive)

### Environment & Infrastructure (Oct 2025)
- [x] Create project structure (scripts/, pipelines/, data/, tests/)
- [x] Set up legacy data mounts (read-only symlinks)
- [x] Create requirements.txt with pinned dependencies
- [x] Implement `scripts/run_lidar_hag.py`
- [x] Create `tests/test_golden_aoi.py` (12 tests)
- [x] Validate 776 detection baseline on cloud3.las (`--top-method max`, updated Feb 2026)

### Thermal Infrastructure (Oct 2025)
- [x] Extract thermal ortho script from legacy
- [x] Wire 16-bit radiometric extraction into `pipelines/thermal.py`
- [x] Create `tests/test_thermal_radiometric.py` (5 tests)
- [x] Document thermal signal variability (0.14°C to 11°C)
- [x] Complete thermal characterization study

### Camera Model Fix (Dec 2025)
- [x] Research DJI angle conventions (see `docs/research/DJI Drone Camera Model & Angle Conventions.pdf`)
- [x] Fix `rotation_from_ypr()` with proper Euler ZYX sequence
- [x] Use Gimbal angles directly (ABSOLUTE to NED), not Flight+Gimbal
- [x] Add deprecation warnings to incorrect `Pose.*_total` properties
- [x] Verify det(R)=+1 for all test cases including nadir
- [x] All 41 tests passing

### Argentina Data (Dec 2025)
- [x] Catalogue Argentina LiDAR (24 files, 754M points)
- [x] Tune DJI L2 parameters (Caleta sites)
- [x] Tune TrueView 515 parameters (San Lorenzo)
- [x] Extract GPS waypoints from field notes
- [x] Document in SESSION_2025-12-10_LIDAR_TUNING.md

---

## 📊 Progress Summary

| Category | Complete | Total | Percentage |
|----------|----------|-------|------------|
| LiDAR Pipeline | 7 | 7 | 100% |
| LiDAR Deep Dive | 11 | 16 | 69% |
| Thermal Pipeline | 5 | 9 | 56% |
| Fusion Pipeline | 3 | 6 | 50% |
| Ground Truth (legacy) | 3 | 7 | 43% |
| Ground Truth (Argentina) | 2 | 4 | 50% |
| Documentation | 4 | 4 | 100% |

**Overall:** ~60% complete (LiDAR deep dive implemented, pending data runs and labeling)

---

## 📁 Related Documents

| Document | Purpose |
|----------|---------|
| `docs/reports/STATUS.md` | Current implementation state |
| `docs/reports/PROJECT_STATUS_REVIEW_2025-12-17.md` | Detailed fact-checked review |
| `RUNBOOK.md` | Tested commands only |
| `PRD.md` | Product requirements |
| `docs/reports/SESSION_2025-12-10_LIDAR_TUNING.md` | Argentina sensor tuning |

---

## 🔄 Update Log

- **2026-01-30:** LiDAR deep dive: CRS auto-detection, AOI fixes, intensity extraction, parameter sweep, confidence scoring, precision estimation framework, client deliverables
- **2025-12-17 (PM):** Camera model fix (A3) implemented — proper Euler ZYX sequence, gimbal angles ABSOLUTE to NED, det(R)=+1 verified, all 41 tests passing
- **2025-12-17:** Major refresh — accurate task status, clarified ground truth (48 waypoints vs 3,705 count), documented test failures, updated blocker matrix
- **2025-11-05:** Consolidated from PLAN.md, NEXT_STEPS.md, and Codex feedback
- **2025-10-21:** Major update post client meeting
- **2025-10-17:** Initial version (LiDAR HAG polish tasks)

---

**This file is the single source of truth for task tracking. Update after each task completion.**
