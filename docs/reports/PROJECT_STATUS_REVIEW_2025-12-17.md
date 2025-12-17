# Project Status Review — Penguin Detection Pipeline v4.0

**Review Date:** 2025-12-17
**Reviewer:** Project Manager / Senior GIS Analyst
**Validation:** Cross-checked against repository contents by Codex and Cursor Agent

---

## Executive Summary

The Penguin Detection Pipeline v4.0 has a **production-ready LiDAR component** with validated Argentina sensor tuning, but faces **critical infrastructure issues**: broken test suite, stale documentation (6-10 weeks old), and incomplete fusion/golden harnesses. The thermal pipeline remains in research phase with unresolved calibration issues.

**Overall Maturity:** ~55% complete
**Test Suite Status:** BROKEN (sample data missing, 2 thermal test failures)
**Documentation Status:** STALE (requires immediate refresh)

---

## 1. Component Status

### LiDAR Detection Pipeline

| Aspect | Status | Evidence |
|--------|--------|----------|
| Core Algorithm | Production-ready | `scripts/run_lidar_hag.py` (620+ lines) |
| Golden AOI Baseline | 879 detections | Documented in multiple files |
| Argentina Tuning | Validated | DJI L2: +6% error, TrueView 515: +1% error |
| Test Suite | BROKEN | `data/legacy_ro/.../LiDAR/sample/` empty |

**Argentina LiDAR Catalogue** (verified from `data/2025/lidar_catalogue_full.json`):
- Total files: 24
- Total points: 753,786,458 (~754M)
- Total size: 25,822.7 MB (~25.8 GB)

**Tuned Parameters** (from `SESSION_2025-12-10_LIDAR_TUNING.md`):

| Sensor | Cell Res | HAG Range | Min Area | Error vs Ground Truth |
|--------|----------|-----------|----------|----------------------|
| DJI L2 | 0.25m | 0.28-0.48m | 3 cells | +6% |
| TrueView 515 | 0.30m | 0.28-0.48m | 3 cells | +1% |

### Thermal Pipeline

| Aspect | Status | Evidence |
|--------|--------|----------|
| 16-bit Extraction | Working | `pipelines/thermal.py:97-104` |
| Camera Model | Implemented | `pipelines/thermal.py:478-523` (hand-rolled) |
| Scale Heuristics | Fragile | Magic constants at lines 78-83 |
| Calibration | UNRESOLVED | Two different offset issues documented |
| Test Suite | FAILING | 2 failures in `test_thermal.py` |

**Calibration Issues** (two distinct problems):

1. **Ambient Offset (~9°C)**: Metadata ambient (21°C) vs computed max (12.16°C)
   - Source: `docs/reports/thermal_extraction_progress.md:91-105`

2. **Biological Offset (~30°C)**: Expected penguin temps (25-30°C) vs observed (~-5°C)
   - Source: `docs/supplementary/RADIOMETRIC_INTEGRATION.md:62-76`

**Thermal Scale Constants** (`pipelines/thermal.py:78-83`):
```python
DEFAULT_THERMAL_SCALE = 64.0
ALTERNATE_SCALES = (96.0, 80.0, 128.0)
```
These are undocumented heuristics for H30T sensor modes.

### Fusion Pipeline

| Aspect | Status | Evidence |
|--------|--------|----------|
| Implementation | STUB ONLY | `pipelines/fusion.py:29` raises `NotImplementedError` |
| Golden Harness | STUB ONLY | `pipelines/golden.py:30` raises `NotImplementedError` |

Both files contain placeholder dataclasses but no functional code.

---

## 2. Test Infrastructure Status

### Current Failures

| Test File | Issue | Line | Root Cause |
|-----------|-------|------|------------|
| `test_golden_aoi.py` | Data missing | 51 | `LiDAR/sample/cloud3.las` does not exist |
| `test_thermal.py` | Rotation det=-1 | 76 | Nadir case returns inverted matrix |
| `test_thermal.py` | Pose columns | 116 | Stricter validation in `pipelines/thermal.py:401` |

### Passing Tests

- `tests/test_thermal_radiometric.py` — 5 tests (thermal extraction)

### Test Coverage Gap

No integration tests exist for the end-to-end LiDAR → Thermal → Fusion workflow.

---

## 3. Ground Truth Status

### Verified Facts

| Dataset | Actual Content | Common Misconception |
|---------|----------------|---------------------|
| `data/processed/san_lorenzo_waypoints.csv` | 48 lines (boundary/route waypoints) | Often cited as "3,705 GPS waypoints" |
| `data/processed/san_lorenzo_analysis.json` | Penguin COUNT totals (~3,705) | This is count, not locations |
| `verification_images/*.csv` | 3 files (frames 0353, 0355, 0356) | 4 frames still missing |

