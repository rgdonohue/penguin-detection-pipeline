# Project Cleanup Plan

**Date:** 2025-10-21
**Purpose:** Consolidate documentation and scripts for cleaner project structure

---

## Current State Analysis

### Documentation Status
**Root level:** 8 markdown files
- ✅ `README.md` (missing - should create)
- ✅ `PRD.md` (keep - product requirements)
- ✅ `RUNBOOK.md` (keep - operational commands)
- ✅ `STATUS.md` (keep - current status)
- ✅ `CONTRIBUTING.md` (keep - AI agent guidance)
- ✅ `NEXT_STEPS.md` (keep - just created)
- ✅ `RUNBOOK.md` (keep - collaboration guardrails)
- ✅ `DORA_INTEGRATION.md` (keep - best practices)

**docs/ directory:** 4 client-facing summaries (GOOD)
- ✅ `docs/PENGUIN_DETECTION_PIPELINE_PROJECT_SUMMARY.md`
- ✅ `docs/THERMAL_FINDINGS_SUMMARY.md`
- ✅ `docs/FIELD_DATA_SPECIFICATIONS.md`
- ✅ `docs/WILDLIFE_OBSERVER_CHECKLIST.md`
- ✅ `docs/EQUIPMENT_PROFILE.md`

**docs/supplementary/ directory:** 7 investigation notes (TOO MANY)
- ✅ `THERMAL_INVESTIGATION_FINAL.md` (keep - valuable reference)
- ❌ `THERMAL_INVESTIGATION_REVIEW.md` (archive - interim)
- ❌ `THERMAL_CALIBRATION_INVESTIGATION.md` (archive - interim)
- ❌ `THERMAL_EXPERT_REVIEW_REQUEST.md` (archive - not sent)
- ❌ `RADIOMETRIC_INTEGRATION.md` (archive - technical deep-dive)
- ❌ `FIELD_SOP.md` (merge into FIELD_DATA_SPECIFICATIONS.md)
- ❌ `FIELD_DEPLOYMENT_GUIDE.md` (merge into FIELD_DATA_SPECIFICATIONS.md)
- ❌ `notes.md` (archive - scratch notes)

### Scripts Status
**scripts/ directory:** 27 Python files

**Working Production Scripts:** (KEEP)
- ✅ `run_lidar_hag.py` (LiDAR detection - proven)
- ✅ `run_thermal_ortho.py` (Thermal orthorectification - working)
- ✅ `validate_thermal_extraction.py` (Thermal validation)
- ✅ `visualize_thermal_detections.py` (Visualization tool)
- ✅ `validate_environment.sh` (Environment setup)

**Investigation Scripts:** (ARCHIVE)
- ❌ `test_thermal_detection.py` (prototype)
- ❌ `test_thermal_detection_simple.py` (prototype)
- ❌ `test_thermal_detection_0353.py` (single-frame test)
- ❌ `test_thermal_detection_enhanced.py` (prototype)
- ❌ `test_thermal_local_deltaT.py` (investigation)
- ❌ `investigate_thermal_calibration.py` (investigation complete)
- ❌ `test_thermal_minimal.sh` (one-off test)
- ❌ `test_thermal_verified_frame.sh` (one-off test)

**To Be Created:** (PENDING)
- 📝 `optimize_thermal_detection.py` (Phase 2 of NEXT_STEPS.md)
- 📝 `run_thermal_detection_batch.py` (Phase 3)
- 📝 `run_fusion_join.py` (Phase 5)
- 📝 `generate_client_report.py` (Phase 6)

---

## Cleanup Actions

### 1. Create Archive Directories

```bash
# Create archive structure
mkdir -p docs/archive/thermal_investigation
mkdir -p scripts/archive/thermal_prototypes
mkdir -p data/interim/archive
```

### 2. Move Documentation

```bash
# Archive interim investigation docs
mv docs/supplementary/THERMAL_INVESTIGATION_REVIEW.md docs/archive/thermal_investigation/
mv docs/supplementary/THERMAL_CALIBRATION_INVESTIGATION.md docs/archive/thermal_investigation/
mv docs/supplementary/THERMAL_EXPERT_REVIEW_REQUEST.md docs/archive/thermal_investigation/
mv docs/supplementary/RADIOMETRIC_INTEGRATION.md docs/archive/thermal_investigation/
mv docs/supplementary/notes.md docs/archive/thermal_investigation/

# Keep docs/supplementary/ with only THERMAL_INVESTIGATION_FINAL.md
# OR move FINAL to docs/ and remove supplementary/
mv docs/supplementary/THERMAL_INVESTIGATION_FINAL.md docs/
rmdir docs/supplementary  # if empty

# Consolidate field guides
# Manual step: merge FIELD_SOP.md and FIELD_DEPLOYMENT_GUIDE.md into FIELD_DATA_SPECIFICATIONS.md
# Then archive originals
```

