# Next Steps — Post-Client Meeting Plan

**Date:** 2025-10-21
**Status:** Planning phase for Argentina deployment optimization
**Client Feedback:** Very pleased with progress; want more visual outputs and refined detection

---

## Context Summary

### Client Meeting Outcomes
- ✅ Client very pleased with work so far
- 🎯 **Primary Goal:** Approximate the estimated **1533 total penguin count** using both thermal and LiDAR detection
- 📊 **Secondary Goal:** Generate more visual outputs for stakeholder communication
- 🇦🇷 **Timeline:** Prepare for Argentina data collection trip

### Current Status
- ✅ **LiDAR Pipeline:** Working (802 detections on cloud3.las sample)
- ✅ **Thermal Investigation:** Complete - mixed contrast findings (typical 8-11°C, worst-case 0.14°C)
- ✅ **Ground Truth:** 3/7 frames manually verified (frames 0353, 0355, 0356 = 60 penguins)
- ⚠️ **Thermal Detection:** Variable performance - frame-dependent (F1: 0.02-0.30)
- ❌ **Full Dataset Run:** Not yet attempted across all ~1533 thermal frames
- ❌ **Fusion Analysis:** Not yet implemented

### The 1533 Target
The client's estimated total penguin count of **1533** (not 1022 as previously stated) is our calibration target. We need to:
1. Optimize thermal detection to approximate this count
2. Tune LiDAR detection to match this count
3. Understand the overlap/discrepancy through fusion analysis

---

## Phase 1: Complete Ground Truth Validation (Manual Process)

**Priority:** HIGH
**Timeline:** 2-3 hours manual work
**Owner:** Richard (manual annotation required)

### Tasks

1. **Complete remaining 4 frames from PDF** (frames 0354, 0357, 0358, 0359)
   - Frame 0354: 23 penguins → `verification_images/frame_0354_locations.csv`
   - Frame 0357: 20 penguins → `verification_images/frame_0357_locations.csv`
   - Frame 0358: 15 penguins → `verification_images/frame_0358_locations.csv`
   - Frame 0359: 13 penguins → `verification_images/frame_0359_locations.csv`

   **Method:**
   - Open PDF in Preview/Acrobat
   - Open corresponding thermal image in image viewer with pixel coordinates
   - Manually transcribe blue circle centers to CSV (x, y, label)
   - Cross-reference with existing CSVs (0353, 0355, 0356) for format consistency

2. **Verify total count**
   - Expected: 137 penguins across 7 frames (21 seconds of flight)
   - Validate CSV row counts match PDF annotations

3. **Create validation summary**
   - Document any ambiguous detections ("Maybe 2?" annotations in PDF)
   - Note frame quality and detection difficulty

**Deliverable:** 7 complete CSV files with 137 total penguin locations

---

## Phase 2: Optimize Thermal Detection Parameters

**Priority:** HIGH
**Timeline:** 4-6 hours
**Dependencies:** Phase 1 complete

### Current Performance (Varies by Frame)
- Frame 0353 (10.5°C contrast): Best F1 = 0.30 with local ΔT method
- Frame 0355 (8.5°C contrast): Best F1 = 0.29 with bilateral filter
- Frame 0356 (0.14°C contrast): Best F1 = 0.09 with local ΔT method
- Challenge: No method achieves both >50% precision and >80% recall

### Optimization Strategy

1. **Run parameter sweep on all 7 ground truth frames**
   ```bash
   # Test different threshold combinations
   python scripts/optimize_thermal_detection.py \
     --ground-truth-dir verification_images/ \
     --thermal-dir data/legacy_ro/penguin-2.0/data/raw/thermal-images/ \
     --output data/interim/thermal/optimization_results.csv
   ```

   **Parameters to sweep:**
   - `--threshold`: [0.1, 0.15, 0.2, 0.25, 0.3, 0.5] (local ΔT in °C)
   - `--window-size`: [5, 7, 9, 11] (local background radius in pixels)
   - `--min-cluster-size`: [1, 2, 3, 5] (connected pixels)
   - `--morphology`: ['none', 'open', 'close'] (noise reduction)

