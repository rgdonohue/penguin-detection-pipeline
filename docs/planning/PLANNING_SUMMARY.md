# Planning Summary — Post-Client Meeting

**Date:** 2025-10-21
**Context:** Client meeting feedback + Codex review incorporated
**Status:** Planning complete, ready for execution

---

## 📋 What Was Created

### 1. **notes/pipeline_todo.md** — Single Source of Truth ⭐
**Purpose:** Consolidated task tracking for Argentina deployment prep

**Key Features:**
- 9 prioritized tasks with dependency graph
- Blocker matrix showing critical path
- Codex feedback integrated throughout
- 2-week timeline estimate
- Clear completion criteria for each task

**This replaces:** Overlapping guidance from PLAN.md, docs/planning/NEXT_STEPS.md, and scattered TODOs

### 2. **docs/planning/NEXT_STEPS.md** — Detailed 7-Phase Plan
**Purpose:** Comprehensive breakdown of each phase with examples

**Covers:**
- Phase 1: Complete ground truth validation (4 frames remaining)
- Phase 2: Optimize thermal detection parameters
- Phase 3: Full dataset thermal run (~1533 frames)
- Phase 4: Tune LiDAR detection pipeline
- Phase 5: Fusion analysis implementation
- Phase 6: Client-ready visual outputs
- Phase 7: Project cleanup

**Audience:** Reference for understanding approach and methodology

### 3. **CLEANUP_PLAN.md** — Project Organization Guide
**Purpose:** Consolidate documentation and archive old scripts

**Actions:**
- Move PLAN.md → docs/planning/ (centralized)
- Move 8 prototype scripts → scripts/experiments/
- Consolidate 15+ markdown files → 8 essential docs
- Create README.md (missing)
- Update docs/reports/STATUS.md to remove "BLOCKER" language

---

## 🎯 Client Goals Recap

From your meeting notes:

**Primary Goal:** Approximate **1533 total penguin count** using:
1. Thermal detection (optimized)
2. LiDAR detection (tuned)
3. Fusion analysis (understand overlap)

**Secondary Goal:** Generate more visual outputs for stakeholders

**Timeline:** Prepare for Argentina data collection trip

---

##⚡ Critical Path Summary

From `notes/pipeline_todo.md`:

```
#1 Environment Verification (30 min)
  ↓
#2 Ground Truth Annotation (3 hours) ← Manual work
  ↓
#3 Thermal Calibration Fix (6 hours) ← Investigation
  ↓
#4 Parameter Optimization (6 hours)
  ↓
#5 Full Thermal Run (4 hours runtime)
  ↓
#8 Fusion Implementation (8 hours)
  ↓
#9 Client Reporting (6 hours)
```

**Parallel track:** #6 LiDAR Full Run (3 hours) can run alongside #2-#5

**Total critical path:** ~36 hours active work
**Calendar time:** 2 weeks (with testing, iteration, debugging)

---

## 🔑 Key Decisions Incorporated

### From Client Feedback:
- **1533 target count** is the calibration benchmark (not 1022)
- Focus on visual outputs for stakeholder communication
- Need to complete manual ground truth validation carefully

### From Codex Review:
- Create single source of truth for tasks (notes/pipeline_todo.md) ✅
- Prototype thermal calibration on single frame before batching ✅
- Rerun environment tests and document GDAL status ✅
- Capture reproducible workflows in RUNBOOK.md ✅
- Update manifests/qc_report.md with 1533 benchmark assumptions ✅

---

## 📂 File Organization

### Task Tracking (NEW)
- **notes/pipeline_todo.md** ← Single source of truth for all tasks

### Reference Plans
- **docs/planning/NEXT_STEPS.md** ← Detailed phase breakdown (superseded by pipeline_todo.md)
- **CLEANUP_PLAN.md** ← Project organization guide

### Living Documents (Update After Each Task)
- **docs/reports/STATUS.md** ← "What works now"
- **RUNBOOK.md** ← "Proven commands only"
- **docs/reports/thermal_extraction_progress.md** ← Investigation findings log

### Stable Reference
- **PRD.md** ← Requirements & design
- **README.md** ← User-facing quick start (to be created)
- **CLAUDE.md** ← AI collaboration guidance

---

## 🚀 Next Actions (In Order)

### Immediate (This Week)
1. **Environment Verification** [30 min]
   - Verify laspy installed
   - Rerun make test-lidar (expect 879 detections)
   - Run pytest tests/test_golden_aoi.py (expect 12 passes)
   - Document GDAL status in RUNBOOK.md

2. **Ground Truth Annotation** [3 hours] ← Manual work
   - Frame 0354: 23 penguins
   - Frame 0357: 20 penguins
   - Frame 0358: 15 penguins
   - Frame 0359: 13 penguins
   - Total: 71 remaining penguins to annotate

3. **Thermal Calibration** [6 hours]
   - Prototype on frame 0356 (26 verified penguins)
   - Try Option A (decode ThermalCalibration blob), B (atmospheric correction), or C (empirical offset)
   - Document findings in docs/reports/thermal_extraction_progress.md

### Week 1 Deliverables
- Environment validated ✅
- Ground truth complete (137 penguins) ✅
- Thermal calibration working ✅
- Parameters optimized ✅
- Full thermal run started (overnight) ✅

### Week 2 Deliverables
- Full thermal run complete + count
- LiDAR full run complete + count
- Fusion analysis complete
- Client visual outputs ready
- docs/reports/STATUS.md updated for Argentina

