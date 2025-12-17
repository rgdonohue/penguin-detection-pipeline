# Project Status — Honest Assessment

Last updated: 2025-12-17 UTC

---

## ✅ What Actually Works

### 1. LiDAR Detection Pipeline
**Status:** PRODUCTION-READY (Argentina sensors validated)

- **Script:** `scripts/run_lidar_hag.py` (620+ lines, streaming architecture)
- **Dependencies:** `pipelines/utils/provenance.py`, laspy, scipy, scikit-image
- **Golden AOI baseline:** 802 candidates on cloud3.las (guardrail test)
- **Argentina validation (2025-12-10):**
  - DJI L2: +6% error (340 detections vs 321 ground truth)
  - TrueView 515: +1% error (108 detections vs 107 ground truth)
- **Outputs:** JSON, GeoJSON, QC plots, provenance tracking
- **Makefile target:** `make test-lidar`

**Argentina Data Processed:**
- 24 LiDAR files catalogued
- 754M points total
- 25.8 GB across DJI L2 and TrueView 515 sensors

### 2. Foundation Infrastructure
**Status:** WORKING

- **Legacy data mounts:** Read-only symlinks to 4 projects ✅
- **Directory structure:** scripts/, pipelines/, data/, manifests/, tests/ ✅
- **Environment spec:** `requirements.txt` (Python 3.11+ recommended) ✅
- **Makefile:** Working targets for env, test, test-lidar, clean ✅

**Test Suite (core):**
- `tests/test_golden_aoi.py` ✅ (guardrail baseline: 802)
- `tests/test_lidar_dem_hag_unit.py` ✅
- `tests/test_thermal.py` ✅ (GDAL-dependent tests may skip)
- `tests/test_thermal_radiometric.py` ✅ (data-dependent tests may skip)
- `tests/test_data_2025_invariants.py` ✅

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
**Status:** STUB ONLY

- `pipelines/fusion.py:29` raises `NotImplementedError`
- `pipelines/golden.py:30` raises `NotImplementedError`
- No spatial join, buffer matching, or label classification implemented

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
| LiDAR Detection | Production | High | None |
| LiDAR Tests | Passing | High | None |
| Thermal Extraction | Working | Medium | Calibration offset |
| Thermal Detection | Research | Low | F1 < 0.1 on most frames |
| Thermal Tests | Passing | Medium | Data/GDAL availability |
| Fusion | Stub | N/A | Not implemented |
| Ground Truth (legacy) | 44% | Medium | Manual annotation needed |
| Ground Truth (Argentina) | 0% | — | Georeferencing needed |

---

## 🎯 Critical Path

### Immediate Blockers (fix before any other work)

1. **Implement fusion pipeline** — `pipelines/fusion.py` is a stub
2. **Resolve thermal calibration** — address the documented offsets before operational use
3. **Complete ground truth** — finish legacy frames and implement Argentina GPS→pixel projection

### Short-term (1-2 weeks)

4. Complete legacy ground truth (4 frames, 77 penguins)
5. Implement fusion pipeline (~6-8 hours)
6. Run full legacy LiDAR dataset (35 GB, cloud0-4.las)

### Medium-term (1 month)

7. Georeference Argentina GPS waypoints (~9-15 hours)
8. Resolve thermal calibration (investigate 9°C and 30°C offsets)
9. Batch thermal processing on full dataset

---

## 📁 Key Files Reference

| Purpose | File |
|---------|------|
| Product requirements | `PRD.md` |
| Tested commands | `RUNBOOK.md` |
| Task tracking | `notes/pipeline_todo.md` |
| Argentina tuning | `docs/reports/SESSION_2025-12-10_LIDAR_TUNING.md` |
| This status | `docs/reports/STATUS.md` |
| Detailed review | `docs/reports/PROJECT_STATUS_REVIEW_2025-12-17.md` |

---

## ✅ Argentina LiDAR Parameters (Validated)

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