2. **Evaluate precision-recall tradeoff**
   - Generate PR curve across all 7 frames
   - Select operating point that maximizes F1 score
   - Consider separate thresholds for high-density vs low-density scenes

3. **Analyze failure modes**
   - False positives: What are they? (rocks, shadows, artifacts)
   - False negatives: Which penguins are missed? (edge cases, low contrast)
   - Spatial patterns: Do errors cluster?

**Deliverable:** Optimized thermal detection parameters with quantified performance metrics

---

## Phase 3: Full Dataset Thermal Detection Run

**Priority:** HIGH
**Timeline:** 1-2 hours (mostly compute time)
**Dependencies:** Phase 2 complete

### Dataset Scope
- **Total frames:** ~1533 thermal images
- **Location:** `data/legacy_ro/penguin-2.0/data/raw/thermal-images/`
- **Expected runtime:** ~30-60 seconds per frame (if orthorectification needed) = 12-25 hours
  - **Alternative:** Run on raw thermal without ortho (5-10 seconds/frame) = 2-4 hours

### Execution Plan

1. **Create batch processing script**
   ```bash
   python scripts/run_thermal_detection_batch.py \
     --input data/legacy_ro/penguin-2.0/data/raw/thermal-images/ \
     --params data/interim/thermal/optimal_thermal_params.json \
     --output data/processed/thermal/thermal_detections/ \
     --parallel 4 \
     --checkpoint-every 100
   ```

2. **Output format**
   - Per-frame CSV: `detections_frameXXXX.csv` (x, y, confidence, temperature)
   - Aggregate CSV: `all_detections.csv` (frame_id, x, y, confidence, temperature, timestamp)
   - Summary JSON: `detection_summary.json` (total_count, per_frame_counts, runtime)

3. **Monitoring**
   - Progress bar with ETA
   - Checkpoint saves every 100 frames (resume capability)
   - Error logging for problematic frames

4. **Validation**
   - Sanity check: Does total count approximate 1533?
   - Distribution check: Count per frame (should follow flight path density)
   - Visual spot-check: Sample 10-20 frames for manual review

**Deliverable:** Complete thermal detection results across ~1533 frames with total penguin count estimate

---

## Phase 4: Tune LiDAR Detection Pipeline

**Priority:** MEDIUM
**Timeline:** 3-4 hours
**Dependencies:** Phase 3 complete (to understand LiDAR vs Thermal discrepancy)

### Current Performance
- **Sample run:** 802 detections on cloud3.las (4.4 GB tile)
- **Full dataset:** 5 tiles (cloud0-4.las, ~35 GB total)
- **Parameters:** cell_res=0.25m, HAG 0.2-0.6m, area 2-80 cells

### Optimization Strategy

1. **Run LiDAR on full dataset with current parameters**
   ```bash
   python scripts/run_lidar_hag.py \
     --data-root data/legacy_ro/penguin-2.0/data/raw/LiDAR/ \
     --out data/processed/lidar_full_run.json \
     --cell-res 0.25 --hag-min 0.2 --hag-max 0.6 \
     --min-area-cells 2 --max-area-cells 80 \
     --emit-geojson --plots --rollup
   ```

2. **Compare LiDAR count to thermal count**
   - If LiDAR >> Thermal: LiDAR has false positives (rocks, vegetation)
   - If Thermal >> LiDAR: LiDAR missing penguins (low point density, occlusion)
   - Ideal: Both approximate 1533 with explainable discrepancy

3. **Parameter adjustment**
   - Adjust HAG range (currently 0.2-0.6m, penguin height)
   - Refine area constraints (currently 2-80 cells = 0.125-5 m²)
   - Add circularity/solidity filters if too many false positives
   - Tune cell resolution if needed (0.25m vs 0.5m tradeoff)