### 3. Move Scripts

```bash
# Archive thermal investigation prototypes
mv scripts/test_thermal_detection.py scripts/archive/thermal_prototypes/
mv scripts/test_thermal_detection_simple.py scripts/archive/thermal_prototypes/
mv scripts/test_thermal_detection_0353.py scripts/archive/thermal_prototypes/
mv scripts/test_thermal_detection_enhanced.py scripts/archive/thermal_prototypes/
mv scripts/test_thermal_local_deltaT.py scripts/archive/thermal_prototypes/
mv scripts/investigate_thermal_calibration.py scripts/archive/thermal_prototypes/

# Archive one-off test scripts
mv scripts/test_thermal_minimal.sh scripts/archive/
mv scripts/test_thermal_verified_frame.sh scripts/archive/
```

### 4. Create README.md

```bash
# Create root README with project overview
```

Content:
```markdown
# Penguin Detection Pipeline v4.0

Multi-sensor penguin detection system combining LiDAR and thermal imaging.

## Quick Start

# Setup environment
make env
source .venv/bin/activate

# Run LiDAR detection test
make test-lidar

# Run full test suite
make test

## Documentation

- **[PRD.md](PRD.md)** - Product requirements and implementation plan
- **[RUNBOOK.md](RUNBOOK.md)** - Operational commands and workflows
- **[STATUS.md](STATUS.md)** - Current implementation status
- **[NEXT_STEPS.md](NEXT_STEPS.md)** - Upcoming work and priorities
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - AI agent collaboration guidance

## Client Deliverables

- **[docs/PENGUIN_DETECTION_PIPELINE_PROJECT_SUMMARY.md](docs/PENGUIN_DETECTION_PIPELINE_PROJECT_SUMMARY.md)**
- **[docs/THERMAL_FINDINGS_SUMMARY.md](docs/THERMAL_FINDINGS_SUMMARY.md)**
- **[docs/FIELD_DATA_SPECIFICATIONS.md](docs/FIELD_DATA_SPECIFICATIONS.md)**

## Pipeline Stages

1. **LiDAR HAG Detection** - Identify penguin candidates from point clouds
2. **Thermal Orthorectification** - Project thermal imagery onto DSM
3. **Data Fusion** - Combine LiDAR and thermal detections

## Status

- ✅ LiDAR detection: Working (802 detections on sample)
- ✅ Thermal investigation: Complete (weak signal characterized)
- ⏳ Full-dataset run: Planned (see NEXT_STEPS.md)
- ⏳ Fusion analysis: Planned

## Contact

See [PRD.md](PRD.md) for project requirements.
See [STATUS.md](STATUS.md) for detailed implementation status.
```

### 5. Update STATUS.md

Remove "BLOCKER" language from thermal section:

```markdown
### 3. Thermal Characterization Study
**Status:** ✅ INVESTIGATION COMPLETE (2025-10-14)

**FINDINGS:**
- ✅ **Signal Characterized**: Thermal contrast 0.14°C (0.047σ SNR) quantified
- ✅ **Ground Truth Established**: 60/137 penguin locations validated (44%)
- ✅ **Biological Explanation**: Effective penguin insulation minimizes surface thermal signature
- ✅ **Detection Performance**: Precision 2.2%, Recall 80.8%, F1 0.043 (requires optimization)
- 📊 **Assessment**: Weak but usable signal; parameter tuning needed for operational deployment

**NEXT:** Optimize detection parameters (see NEXT_STEPS.md Phase 2)
```

Remove old "Immediate Next Steps" section, replace with:

```markdown
## 📋 Next Steps

See **[NEXT_STEPS.md](NEXT_STEPS.md)** for comprehensive plan.

**Current priorities:**
1. Complete ground truth validation (4 remaining frames)
2. Optimize thermal detection parameters
3. Run full-dataset thermal detection (~1533 frames)
4. Generate client visual outputs
```

### 6. Update RUNBOOK.md

Add section for full-dataset workflows:

```markdown
## Full Dataset Processing

### Thermal Detection Batch Run

```bash
# Run optimized thermal detection across all frames
python scripts/run_thermal_detection_batch.py \
  --input data/legacy_ro/penguin-2.0/data/raw/thermal-images/ \
  --params data/interim/optimal_thermal_params.json \
  --output data/processed/thermal_detections/ \
  --parallel 4 \
  --checkpoint-every 100
