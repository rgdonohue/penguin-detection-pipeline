# Workstreams: QC/Engineering vs Scientific Validity

This project has two kinds of “done”:

1. **QC / Engineering Done**: the pipeline runs end-to-end with deterministic, CRS-aware artifacts that let us validate geometry and contracts.
2. **Scientifically / Field-Valid Done**: the outputs are *numerically trustworthy for counting* (calibration + validation against real control points / ground truth).

Conflating these has been a repeated source of confusion. This document is the shared policy for how we plan, label, and communicate progress.

---

## Definitions

### QC / Engineering Milestone
Work that improves correctness, determinism, schemas, CRS labeling, and runnable workflows **without claiming** temperature accuracy or biologically meaningful counts.

Examples:
- “Fusion aligns thermal detections to LiDAR candidates in CRS space”
- “We reject CRS mismatches”
- “Outputs are deterministic and schema-stable”

### Scientific / Field-Valid Milestone
Work that makes thermal-derived temperatures and thresholds reliable enough to support counting, and demonstrates that reliability on real data.

Examples:
- “Thermal calibration validated against DJI TA3 exports / field references”
- “Orthorectified products align to control points at ≤2 px RMSE”
- “Thermal detection achieves target F1 on annotated frames”

---

## Non-Negotiables (applies to both workstreams)

- **Do not modify** anything under `data/legacy_ro/`.
- **Determinism**: identical inputs must yield identical outputs (stable ordering; no timestamps in blessed artifacts).
- **CRS explicitness**: projected coordinates must always have an explicit CRS; never silently mix pixel and CRS coordinates.
- **Sources of truth**:
  - Tasks: `notes/pipeline_todo.md`
  - Current state: `docs/reports/STATUS.md`
  - Commands: `RUNBOOK.md`

---

## Output Labeling Rules (prevent “ran” from implying “valid”)

Any artifact intended for review should be labeled with:

- `purpose`: one of `qc_alignment`, `research_exploration`, `scientific_counting`
- `crs`: e.g. `EPSG:32720` (when using projected meters)
- `temperature_calibrated`: boolean

Rules:
- QC/fusion runs **must** set `purpose=qc_alignment` and `temperature_calibrated=false` unless calibration is validated.
- Any report that includes counts derived from thermal thresholds must be labeled `scientific_counting` and cite the calibration method + validation set.

---

## Work Plan While Waiting For New Client Thermal Imagery

### Track A — QC / Engineering (do now)

1. **Schema/CRS contracts**
   - Define stable summary JSON schemas (versioned) for LiDAR, thermal, and fusion.
   - Enforce CRS mismatch rejection in fusion inputs.

2. **Thermal pixel→CRS scaffolding**
   - Implement pixel→CRS conversion for detections from orthorectified GeoTIFFs using the raster geotransform.
   - Provide unit tests with synthetic transforms.

3. **Fusion-as-QC**
   - Make the fusion stage runnable and clearly labeled as QC.
   - Add minimal end-to-end contract tests with synthetic fixtures (not real imagery).

4. **Golden harness decision**
   - Decide whether `pipelines/golden.py` becomes a wrapper around existing guardrails or is formally deprecated.
   - Remove ambiguity: no “stub that looks real”.

### Track B — Scientific / Field-Valid (blocked on new imagery)

1. **Thermal calibration**
   - Resolve the ~9°C offset (and any other offsets) with a documented, testable method.

2. **Camera model accuracy harness**
   - Validate orthorectification geometrically using control points (LRF targets / known ground points) and report RMSE.

3. **Ground truth georeferencing scope**
   - Argentina field counts are region totals; decide whether validation is region-based (polygons/densities) or point-based.

---

## Update Protocol

- Update `notes/pipeline_todo.md` after finishing any milestone (QC or Scientific).
- If a milestone changes a user-facing command, update `RUNBOOK.md` in the same change.
- If a milestone changes a baseline, record it in `manifests/incidents.md` / `manifests/delivery_metrics.csv`.

