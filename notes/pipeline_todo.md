# Pipeline TODO — Single Source of Truth

**Last Updated:** 2025-10-21 (Consolidated from PLAN.md, NEXT_STEPS.md, and Codex feedback)
**Purpose:** Single task tracker for Argentina deployment preparation

---

## 🎯 Client Context (Post-Meeting 2025-10-21)

**Goal:** Optimize detection pipelines to approximate **1533 total penguin count**
**Client Requests:**
- More visual outputs for stakeholder communication
- Dial in thermal detection (complete ground truth validation)
- Run across all thermal images (~1533 frames)
- Tune LiDAR detection to match target count
- Fusion analysis to understand LiDAR+Thermal overlap

**Timeline:** Prepare for Argentina data collection trip

---

## ⚡ Critical Path (Prioritized by Dependencies)

### 1. Environment Verification & Foundation Hygiene [30 min] 🔴 NEXT UP

**Codex Feedback:** "Finish the outstanding retest once laspy is available, record the run in RUNBOOK.md, and note GDAL install status so thermal tests stop skipping unexpectedly."

**Tasks:**
- [ ] Install/verify laspy availability (`pip list | grep laspy`)
- [ ] Rerun `make test-lidar` and verify 862 detections (or document new baseline)
- [ ] Run `pytest tests/test_golden_aoi.py -v` and verify all 12 tests pass
- [ ] Document GDAL install status (system/conda/none) in RUNBOOK.md:30
  - If installed: note version and method (conda/brew/apt)
  - If missing: document that thermal tests will skip
- [ ] Record results in RUNBOOK.md with timestamp

**Dependencies:** None (foundational)
**Blocking:** All downstream tasks depend on stable environment
**Owner:** Richard
**Deliverable:** RUNBOOK.md updated with confirmed environment state

---

### 2. Manual Ground Truth Annotation [2-3 hours] 🔴 HIGH PRIORITY

**Codex Feedback:** "Queue the manual ground-truth pass over verification_images/Penguin Count - 7 Photos.pdf; log findings and any mismatches in thermal_extraction_progress.md."

**Status:** 60/137 penguins validated (44% complete)

**Tasks:**
- [ ] Frame 0354: Extract 23 penguin locations from PDF page 6 → CSV
- [ ] Frame 0357: Extract 20 penguin locations from PDF page 3 → CSV
- [ ] Frame 0358: Extract 15 penguin locations from PDF page 2 → CSV
- [ ] Frame 0359: Extract 13 penguin locations from PDF page 1 → CSV
- [ ] Verify all 7 CSVs sum to 137 total penguins
- [ ] Document ambiguous cases ("Maybe 2?" annotations) in thermal_extraction_progress.md
- [ ] Log any mismatches between PDF circles and actual thermal hot spots