4. **Spatial overlap analysis** (leads into Phase 5)
   - Which LiDAR detections have corresponding thermal hotspots?
   - Which thermal detections lack LiDAR height signature?

**Deliverable:** Optimized LiDAR detection with total count and geospatial outputs (GeoJSON, GPKG)

---

## Phase 5: Fusion Analysis

**Priority:** MEDIUM
**Timeline:** 4-6 hours
**Dependencies:** Phase 3 and 4 complete

### Goal
Understand the relationship between LiDAR and thermal detections:
- **Both:** High-confidence penguins (height + thermal signature)
- **LiDAR-only:** Possible false positives or thermally-invisible penguins
- **Thermal-only:** Possible false positives or penguins in LiDAR gaps

### Approach

1. **Geospatial join**
   - Orthorectify thermal detections to DSM coordinate system
   - Buffer LiDAR centroids (e.g., 0.5m radius)
   - Match thermal hotspots within buffer

2. **Label classification**
   ```python
   for lidar_detection in lidar_detections:
       nearby_thermal = find_thermal_within_radius(lidar_detection, radius=0.5m)
       if nearby_thermal:
           label = "Both"
       else:
           label = "LiDAR-only"

   for thermal_detection in thermal_detections:
       nearby_lidar = find_lidar_within_radius(thermal_detection, radius=0.5m)
       if not nearby_lidar:
           label = "Thermal-only"
   ```

3. **Statistical analysis**
   - Agreement rate: % of detections in "Both" category
   - Disagreement patterns: Spatial distribution of discrepancies
   - Confidence weighting: Use thermal temperature and LiDAR HAG as confidence scores

4. **Visual outputs** (client deliverable)
   - Fusion map: Color-coded detections (green=Both, blue=LiDAR-only, red=Thermal-only)
   - Venn diagram: Count breakdown
   - Sample frames: Side-by-side LiDAR+Thermal overlays

**Deliverable:** Fusion analysis report with visual outputs and detection count breakdown

---

## Phase 6: Visual Outputs for Client

**Priority:** HIGH (client specifically requested)
**Timeline:** 2-3 hours
**Dependencies:** Phases 3, 4, 5 complete

### Deliverables

1. **Detection Visualizations**
   - Sample thermal frames with detections overlaid (10-20 frames)
   - LiDAR height maps with penguin centroids
   - Fusion maps showing LiDAR+Thermal agreement

2. **Summary Statistics**
   - Total penguin count estimate (with confidence interval)
   - Detection method breakdown (LiDAR, Thermal, Both)
   - Per-frame count histogram
   - Spatial distribution map (flight path with density heatmap)

3. **Comparison to 1533 Target**
   - How close did we get?
   - Explanation of discrepancy (if any)
   - Recommendations for parameter refinement

4. **Client-Ready Report** (PDF/slides)
   - Executive summary (1 page)
   - Methodology overview (2 pages)
   - Results with visuals (5-10 pages)
   - Recommendations for Argentina deployment (1-2 pages)

**Deliverable:** Client presentation package with visual outputs

---

## Phase 7: Project Cleanup

**Priority:** MEDIUM
**Timeline:** 2-3 hours
**Dependencies:** None (can run in parallel)

### Tasks

1. **Consolidate documentation**
   - Too many markdown files in `docs/supplementary/`
   - Create `docs/archive/` for old investigation notes
   - Keep only essential docs in root and `docs/`:
     - Root: `README.md`, `PRD.md`, `RUNBOOK.md`, `Makefile`
     - `docs/planning/`: Working plans (`docs/planning/NEXT_STEPS.md`, `PLAN.md`, etc.)
     - `docs/reports/`: Status snapshots (`docs/reports/STATUS.md`, thermal progress logs)

2. **Remove redundant scripts**
   - Many test scripts in `scripts/`:
     - `test_thermal_detection.py`
     - `test_thermal_detection_simple.py`
     - `test_thermal_detection_0353.py`
     - `test_thermal_detection_enhanced.py`
     - `test_thermal_local_deltaT.py`
   - Consolidate into a single script or move to `scripts/experiments/`
   - Keep only production scripts

