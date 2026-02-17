# DORA 2025 Integration Summary

How this penguin pipeline embodies DORA best practices for AI-assisted solo development.

---

## The 7 AI Capabilities — Our Implementation

### 1. Clear AI Stance ✅
**DORA:** Define AI tool usage, boundaries, and review rules.

**We do:**
- PRD Section 16 - Agent constraints codified
- Pre-commit hooks prevent legacy data modification

### 2. Healthy Data Ecosystem ✅
**DORA:** Clean, versioned, well-organized data with clear provenance.

**We do:**
- `manifests/harvest_manifest.csv` - SHA256 + provenance tracking
- Read-only legacy mounts (`data/legacy_ro/`)
- Confidence scoring (field/vendor/peer/LLM)
- `.gitignore` prevents accidental data commits

### 3. AI-Accessible Internal Data ✅
**DORA:** Wire AI into codebase with proper context.

**We do:**
- `CLAUDE.md` - Single source of truth for project specifications
- `RUNBOOK.md` - Authoritative commands
- `manifests/harvest_notes.md` - Searchable legacy findings

### 4. Strong Version Control ✅
**DORA:** Frequent commits, reversible changes, branch protection.

**We do:**
- Git repository with descriptive commits
- No silent parameter changes policy
- Pre-commit hooks for quality gates
- Rollback capability (`make rollback`)

### 5. Small Batches ✅
**DORA:** Tiny PRs, fast cycles, low blast radius.

**We do:**
- Golden AOI - minimal testable dataset first
- Track A/B decision gates - fail fast
- Stage-by-stage pipeline (harvest → lidar → thermal → fusion)
- Each Makefile target is independently runnable

### 6. User-Centric Focus ✅
**DORA:** Start with user scenarios and measurable outcomes.

**We do:**
- 48h zoo readout - concrete deliverable
- 72h Argentina readout - time-boxed commitment
- QC gates with RMSE thresholds
- Client communication templates in PRD

### 7. Quality Internal Platform ✅
**DORA:** One-touch test/deploy, reproducible environments.

**We do:**
- `requirements.txt` - Pinned dependencies (venv-based)
- `Makefile` - One-command pipeline execution
- `make smoke` - Fast feedback (< 2 min)
- `make golden` - Full reproducible pipeline

---

## DORA Four Keys Tracking

### How We Measure

**File:** `manifests/delivery_metrics.csv`
**Command:** `make metrics`

### Metrics Captured

1. **Deployment Frequency**
   - Every `make golden` success = deployment
   - Target: Daily during development

2. **Lead Time**
   - Time from "start implementation" to "golden AOI passes"
   - Tracked in CSV: `lead_time_min` column
   - Current: 720 min (12 hours) for initial setup

3. **Change Failure Rate**
   - % of pipeline runs that fail QC gates
   - Logged in `manifests/incidents.md`
   - Target: < 15% (DORA high performer benchmark)

4. **Time to Restore**
   - Minutes from incident detection to `make rollback` success
   - Tracked in incidents log
   - Target: < 60 minutes

---

## Stability Tax Payment (DORA Warning: AI Increases Change Volume)

### What We Built to Prevent Chaos

1. **Golden AOI Smoke Tests** (`tests/test_golden_aoi.py`)
   - Fast: < 5 min local runtime
   - Assertions: File existence, candidate counts, reproducibility
   - Run on every change before production

2. **Pre-commit Quality Gates** (`.pre-commit-config.yaml`)
   - Ruff linting + formatting
   - Prevent large file commits
   - Block legacy data modifications
   - Detect private keys

3. **Provenance Locks**
   - SHA256 checksums on all imports
   - No overwrites without explicit approval
   - Harvest manifest tracks all data lineage

4. **Rollback Safety Net**
   - `make rollback` restores last known-good
   - `.rollback/` directory preserved after each golden run
   - Incident log tracks restore time

---

## AI-Accelerated Workflows

### What AI Does Well (with guardrails)
- ✅ Generate wrapper scripts from PRD specs
- ✅ Parse legacy docs for metadata extraction
- ✅ Draft QC reports with statistics
- ✅ Debug errors and propose fixes
- ✅ Create test suites for golden AOI

### What Humans Must Do
- 🔒 Validate QC thresholds (domain knowledge)
- 🔒 Approve parameter changes (field-tested)
- 🔒 Review client communications
- 🔒 Set capture SOP (safety-critical)
- 🔒 Final sign-off on outputs before delivery

---

## Value Stream Map

```
Idea → PRD → PLAN → Code → Golden AOI Test → QC Review → Production Run → Client Readout
  ↑                              ↓ FAIL                                         ↓
  └────────────────── Incident → Rollback ──────────────────────────────────────┘
```

**Bottlenecks Addressed:**
1. ~~Finding working code~~ → Harvest manifest + documented legacy scripts
2. ~~Environment setup~~ → Pinned requirements.txt + Makefile
3. ~~QC validation~~ → Automated golden AOI tests
4. ~~Recovery from failures~~ → One-command rollback

---

## Weekly Improvement Cadence

### Monday: Plan
- Review DORA metrics from previous week
- Identify slowest stage in value stream
- Set 1-2 improvement targets

### Tuesday-Thursday: Execute
- Implement changes in small batches
- Run `make smoke` after each change
- Update incidents log if failures occur

### Friday: Validate
- Run `make golden` on full pipeline
- Compare metrics to baseline
- Update `manifests/qc_report.md`

### Weekend: Production
- Zoo/Argentina data capture
- Execute pipeline with frozen parameters
- 48-72h readout delivery

---

## Success Criteria (DORA-Aligned)

### We're winning if:
1. ✅ **Deployment Frequency** increases (more golden AOI runs)
2. ✅ **Lead Time** decreases (faster idea → validated output)
3. ✅ **Change Failure Rate** stays < 15% (stability maintained)
4. ✅ **Time to Restore** < 60 min (fast recovery)
5. ✅ Client readouts delivered on time (48h zoo, 72h Argentina)

### Red flags:
- ⚠️ Golden AOI tests start flaking
- ⚠️ Lead time increases despite AI assistance
- ⚠️ Parameters drift without documentation
- ⚠️ Rollbacks take > 1 hour

---

## Emergency Protocol

If AI-generated code breaks the pipeline:

1. **Stop:** Halt all processing immediately
2. **Rollback:** `make rollback` to last known-good
3. **Validate:** `make golden` to confirm restoration
4. **Log:** Add incident to `manifests/incidents.md`
5. **Learn:** Update project policies to prevent recurrence

**Target time to restore:** < 30 minutes

---

## Quote from DORA 2025

> "Work in small batches with strong rollbacks and smoke tests. That's the pressure-valve that turns AI speed into durable momentum rather than chaos."

**We embody this by:**
- Small batches: Stage-by-stage pipeline, golden AOI first
- Strong rollbacks: `make rollback` with .rollback snapshots
- Smoke tests: `tests/test_golden_aoi.py` runs in < 5 min

---

## Next Evolution

As the project matures:
1. Add CI/CD (GitHub Actions) running `make golden` on PRs
2. Expand smoke tests to cover thermal + fusion stages
3. Create `notes/delivery-metrics-YYYY-MM.md` monthly summaries
4. Implement automated QC threshold tuning with validation

---

Last updated: 2025-10-08
Next review: After zoo deployment (2025-10-12)