**Dependencies:** None (manual work)
**Blocking:** Thermal parameter optimization (#4)
**Owner:** Richard (manual annotation)
**Deliverable:** 7 complete CSV files in `verification_images/`

**Note:** Existing CSVs: 0353 (13), 0355 (21), 0356 (26) = 60 ✅ | Remaining: 71 penguins ❌

---

### 3. Thermal Calibration Fix [4-6 hours] 🔬 INVESTIGATION

**Codex Feedback:** "Decode or approximate the ThermalCalibration blob to resolve the ~9°C offset; prototype the thermal calibration fix on a single frame before batching."

**Status:** 9°C offset identified (max temp 12°C vs. expected 21°C ambient)

**Tasks:**
- [ ] **Prototype on frame 0356** (highest density, 26 verified penguin locations):

  **Option A:** Decode ThermalCalibration blob (32768 bytes)
  - Try interpreting as 16384 16-bit LUT
  - Document structure findings

  **Option B:** Apply atmospheric correction (Planck law)
  - Implement emissivity/reflection/humidity correction
  - Test on frame 0356

  **Option C:** Empirical offset
  - Calculate offset to match metadata ambient
  - Apply and validate against ground truth

- [ ] Measure temperatures at 26 verified penguin locations
- [ ] Verify hot spots align with ground truth CSV
- [ ] Calculate optimal detection threshold (local ΔT in °C)
- [ ] Document findings in thermal_extraction_progress.md:
  - Which method worked?
  - What temperature range for penguins?
  - Optimal threshold value?
  - False positive rate?

**Dependencies:** Ground truth CSV for frame 0356 ✅ (complete)
**Blocking:** Thermal parameter optimization (#4)
**Owner:** Richard + Claude (decoding assistance)
**Deliverable:** Calibrated thermal extraction function with documented threshold

---

### 4. Thermal Detection Parameter Optimization [4-6 hours] 🎯

**Codex Feedback:** "Retune hotspot thresholding so per-frame counts trend toward 1533 when summed; capture the workflow in pipelines/thermal.py docstrings and surface CLI knobs in scripts/run_thermal_ortho.py."

**Status:** Waiting for calibration fix (#3)

**Tasks:**
- [ ] Apply calibration fix to all 7 ground truth frames
- [ ] Run parameter sweep:
  - Threshold: [0.1, 0.15, 0.2, 0.25, 0.3, 0.5] °C (local ΔT)
  - Window size: [5, 7, 9, 11] pixels (background radius)
  - Min cluster: [1, 2, 3, 5] connected pixels
  - Morphology: ['none', 'open', 'close']
- [ ] Generate precision-recall curve across all 7 frames
- [ ] Select operating point (optimize F1 score, target > 0.1)
- [ ] Document optimal parameters in `data/interim/optimal_thermal_params.json`
- [ ] Update `pipelines/thermal.py` docstrings with threshold logic
- [ ] Add CLI knobs to `scripts/run_thermal_ortho.py` (--threshold, --window-size, etc.)
- [ ] Update RUNBOOK.md with optimized thermal detection command

**Dependencies:** Ground truth (#2), Calibration (#3)
**Blocking:** Full-dataset thermal run (#5)
**Deliverable:** `optimal_thermal_params.json` + RUNBOOK entry

**Baseline (frame 0356):** Precision 2.2%, Recall 80.8%, F1 0.043

---

### 5. Full-Dataset Thermal Run [2-4 hours runtime] 🚀

**Status:** Script needs creation

**Tasks:**
- [ ] Create `scripts/run_thermal_detection_batch.py`:
  - Load optimal params from #4
  - Process ~1533 thermal frames
  - Checkpoint every 100 frames (resume capability)
  - Progress bar with ETA
  - Error logging for problematic frames
  - Parallel processing (4 cores)

- [ ] Run on full dataset:
  - Input: `data/legacy_ro/penguin-2.0/data/raw/thermal-images/`
  - Output: `data/processed/thermal_detections/`

- [ ] Validate outputs:
  - Total count within 20% of 1533? (1226-1840)
  - Distribution: count-per-frame histogram
  - Visual spot-check: sample 10-20 frames

- [ ] Document runtime and results

**Dependencies:** Optimal parameters (#4)
**Blocking:** Fusion analysis (#8)
**Deliverable:** `all_detections.csv` + `summary.json` (total count)

---

### 6. LiDAR Validation & Full-Dataset Run [2-3 hours] 🗺️

**Codex Feedback:** "Validate the current HAG tweaks, regenerate QC panels in data/interim/lidar_hag_plots/, and update rollup logic so reports can be calibrated against the 1533 benchmark (document assumptions in manifests/qc_report.md once the count math is steady)."

**Status:** Working on sample (862 detections), needs full-dataset validation

**Tasks:**
- [x] Wire CLI parameters (--top-method, --top-zscore-cap, --connectivity) ✅ DONE
- [x] Reapply HAG threshold after morphology ✅ DONE
- [x] Skip duplicate tiles (LiDAR/ vs LiDAR/sample/) ✅ DONE
- [ ] Rerun `make test-lidar` and verify 862 ± tolerance (blocked on laspy - see #1)
- [ ] Regenerate QC panels in `data/interim/lidar_hag_plots/`
- [ ] Verify panel annotations use filtered detection count

- [ ] Run on full dataset (5 tiles: cloud0-4.las, ~35 GB):
  ```bash
  python scripts/run_lidar_hag.py \
    --data-root data/legacy_ro/penguin-2.0/data/raw/LiDAR/ \
    --out data/processed/lidar_full_run.json \
    --cell-res 0.25 --hag-min 0.2 --hag-max 0.6 \
    --min-area-cells 2 --max-area-cells 80 \
    --emit-geojson --plots --rollup
  ```

- [ ] Compare total count to thermal count (#5):
  - Document discrepancy (LiDAR vs Thermal)
  - Hypothesize reasons (false positives, occlusion, etc.)

- [ ] Update rollup logic for 1533 benchmark calibration
- [ ] Document assumptions in `manifests/qc_report.md`
- [ ] Update RUNBOOK.md with full-dataset LiDAR command

**Dependencies:** Environment verification (#1)
**Blocking:** Fusion analysis (#8)
**Deliverable:** `lidar_full_run.json` (total count) + QC panels + qc_report.md

---

### 7. Thermal ↔ LiDAR Alignment Workflow [2-3 hours] 🔧

**Codex Feedback:** "Capture a reproducible workflow: estimate boresight from LRF data, orthorectify ≥2 consecutive thermal frames with --snap-grid, and record residuals against LiDAR detections."

**Status:** Infrastructure exists, workflow needs documentation

**Tasks:**
- [ ] Document reproducible orthorectification workflow:
  1. Extract poses from DJI EXIF (using exiftool)
  2. Estimate boresight calibration from LRF measurements
  3. Orthorectify 2+ consecutive frames with `--snap-grid`
  4. Verify grid alignment (ratio=1.0, offsets=0.0)
  5. Record residuals against LiDAR DSM

- [ ] Capture workflow in RUNBOOK.md
- [ ] Note missing inputs for field teams (poses, timestamps, LRF targets)
- [ ] Produce time-aligned thermal stacks (or document blockers)

**Dependencies:** LiDAR DSM (#6), Thermal calibration (#3)
**Blocking:** Fusion implementation (#8)
**Deliverable:** RUNBOOK entry for thermal orthorectification workflow

---

### 8. Fusion Pipeline Implementation [6-8 hours] 🔗

**Codex Feedback:** "Once both stages are calibrated, stand up pipelines/fusion.py/scripts/run_fusion_join.py with LiDAR-gated thermal scoring, add regression coverage in tests/test_fusion.py, and record a reproducible command in RUNBOOK.md."

**Status:** Not started

**Tasks:**
- [ ] Create `pipelines/fusion.py` library:
  - Geospatial join function (LiDAR + Thermal)
  - Buffer matching (0.5m radius)
  - Label classification (Both / LiDAR-only / Thermal-only)
  - LiDAR-gated thermal scoring (use HAG as prior)
  - Statistical analysis functions

- [ ] Create `scripts/run_fusion_join.py` CLI:
  - Input: LiDAR candidates.gpkg + thermal VRT/CSV
  - Output: fusion.csv with labels + confidence scores
  - QC panel generation (fusion overlay map)

- [ ] Add regression coverage in `tests/test_fusion.py`:
  - Test spatial join logic
  - Test label classification
  - Test LiDAR-gated path with fixtures

- [ ] Run fusion analysis on full dataset
- [ ] Generate visual outputs (fusion map, Venn diagram, sample frames)
- [ ] Document reproducible command in RUNBOOK.md

**Dependencies:** Thermal results (#5), LiDAR results (#6), Alignment workflow (#7)
**Blocking:** Client reporting (#9)
**Deliverable:** fusion.py library + fusion_join.py CLI + test suite + fusion.csv results

---

### 9. Reporting & Client Visual Outputs [4-6 hours] 📊

**Codex Feedback:** "Expand QC outputs (thermal ortho snapshots, combined LiDAR/thermal overlays) and summarize deliverables plus open questions in STATUS.md so the client sees progress toward Argentina collection."

**Status:** Not started

**Tasks:**
- [ ] Expand QC visual outputs:
  - Thermal ortho snapshots (10-20 sample frames with detections)
  - Combined LiDAR/Thermal overlays (fusion maps)
  - Detection count histogram (per-frame distribution)
  - Spatial distribution heatmap (flight path + density)

- [ ] Create client-ready report (PDF/slides):
  - Executive summary (1 page): Total count vs. 1533 target
  - Methodology (2 pages): LiDAR, Thermal, Fusion explained
  - Results with visuals (5-10 pages): Maps, plots, tables
  - Recommendations for Argentina (1-2 pages): Parameters, data collection

- [ ] Update STATUS.md:
  - Completed tasks (thermal calibrated, full runs complete)
  - Open questions for Argentina deployment
  - Progress toward 1533 target
  - Deliverables summary

**Dependencies:** All analysis complete (#5, #6, #8)
**Deliverable:** Client presentation package + updated STATUS.md

---

## 🧹 Project Hygiene (Non-Blocking)

### Documentation Reconciliation [1-2 hours]

**Codex Feedback:** "Reconcile overlapping guidance in PLAN.md, STATUS.md, and RUNBOOK.md so the 'what works' section, tested commands, and DORA next steps reflect the current state; move stale tasks into a single source (this file)."

**Tasks:**
- [ ] **Archive outdated docs:**
  - Move PLAN.md → `notes/archive/PLAN_2025-10-08.md` (historical, mostly complete)
  - Move NEXT_STEPS.md → `notes/archive/NEXT_STEPS_2025-10-21.md` (superseded by this file)

- [ ] **Update living docs:**
  - STATUS.md = "what works now" (update after each task)
  - RUNBOOK.md = "proven commands only" (update after validation)
  - THIS FILE (notes/pipeline_todo.md) = task tracking (single source)

- [ ] **Single source of truth:**
  - Tasks: THIS FILE
  - Current state: STATUS.md
  - Commands: RUNBOOK.md
  - Requirements: PRD.md
  - Quick start: README.md

**Deliverable:** Clear doc hierarchy, no overlapping guidance

---

### Script Cleanup [15 min]

**Tasks:**
- [ ] Move prototype thermal scripts to `scripts/archive/`:
  - test_thermal_detection*.py (4 files)
  - test_thermal_local_deltaT.py
  - investigate_thermal_calibration.py
  - test_thermal_*.sh (2 files)

- [ ] Keep production scripts:
  - run_lidar_hag.py ✅
  - run_thermal_ortho.py ✅
  - validate_thermal_extraction.py ✅
  - visualize_thermal_detections.py ✅
  - validate_environment.sh ✅

---

## 🚧 Blocker Matrix

| Task | Blocked By | Blocks |
|------|-----------|--------|
| #1 Environment Verification | None | All tasks |
| #2 Ground Truth | None | #4 |
| #3 Thermal Calibration | None | #4, #5 |
| #4 Parameter Optimization | #2, #3 | #5 |
| #5 Full Thermal Run | #4 | #8 |
| #6 LiDAR Full Run | #1 | #8 |
| #7 Alignment Workflow | #3, #6 | #8 |
| #8 Fusion | #5, #6, #7 | #9 |
| #9 Client Reporting | #5, #6, #8 | None |

**Critical Path:** #1 → #2 → #3 → #4 → #5 → #8 → #9 (~36 hours)
**Parallel:** #6 can run alongside #2-#5 (saves ~3 hours)

---

## ✅ Completion Criteria

### Task Complete When:
- [x] All checkboxes checked
- [x] Deliverable created and validated
- [x] Relevant docs updated (STATUS.md, RUNBOOK.md)
- [x] Results documented in this file

---

## 📅 Timeline Estimate

**Week 1:**
- Mon: #1, #2 (Environment + Ground Truth)
- Tue-Wed: #3 (Thermal Calibration)
- Thu: #4 (Parameter Optimization)
- Fri: #5 start (Full Thermal Run - overnight)

**Week 2:**
- Mon: #5 complete, #6 (LiDAR Full Run)
- Tue: #7, #8 start (Alignment + Fusion)
- Wed-Thu: #8 complete (Fusion)
- Fri: #9 (Client Reporting)

**Total: 2 weeks**

---

## 🔄 Update Log

- **2025-10-17:** Initial version (LiDAR HAG polish tasks)
- **2025-10-21:** Major consolidation - merged PLAN.md, NEXT_STEPS.md, and Codex feedback into single source

---

**This file is the single source of truth for task tracking. Update after each task completion.**
