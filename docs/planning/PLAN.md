# IMMEDIATE ACTION PLAN

## ✅ Critical Decision: Track A Confirmed!

**LiDAR detector validated:** 802 candidates detected in 12 seconds on cloud3.las
**Proceed with full pipeline** (LiDAR + Thermal + Fusion)

---

## DORA 2025 Integration (Documented, Partially Implemented)

DORA principles documented for future implementation:
- `AI_POLICY.md` - Collaboration guardrails ✅ (documented)
- `DORA_INTEGRATION.md` - Full best practices reference ✅ (documented)
- `Makefile` - Minimal working targets only ⚠️ (test-lidar works, metrics/golden don't)
- `.pre-commit-config.yaml` - Legacy data guard active ⚠️ (manifest hook disabled)
- `manifests/delivery_metrics.csv` - Manual tracking ⚠️ (1 entry, no automation)
- `manifests/incidents.md` - Manual log ⚠️ (template only)

**Reality check:** Documentation exists, automation doesn't yet. Growing incrementally per DORA "small batches" principle.

---

## COMPLETED (Wednesday 2025-10-08)

### ✅ Foundation Established
- Legacy data mounted (read-only) at `data/legacy_ro/`
- Working LiDAR detector found and copied to `scripts/run_lidar_hag.py`
- Tested: 802 detections on cloud3.las
- Documentation: PRD, CLAUDE.md, PLAN, AI_POLICY, DORA principles

### ✅ Critical Discovery
**Thermal radiometric data IS encoded in images** - previous assumptions about missing data were WRONG. Updated in PRD and CLAUDE.md.

### ⚠️ Corrective Actions (After Codex Review)
- Stripped Makefile to only working targets
- Added honest docs/reports/STATUS.md documenting what actually works
- Created RUNBOOK.md with tested commands only
- Disabled untested pre-commit hooks
- Acknowledged environment setup dependency

---

## IMMEDIATE NEXT STEPS (Small Batches)

Following DORA principle: **Working software over comprehensive tooling**

### 1. Validate Environment Setup [30 min]
```bash
# Create virtual environment (recommended)
make env
source .venv/bin/activate

# Verify it works
make test-lidar

# Expected: 802 detections
```

**Status:** ⏳ NEXT UP
**Goal:** Confirm `make test-lidar` works from clean environment
**Update:** Add results to RUNBOOK.md

### 2. Create Golden AOI Test [1 hour]
```bash
# Create basic smoke test for LiDAR detector
# File: tests/test_golden_aoi.py

# Test asserts:
# - Output JSON exists and has 802 candidates
# - GeoJSON files created
# - Plots generated
# - Reproducible across runs
```

**Status:** ⏳ TODO
**Goal:** Automated validation that LiDAR pipeline works
**Blocker:** None (script already works)

### 3. Extract One Thermal Script [2-3 hours]
```bash
# Find thermal processing in legacy
ls data/legacy_ro/penguin-2.0/scripts/ | grep thermal

# Candidates:
# - thermal_ortho.py
# - safe_thermal_rollback.py (probably not what we need)

# Copy working thermal script
# Test on subset of thermal frames
# Add to RUNBOOK.md when proven
```

**Status:** ⏳ TODO
**Goal:** Working thermal processing on subset
**Decision Point:** Track A vs Track B
  - If thermal works easily: Track A (full pipeline)
  - If thermal has issues: Track B (LiDAR-only for zoo)

### 4. Create Fusion Script OR Ship LiDAR-Only [2 hours]

**Track A Path:**
- Extract `fusion_analysis.py` from legacy
- Test on LiDAR candidates + thermal (if available)
- Add to RUNBOOK.md

**Track B Path (Fallback):**
- Skip fusion for zoo deployment
- Ship LiDAR-only counts + maps
- Document thermal as "Phase 2"

**Status:** ⏳ TODO (depends on Step 3)
**Decision:** Make at end of Thursday based on thermal results

---

## TIMELINE (Realistic)

### Thursday (2025-10-09)
- **Morning:** Validate environment, create golden AOI test
- **Afternoon:** Extract thermal script, test on subset
- **EOD Decision:** Track A (full pipeline) or Track B (LiDAR-only)

### Friday (2025-10-10)
- **Track A:** Create fusion script, test end-to-end
- **Track B:** Polish LiDAR outputs, create QC report template
- **EOD:** Working pipeline (partial or full) ready for zoo

### Weekend (Zoo Deployment)
- Capture data per hardware SOP
- Run pipeline (whichever track is ready)
- Generate 48h readout

---

## DORA-Aligned Growth Pattern

**Current state:** 1 working script (`run_lidar_hag.py`)

**Growth sequence:**
1. ✅ Script works → ✅ Copied to new repo
2. ⏳ Environment validated → Add to RUNBOOK
3. ⏳ Tests created → Add to `make test`
4. ⏳ Second script (thermal) → Add to Makefile
5. ⏳ Full pipeline → `make golden`
6. ⏳ Metrics automation → `make metrics`
7. ⏳ Rollback mechanism → `make rollback`

**Each step must be proven before moving to next.**

---

## RED FLAGS (Stop and Reassess)

- If environment setup takes > 1 hour → Something's wrong with requirements.txt
- If thermal script doesn't exist in legacy → Track B immediately
- If thermal RMSE > 5 pixels → Track B (don't block on thermal)
- If Friday EOD arrives with no working pipeline → Ship LiDAR manually

**Principle:** Ship something working beats waiting for everything perfect

---

## Summary

**What works:** LiDAR detection (802 candidates on test data)
**What's next:** Environment validation → Tests → Thermal extraction
**Decision point:** Thursday EOD (Track A vs Track B)
**Hard deadline:** Friday EOD (something working for zoo weekend)
