# AI Collaboration Policy — Penguin Detection Pipeline

Based on DORA 2025 AI Capabilities Model, adapted for solo development with AI assistance.

## Core Principle

**AI is an amplifier:** It speeds up clean workflows and multiplies messy ones. This policy ensures AI assistance amplifies quality, not chaos.

---

## Allowed AI Activities

### 1. Code Generation & Modification
- **Allowed:** Generate new scripts, wrapper functions, test code
- **Allowed:** Propose parameter sweeps, optimization suggestions
- **Allowed:** Draft documentation, QC reports, markdown files
- **Allowed:** Create data processing pipelines following PRD specifications
- **Required:** All generated code must be reviewed before execution on real data

### 2. Data Analysis
- **Allowed:** Analyze outputs (JSON, CSV, plots) and summarize findings
- **Allowed:** Suggest regex patterns for harvest manifest rules
- **Allowed:** Parse legacy documentation for metadata extraction
- **Allowed:** Generate QC statistics and visualizations

### 3. Problem Solving
- **Allowed:** Debug errors, propose fixes, suggest alternative approaches
- **Allowed:** Research geospatial libraries and best practices
- **Allowed:** Optimize performance bottlenecks

---

## Forbidden AI Activities

### 1. Data Integrity
- **NEVER:** Modify files in `data/legacy_ro/` (read-only boundary)
- **NEVER:** Overwrite existing `dest_path` with different SHA256 without explicit approval
- **NEVER:** Generate synthetic data and pass it as real field data

### 2. Parameter Changes
- **NEVER:** Silently change parameters outside `RUNBOOK.md` without discussion
- **NEVER:** Apply "autofix" transforms on geodata without validation
- **NEVER:** Modify capture SOP parameters without field testing

### 3. Provenance
- **NEVER:** Skip checksum calculation when copying legacy artifacts
- **NEVER:** Remove entries from harvest manifest
- **NEVER:** Alter timestamps or confidence scoring without justification

---

## AI-Human Collaboration Protocol

### Before Implementation
1. AI proposes approach with rationale
2. Human reviews against PRD constraints
3. For novel approaches: prototype on golden AOI first
4. For parameter changes: justify with docs/papers or propose A/B test

### During Implementation
1. AI generates code with inline comments explaining choices
2. Human reviews diff, checks against QC gates
3. Run on golden AOI before production data
4. Track changes in git with descriptive commit messages

### After Implementation
1. AI generates QC report with metrics
2. Human validates outputs against acceptance criteria
3. Update harvest manifest with provenance
4. Document lessons learned in `manifests/qc_report.md`

---

## Quality Gates for AI-Generated Code

1. **Reproducibility:** Same inputs → same outputs across runs
2. **Provenance:** All data transformations logged with checksums
3. **Testability:** Golden AOI test passes before production use
4. **Readability:** Code is documented, not obfuscated
5. **Reversibility:** Changes can be rolled back cleanly

---

## DORA Four Keys Tracking

Track these metrics from git and QC reports:

1. **Deployment Frequency:** How often do we update pipeline scripts?
2. **Lead Time:** Time from "need change" to "validated on golden AOI"
3. **Change Failure Rate:** % of runs that fail QC gates
4. **Time to Restore:** How fast can we rollback to last working version?

Target: Minimize Change Failure Rate before optimizing speed.

---

## When NOT to Use AI

1. **Critical decisions about data validity** - Requires domain expertise
2. **Setting QC thresholds** - Based on field observations, not optimization
3. **Client communication** - Requires human judgment and accountability
4. **Hardware SOP modifications** - Safety-critical, needs field validation

---

## Review Cadence

- **Daily:** Review AI-generated code before committing
- **After each stage:** Validate QC outputs match expected format
- **Before zoo/Argentina:** Full pipeline review of all AI-contributed code

---

## Emergency Rollback

If AI-generated code causes data corruption or invalid results:

1. Stop pipeline immediately
2. Revert to last known-good commit
3. Re-run golden AOI test to validate rollback
4. Document incident in `manifests/incidents.md`
5. Review AI policy for gaps

---

## Success Criteria

This policy succeeds if:
- ✅ We ship faster WITHOUT more bugs
- ✅ All outputs are reproducible and provenance-tracked
- ✅ QC gates catch issues before production
- ✅ Rollbacks are fast and complete

---

> **Principle:** "Work in small batches with strong rollbacks and smoke tests." — DORA 2025

Last updated: 2025-10-08