3. **Update docs/reports/STATUS.md**
   - Reflect completion of thermal investigation
   - Remove "BLOCKER" status (investigation complete, weak signal understood)
   - Update "Next Steps" section with this plan

4. **Clean up interim files**
   ```bash
   # Archive old test outputs
   mkdir -p data/interim/thermal/archive
   mv data/interim/thermal/thermal_validation data/interim/thermal/archive/
   ```

5. **Update RUNBOOK.md**
   - Add proven thermal detection commands
   - Document full-dataset batch processing workflow
   - Add fusion analysis commands

**Deliverable:** Cleaned-up project structure with clear documentation

---

## Proposed Execution Order

### Week 1: Ground Truth & Thermal Optimization
1. **Mon-Tue:** Complete ground truth validation (Phase 1)
2. **Wed-Thu:** Optimize thermal detection parameters (Phase 2)
3. **Fri:** Start full-dataset thermal run (Phase 3, overnight compute)

### Week 2: LiDAR, Fusion, Deliverables
4. **Mon:** Complete thermal run analysis, tune LiDAR (Phase 4)
5. **Tue-Wed:** Fusion analysis (Phase 5)
6. **Thu:** Generate visual outputs (Phase 6)
7. **Fri:** Project cleanup, client report finalization (Phase 7)

### Total Time Estimate: 25-35 hours over 2 weeks

---

## Key Decisions Needed

### 1. Thermal Detection Approach
**Question:** Run thermal detection on orthorectified images or raw thermal?

**Option A: Orthorectified** (geospatially accurate)
- ✅ Enables direct LiDAR-Thermal fusion
- ✅ Accurate spatial coordinates
- ❌ Slow (~30-60 sec/frame × 1533 = 12-25 hours)
- ❌ Depends on pose quality