### Legacy Ground Truth Progress

- **Completed:** 60 penguins across 3 frames (44%)
- **Remaining:** 77 penguins across 4 frames (frames 0354, 0357, 0358, 0359)
- **Source:** `notes/pipeline_todo.md:50-53`

### Argentina Ground Truth

The ~3,705 figure represents **total penguin counts** from field observations, NOT georeferenced pixel locations. GPS→pixel projection has not been implemented.

| Site | Count | Source |
|------|-------|--------|
| San Lorenzo Caves | 908 | Field count |
| San Lorenzo Plains | 453 | Field count |
| San Lorenzo Road | 359 | Field count |
| San Lorenzo Box Counts | 87 | Field count |
| Caleta Small Island | 1,557 | Field count |
| Caleta Tiny Island | 321 | Field count |
| Caleta Box Counts | 20 | Field count |
| **Total** | **3,705** | |

---

## 4. Documentation Status

### Staleness Assessment

| Document | Last Updated | Age (as of 2025-12-17) |
|----------|--------------|------------------------|
| `RUNBOOK.md` | 2025-10-08 | ~10 weeks |
| `docs/reports/STATUS.md` | 2025-11-05 | ~6 weeks |
| `notes/pipeline_todo.md` | 2025-11-05 | ~6 weeks |

### Documentation Sprawl

- **40+ markdown files** across docs/, notes/, and root
- Overlap between STATUS.md, pipeline_todo.md, and various planning docs
- 14 experimental scripts in `scripts/experiments/` without clear ownership

---

## 5. Architecture Concerns

### Code Quality Issues Requiring Expert Review

| File | Lines | Concern |
|------|-------|---------|
| `scripts/run_lidar_hag.py` | 182-300 | Complex online quantile tracking; edge cases untested |
| `pipelines/thermal.py` | 179-234 | Magic scale constants; silent fallback to "dynamic" mode |
| `pipelines/thermal.py` | 478-523 | Hand-rolled rotation/projection; no external validation |
| `pipelines/lidar.py` | 138 | `subprocess.run()` with no stdout/stderr capture |

### Design Decisions

1. **LiDAR wrapper shells out to CLI** — Fragile path resolution; loses output on failure
2. **Reproducibility test runs full pipeline twice** — Slow CI; consider checksum validation
3. **No streaming pipeline** — Each stage runs independently; no incremental processing

---

## 6. Recommended Actions

### Critical (Blockers)

| Priority | Action | Estimated Time |
|----------|--------|----------------|
| 1 | Restore `cloud3.las` sample data | 10 min |
| 2 | Fix `test_thermal.py` rotation test | 1 hour |
| 3 | Fix `test_thermal.py` pose column test | 30 min |

### Documentation Debt

| Priority | Action | Estimated Time |
|----------|--------|----------------|
| 4 | Update STATUS.md with current state | 30 min |
| 5 | Update pipeline_todo.md with accurate progress | 30 min |
| 6 | Update RUNBOOK.md with Argentina commands | 30 min |
| 7 | Clarify ground truth (48 waypoints vs 3,705 count) | 15 min |

### Technical Debt

| Priority | Action | Estimated Time |
|----------|--------|----------------|
| 8 | Implement fusion pipeline | 6-8 hours |
| 9 | Add integration test for full workflow | 2-3 hours |
| 10 | Document thermal scale heuristics | 1 hour |
| 11 | Archive or document experimental scripts | 1 hour |

---

## 7. Deployment Recommendation

**LiDAR:** Ready for production use on Argentina data with tuned parameters.

**Thermal:** Experimental only. Use for visual QC, not automated counts. Calibration issues prevent reliable absolute temperature readings.

**Fusion:** Not available. Pipeline stub must be implemented before LiDAR+Thermal integration.

---

## Appendix: Verification Sources

All claims in this report were cross-checked against:

- Repository file contents (direct reads)
- `data/2025/lidar_catalogue_full.json` — Argentina LiDAR metadata
- `docs/reports/SESSION_2025-12-10_LIDAR_TUNING.md` — Sensor tuning results
- `docs/reports/thermal_extraction_progress.md` — Calibration issues
- `docs/supplementary/RADIOMETRIC_INTEGRATION.md` — Biological offset
- `notes/pipeline_todo.md` — Task status and ground truth gaps
- `verification_images/` — Ground truth CSV inventory
- `pipelines/*.py` — Implementation status
- `tests/*.py` — Test suite structure

**Validation performed by:** Codex, Cursor Agent
**Report author:** Claude (Project Manager / Senior GIS Analyst role)

---

*This report supersedes `docs/reports/STATUS.md` (2025-11-05) and should be considered the current source of truth until that file is updated.*