```

**Status:** ⏳ TO BE IMPLEMENTED (see NEXT_STEPS.md Phase 3)

### LiDAR Full Dataset Run

```bash
# Run LiDAR detection on all tiles
python scripts/run_lidar_hag.py \
  --data-root data/legacy_ro/penguin-2.0/data/raw/LiDAR/ \
  --out data/processed/lidar_full_run.json \
  --cell-res 0.25 --hag-min 0.2 --hag-max 0.6 \
  --min-area-cells 2 --max-area-cells 80 \
  --emit-geojson --plots --rollup
```

**Status:** ⏳ TO BE TESTED (script exists, not run on full dataset)
```

---

## Final Structure

```
penguins-4.0/
├── README.md                    # ⭐ New - project overview
├── PRD.md                       # ✅ Keep - product requirements
├── RUNBOOK.md                   # ✅ Keep - operational commands
├── STATUS.md                    # ✅ Keep (updated)
├── NEXT_STEPS.md                # ✅ Keep - comprehensive plan
├── CONTRIBUTING.md                    # ✅ Keep - AI guidance
├── RUNBOOK.md                 # ✅ Keep
├── DORA_INTEGRATION.md          # ✅ Keep
├── Makefile
├── requirements.txt
├── requirements-full.txt
│
├── docs/
│   ├── PENGUIN_DETECTION_PIPELINE_PROJECT_SUMMARY.md
│   ├── THERMAL_FINDINGS_SUMMARY.md
│   ├── THERMAL_INVESTIGATION_FINAL.md    # Moved from supplementary/
│   ├── FIELD_DATA_SPECIFICATIONS.md
│   ├── WILDLIFE_OBSERVER_CHECKLIST.md
│   ├── EQUIPMENT_PROFILE.md
│   └── archive/
│       └── thermal_investigation/
│           ├── THERMAL_INVESTIGATION_REVIEW.md
│           ├── THERMAL_CALIBRATION_INVESTIGATION.md
│           ├── THERMAL_EXPERT_REVIEW_REQUEST.md
│           ├── RADIOMETRIC_INTEGRATION.md
│           ├── FIELD_SOP.md
│           ├── FIELD_DEPLOYMENT_GUIDE.md
│           └── notes.md
│
├── scripts/
│   ├── run_lidar_hag.py                 # ✅ Production
│   ├── run_thermal_ortho.py             # ✅ Production
│   ├── validate_thermal_extraction.py   # ✅ Production
│   ├── visualize_thermal_detections.py  # ✅ Production
│   ├── validate_environment.sh          # ✅ Production
│   ├── optimize_thermal_detection.py    # 📝 To be created
│   ├── run_thermal_detection_batch.py   # 📝 To be created
│   ├── run_fusion_join.py               # 📝 To be created
│   ├── generate_client_report.py        # 📝 To be created
│   └── archive/
│       ├── thermal_prototypes/
│       │   ├── test_thermal_detection.py
│       │   ├── test_thermal_detection_simple.py
│       │   ├── test_thermal_detection_0353.py
│       │   ├── test_thermal_detection_enhanced.py
│       │   ├── test_thermal_local_deltaT.py
│       │   └── investigate_thermal_calibration.py
│       ├── test_thermal_minimal.sh
│       └── test_thermal_verified_frame.sh
│
├── verification_images/
│   ├── README.md
│   ├── Penguin Count - 7 Photos.pdf
│   ├── frame_0353_locations.csv   # ✅ Complete
│   ├── frame_0354_locations.csv   # ❌ TODO
│   ├── frame_0355_locations.csv   # ✅ Complete
│   ├── frame_0356_locations.csv   # ✅ Complete
│   ├── frame_0357_locations.csv   # ❌ TODO
│   ├── frame_0358_locations.csv   # ❌ TODO
│   └── frame_0359_locations.csv   # ❌ TODO
│
└── data/
    ├── interim/
    │   └── archive/               # Old test outputs moved here
    └── ...
```

---

## Execution Checklist

- [ ] Create archive directories
- [ ] Move supplementary docs to archive
- [ ] Move THERMAL_INVESTIGATION_FINAL.md to docs/
- [ ] Remove empty docs/supplementary/ directory
- [ ] Move prototype scripts to archive
- [ ] Create README.md
- [ ] Update STATUS.md (remove BLOCKER language)
- [ ] Update RUNBOOK.md (add full-dataset sections)
- [ ] Archive old interim test outputs
- [ ] Verify all links in documentation still work
- [ ] Update CONTRIBUTING.md if needed (reference to NEXT_STEPS.md)

---

## Estimated Time: 1-2 hours

Most of this is file moves and documentation updates. Low risk.

---

## Notes

- **Don't delete anything** - move to archive instead
- **Verify links** - many docs cross-reference each other
- **Keep git history** - use `git mv` instead of `mv` if repo is tracked
- **Test after cleanup** - ensure `make test` still works