**Option B: Raw Thermal** (faster)
- ✅ Fast (~5-10 sec/frame × 1533 = 2-4 hours)
- ✅ No dependency on pose/DSM
- ❌ No spatial coordinates (can't fuse with LiDAR)
- ❌ Count-only output

**Recommendation:** Start with Option B (raw thermal) for quick count estimate, then run Option A on subset for fusion analysis

### 2. Parameter Optimization Scope
**Question:** Optimize for precision, recall, or F1 score?

**Tradeoff:**
- High precision (fewer false positives) → undercount
- High recall (fewer false negatives) → overcount
- Balanced F1 → middle ground

**Recommendation:** Optimize for F1 score to balance precision/recall, then evaluate if count is close to 1533. If count is too low, shift toward higher recall.

### 3. Ground Truth Ambiguity
**Question:** How to handle "Maybe 2?" annotations in PDF?

**Options:**
- A: Include uncertain detections in ground truth (conservative)
- B: Exclude uncertain detections (strict)
- C: Create separate "uncertain" category for analysis

**Recommendation:** Option C - track separately to measure detector performance on ambiguous cases

---

## Risks & Mitigations

### Risk 1: Full Dataset Run Fails
**Probability:** Medium
**Impact:** High (blocks Phases 4-6)

**Mitigation:**
- Implement checkpointing (resume from failure)
- Test on 100-frame subset first
- Parallel processing to reduce runtime
- Fallback: Run on raw thermal instead of orthorectified

### Risk 2: Detection Count Far From 1533
**Probability:** Medium
**Impact:** Medium (requires re-tuning)

**Mitigation:**
- Iterative parameter adjustment
- Understand source of 1533 estimate (manual count? previous run?)
- Set realistic expectations with client (±10-20% is reasonable)

### Risk 3: Manual Ground Truth is Time-Consuming
**Probability:** High
**Impact:** Low (delays Phase 1 only)

**Mitigation:**
- Prioritize frames with highest penguin density (0356, 0354, 0355)
- Semi-automate with click-to-annotate tool
- Accept ±1-2 pixel uncertainty in manual annotation

### Risk 4: LiDAR-Thermal Fusion Shows Poor Agreement
**Probability:** Medium
**Impact:** Medium (complicates interpretation)

**Mitigation:**
- Understand reasons for disagreement (biological, technical, spatial)
- Use fusion to identify high-confidence detections (Both)
- Frame disagreement as valuable insight, not failure

---

## Success Criteria

### Phase 1 (Ground Truth)
- ✅ 7 CSV files created
- ✅ Total count = 137 penguins
- ✅ Format consistent with existing CSVs

### Phase 2 (Optimization)
- ✅ F1 score > 0.1 on validation set (10x improvement from 0.043)
- ✅ Precision > 10% (5x improvement from 2.2%)
- ✅ Recall > 70% (maintain 80.8%)

### Phase 3 (Full Run)
- ✅ Complete detection results for ~1533 frames
- ✅ Total count within 20% of 1533 target (1226-1840 penguins)
- ✅ Runtime < 5 hours

### Phase 4 (LiDAR)
- ✅ Full LiDAR run completes successfully
- ✅ Total count documented with geospatial outputs
- ✅ Count within 30% of thermal count (explainable discrepancy)

### Phase 5 (Fusion)
- ✅ Spatial join completes with labeled detections
- ✅ Agreement rate quantified (% in "Both" category)
- ✅ Visual outputs generated

### Phase 6 (Client Deliverables)
- ✅ Client report PDF created
- ✅ 10-20 sample visualizations included
- ✅ Recommendations for Argentina deployment documented

### Phase 7 (Cleanup)
- ✅ Documentation consolidated (≤10 markdown files in root/docs)
- ✅ Scripts organized (production vs archive)
- ✅ docs/reports/STATUS.md updated

---

---

## Appendix: File Inventory

### Ground Truth Status
- ✅ `verification_images/frame_0353_locations.csv` (13 penguins)
- ❌ `verification_images/frame_0354_locations.csv` (23 penguins) - MISSING
- ✅ `verification_images/frame_0355_locations.csv` (21 penguins)
- ✅ `verification_images/frame_0356_locations.csv` (26 penguins)
- ❌ `verification_images/frame_0357_locations.csv` (20 penguins) - MISSING
- ❌ `verification_images/frame_0358_locations.csv` (15 penguins) - MISSING
- ❌ `verification_images/frame_0359_locations.csv` (13 penguins) - MISSING

**Total Validated:** 60/137 penguins (44%) - Correct: 13+21+26=60
**Remaining Work:** 4 frames, 77 penguins

### Key Scripts
- ✅ `scripts/run_lidar_hag.py` - Working LiDAR detection
- ✅ `scripts/run_thermal_ortho.py` - Thermal orthorectification (working but not optimized)
- ✅ `scripts/experiments/validate_thermal_extraction.py` - Thermal validation tool
- ✅ `scripts/optimize_thermal_detection.py` - Thermal parameter sweeps
- ✅ `scripts/run_thermal_detection_batch.py` - Batch detection executor
- ❌ `scripts/run_fusion_join.py` - TO BE CREATED

### Documentation Requiring Cleanup
- `docs/supplementary/THERMAL_INVESTIGATION_FINAL.md` ✅ Keep (valuable reference)
- `docs/supplementary/THERMAL_INVESTIGATION_REVIEW.md` ❌ Archive (interim)
- `docs/supplementary/THERMAL_CALIBRATION_INVESTIGATION.md` ❌ Archive (interim)
- `docs/supplementary/THERMAL_EXPERT_REVIEW_REQUEST.md` ❌ Archive (not sent)
- `docs/supplementary/RADIOMETRIC_INTEGRATION.md` ❌ Archive (technical deep-dive)
- `docs/supplementary/notes.md` ❌ Archive (scratch notes)

---

**End of Plan**