---

## ✅ Success Criteria

**Primary:** Combined count within 20% of 1533 (1226-1840 penguins)

**Secondary:**
- Thermal F1 score > 0.1 (10x improvement from 0.043)
- Visual outputs ready for client presentation
- Recommendations documented for Argentina deployment

**Stretch:**
- Combined count within 10% of 1533 (1380-1686)
- Thermal F1 score > 0.2
- Fusion agreement rate > 60%

---

## 📝 Outstanding Questions for You

As noted in docs/planning/NEXT_STEPS.md, these would help refine the plan:

1. **Ground Truth Tool:** Want help creating a click-to-annotate tool for faster CSV creation, or prefer manual entry?

2. **1533 Source:** Where does this estimate come from? (manual count? previous analysis? rough estimate?)
   - Affects tolerance expectations

3. **Argentina Timeline:** When is the trip? How urgent are these outputs?
   - Affects whether we can iterate or need to ship fast

4. **Compute Resources:** Multi-core machine available for batch processing?
   - Affects runtime estimates (4 cores vs. single core)

5. **Deliverable Format:** PDF report? PowerPoint? Jupyter notebook? All of above?
   - For client presentation package

6. **Fusion Priority:** Is fusion analysis critical for Argentina, or are separate LiDAR+Thermal counts sufficient?
   - Affects whether to prioritize fusion or focus on counts

---

## 🧹 Project Hygiene Tasks (Non-Blocking)

From CLEANUP_PLAN.md:

**Can do anytime (doesn't block client work):**
- Keep PLAN.md and docs/planning/NEXT_STEPS.md inside docs/planning/ for quick reference
- Move prototype thermal scripts to scripts/experiments/
- Create missing README.md
- Update docs/reports/STATUS.md to remove "BLOCKER" language (thermal investigation complete)
- Consolidate docs/supplementary/ files

**Estimated time:** 1-2 hours total

---

## 📚 Documentation Hierarchy (Post-Cleanup)

**For Task Tracking:**
- `notes/pipeline_todo.md` ← Single source of truth

**For Current State:**
- `docs/reports/STATUS.md` ← What works now

**For Commands:**
- `RUNBOOK.md` ← Tested commands only

**For Requirements:**
- `PRD.md` ← Product requirements

**For Users:**
- `README.md` ← Quick start guide

**For Investigation:**
- `docs/reports/thermal_extraction_progress.md` ← Thermal findings log
- `docs/supplementary/THERMAL_INVESTIGATION_FINAL.md` ← Complete analysis

**For Client:**
- `docs/PENGUIN_DETECTION_PIPELINE_PROJECT_SUMMARY.md`
- `docs/THERMAL_FINDINGS_SUMMARY.md`
- `docs/FIELD_DATA_SPECIFICATIONS.md`

---

## 🎨 Key Insights from Planning

### 1. Ground Truth is Foundation
All thermal optimization depends on completing the manual annotation of 4 remaining frames (71 penguins). This is the only truly blocking manual task.

### 2. Thermal Calibration is Critical Unknown
The 9°C offset needs resolution before batch processing. Prototyping on frame 0356 first will derisk the approach before committing to full dataset.

### 3. LiDAR Can Run in Parallel
LiDAR full-dataset run doesn't depend on thermal work, so it can proceed independently. This saves ~3 hours on critical path.

### 4. Visual Outputs Throughout
Client specifically requested more visuals, so each phase should generate visual QC outputs (maps, plots, overlays) - not just numbers.

### 5. Conservative Timeline
2 weeks accounts for debugging, iteration, and unexpected issues. If everything works smoothly, could compress to 10 days.

---

## 🔄 How to Use These Documents

**Starting a work session:**
1. Check `notes/pipeline_todo.md` for next task
2. Review task dependencies and deliverables
3. Execute task
4. Update docs/reports/STATUS.md and RUNBOOK.md if needed
5. Check off task in pipeline_todo.md

**Need command reference:**
- Check RUNBOOK.md for tested commands
- Don't trust commands in archived docs

**Need context on design:**
- Check PRD.md for requirements
- Check docs/reports/thermal_extraction_progress.md for investigation history

**Need to explain to client:**
- Use docs/THERMAL_FINDINGS_SUMMARY.md
- Use docs/FIELD_DATA_SPECIFICATIONS.md

---

## ✨ Summary

**What you asked for:** "Review our last chats, make a plan for next phase (thermal detection optimization, full dataset run, visual outputs, LiDAR tuning, fusion), and clean up the project."

**What was delivered:**
- ✅ `notes/pipeline_todo.md` — Single source of truth for all tasks (9 prioritized tasks, 2-week plan)
- ✅ `docs/planning/NEXT_STEPS.md` — Detailed 7-phase breakdown with examples and rationale
- ✅ `CLEANUP_PLAN.md` — Project organization guide (doc consolidation, script archiving)
- ✅ Codex feedback incorporated throughout (foundation hygiene, prototype-before-batch, capture workflows)
- ✅ Client goals centered (1533 target count, visual outputs, Argentina prep)

**Recommended first step:** Task #1 in pipeline_todo.md - Environment Verification (30 min)

**Critical manual task:** Task #2 - Complete ground truth annotation (3 hours, blocks thermal optimization)

**Questions for you:** See "Outstanding Questions" section above

---

**Ready to proceed?** Open `notes/pipeline_todo.md` and start with Task #1.
