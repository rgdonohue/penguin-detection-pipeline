# Penguin Detection Pipeline — PRD / IMPLEMENTATION PLAN (v0.1)

**Owner:** You
**Date:** 2025-10-08
**Goal:** Stand up a clean, reproducible pipeline that (1) harvests value safely from four legacy project folders, (2) delivers a *zoo test* 48-hour readout, and (3) scales to *Argentina* data within 72 hours of capture.

---

## 1) Problem Statement

You have four R&D-heavy codebases with mixed-quality scripts, outputs, and notes generated under AI assistance. Some of it worked, much of it is unverified. We need a **single, production-oriented repo** that **reads legacy data read-only**, deterministically harvests only verified artifacts, and runs a **blessed minimal pipeline**:

1. **LiDAR → HAG candidates** (stable backbone)
2. **Thermal → DSM orthorectification** (pilot; subset)
3. **Fusion → label Both/LiDAROnly/ThermalOnly** (join + simple stats)

---

## 2) Scope & Non-Goals

### In Scope (v0.1)

* New clean repo that ingests legacy artifacts **read-only**
* Provenance-preserving **harvest** with checksums + manifest
* One **golden AOI** and **one blessed command** per stage
* LiDAR HAG detection: counts + vector outputs + QC plots
* Thermal ortho (pilot): subset projection to DSM + VRT/COGs + RMSE
* Fusion: spatial join, local thermal stats, label flags
* **48h Zoo** and **72h Argentina** readouts with fixed QC gates

### Out of Scope (v0.1)

* Full production thermal bundle-adjust for all frames
* Training ML models or deep learning
* Fancy interactive dashboards (static QC panels only)
* Editing or altering files in legacy repos

---

## 3) Success Criteria (Acceptance)

* **Provenance:** Every imported artifact has a row in `manifests/harvest_manifest.csv` with `sha256`, `size`, `src_path`, `notes`.
* **Reproducibility:** `make golden` generates identical counts and files across runs.
* **LiDAR HAG:** outputs `candidates.gpkg`, `rollup_counts.json`, `qc/panels/*png` for golden AOI.
* **Thermal Ortho (pilot):** `thermal.vrt` + `thermal/index.gpkg` with **RMSE ≤ 2 px** on control/tie points for subset.
* **Fusion:** `fusion/fusion.csv` with labels **Both/LiDAROnly/ThermalOnly** and a 3-panel QC image.
* **Turnaround:** Zoo readout ≤ 48h; Argentina first-pass readout ≤ 72h.

---

## 4) Repo Layout (authoritative)

```
penguins-pipeline/
├─ README.md
├─ PRD.md                            # this document
├─ RUNBOOK.md                        # one blessed command per stage
├─ Makefile
├─ requirements.txt                  # core dependencies (LiDAR)
├─ requirements-full.txt             # full dependencies (thermal/fusion)
├─ data/
│  ├─ legacy_ro/                     # read-only mounts/symlinks to 4 legacy dirs
│  ├─ intake/                        # harvested copies with checksums
│  ├─ interim/                       # temporary artifacts
│  └─ processed/                     # blessed outputs (COG, VRT, GPKG, CSV)
├─ manifests/
│  ├─ harvest_manifest.csv           # src→dest + sha256 + status + notes
│  ├─ md_hits.txt                    # mined hardware settings from legacy .md
│  └─ qc_report.md                   # single source of QC truth
├─ scripts/
│  ├─ harvest_legacy.py              # read-only spider + checksum + filter
│  ├─ run_lidar_hag.py               # thin wrapper → lidar_detect_penguins.py
│  ├─ run_thermal_ortho_pilot.py     # subset DSM projection + tie points + RMSE
│  └─ run_fusion_join.py             # spatial join + stats + labels
├─ pipelines/
│  ├─ lidar_hag.py                   # library-style import targets (if needed)
│  ├─ thermal_ortho_pilot.py
│  └─ fusion.py
├─ tests/
│  └─ test_golden_aoi.py
└─ qc/
   └─ panels/                        # LiDAR / Thermal / Fusion PNGs
```

**Policy:** Never modify anything in `data/legacy_ro/`. Always copy to `data/intake/` and log the event in the manifest.

---

## 5) Environments

`requirements.txt` (core dependencies, pin versions for reproducibility):

```
# LiDAR Processing (core)
laspy>=2.6.1
numpy>=2.0.2
scipy>=1.13.1
scikit-image>=0.24.0
matplotlib>=3.9.4
pytest>=8.4.2
ruff>=0.14.0
rich>=14.2.0
click>=8.1.8
```

`requirements-full.txt` (add thermal/fusion dependencies when needed):

```
-r requirements.txt
pandas>=2.3.3

# Uncomment when implementing thermal/fusion stages:
# gdal>=3.6.0
# rasterio>=1.3.0
# geopandas>=0.12.0
# fiona>=1.9.0
# shapely>=2.0.0
# pyproj>=3.4.0
```

**Setup:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`.gitignore` essentials:

```
.env
__pycache__/
*.pyc
data/intake/**
data/interim/**
data/processed/**
.qgis3/
.ipynb_checkpoints/
```

Pre-commit (optional):

```
ruff check .
ruff format .
```

---

## 6) Data Harvest (Read-Only Mining)

### Goals

* Catalog, score, and selectively copy artifacts with **deterministic rules**
* Record provenance for every import

### Allowed artifact types

`*.py, *.ipynb, *.tif, *.vrt, *.gpkg, *.geojson, *.json, *.md, flight logs`

### Discovery commands (non-destructive helpers)

```bash
# Code and notebooks with relevant terms
rg -n --glob '!**/archive/**' -e 'lidar|thermal|penguin' --files-with-matches -- *.py *.ipynb > manifests/code_hits.txt

# Mine .md for hard numbers/settings into a text log
rg -n -i --glob '!**/archive/**' -e 'overlap|altitude|emissiv|rmse|pts/m2|density|resolution|fps|gain|rtk|ppk' \
  --markdown --heading data/legacy_ro > manifests/md_hits.txt

# Inventory of artifacts
fd -e tif -e vrt -e gpkg -e geojson -e json -e png -e jpg data/legacy_ro \
  | sort | uniq -c > manifests/artifacts.txt
```

### Manifest Schema (`manifests/harvest_manifest.csv`)

Columns:

```
src_path, dest_path, sha256, size_bytes, mtime_utc, artifact_type,
discovered_by (rule/regex/manual), confidence (field/vendor/peer/LLM),
status (copied/quarantined/skipped), notes
```

### Scoring Rules

1. Prefer artifacts referenced in `.md` with `worked|passed|RMSE|counts`.
2. Require companion outputs (e.g., script + its PNG/CSV/GPKG).
3. **Confidence:**

   * `field` = observed in real data run
   * `vendor/peer` = external documentation
   * `LLM` = AI-only claim (quarantine until replicated)
4. Never overwrite existing `dest_path` with different `sha256`.

---

## 7) Pipelines (v0.1)

### 7.1 LiDAR → HAG Detector (Backbone)

**Input:** LAZ/LAS tile(s) with ground classified or derivable DEM
**Outputs:**

* `processed/lidar/candidates.gpkg` (centroids + HAG + shape stats)
* `processed/lidar/rollup_counts.json`
* `qc/panels/lidar_hag_<aoi>.png`

**Parameters (initial):**

* `--cell-res 0.5` (m)
* `--hag-min 0.3` (m), `--hag-max 0.7` (m)
* `--min-area-cells 2`, `--max-area-cells 30` (tune to ~0.2–1.0 m²)
* Optional: circularity/solidity thresholds if available

**Blessed command (example):**

```bash
python scripts/run_lidar_hag.py \
  --tiles data/intake/lidar/tile_A.laz \
  --cell-res 0.5 --hag-min 0.3 --hag-max 0.7 \
  --min-area-cells 2 --max-area-cells 30 \
  --emit-geojson --plots --rollup \
  --out-dir data/processed/lidar
```

**QC Gate:** reproducible counts across runs; produces PNG map overlay.

---

### 7.2 Thermal → DSM Orthorectification (Pilot)

**Inputs:** thermal frames + pose/gimbal + LiDAR DSM
**Outputs:**

* `processed/thermal/tiles/*.tif` (COGs)
* `processed/thermal/thermal.vrt`
* `processed/thermal/index.gpkg` (per-frame residuals, pose, tie points)
* `qc/panels/thermal_subset_<aoi>.png`

**Capture SOP (for hardware team):**

* Radiometric **ON**, **16-bit**, emissivity **0.98**, fixed gain
* Overlap **70% forward / 60% side**
* **Nadir or ≤20° oblique**, steady speed, 5–10 min warm-up
* Time-sync camera/controller; record yaw/pitch/roll
* LiDAR: RTK/PPK ON; cross-lines; target **≥150–300 pts/m²**
* Optional calibration aids: flat-field sky, cool tarp/ice packs

**CRITICAL DISCOVERY:** Full radiometric data IS encoded in thermal images, even when it appears lost. Use proper thermal image processing tools to extract it. Do NOT assume radiometric data is missing without verification.

**Blessed command (subset):**

```bash
python scripts/run_thermal_ortho_pilot.py \
  --frames data/intake/thermal/subset/*.tif \
  --poses data/intake/thermal/poses.csv \
  --dsm data/intake/lidar/dsm.tif \
  --max-tiepoints 12 --rmse-threshold 2.0 \
  --out-dir data/processed/thermal
```

**QC Gate:** control/tie-point **RMSE ≤ 2 px** on subset; index.gpkg populated.

---

### 7.3 Fusion (Join + Simple Stats)

**Inputs:** `candidates.gpkg` + `thermal.vrt`
**Outputs:** `processed/fusion/fusion.csv` (joined stats + labels), `qc/panels/fusion_<aoi>.png`

**Logic:**

* For each LiDAR candidate, sample thermal within **1–2 px** window
* Compute `thermal_mean`, `thermal_max`, `thermal_local_z` (z-score vs local neighborhood)
* Label:

  * **Both** if thermal_max or thermal_local_z exceeds tuned threshold
  * **LiDAROnly** if not
  * **ThermalOnly** reserved for future pass (thermal detections without HAG)

**Blessed command:**

```bash
python scripts/run_fusion_join.py \
  --candidates data/processed/lidar/candidates.gpkg \
  --thermal-vrt data/processed/thermal/thermal.vrt \
  --px-window 2 --out data/processed/fusion/fusion.csv \
  --qc-panel qc/panels/fusion_aoi.png
```

**QC Gate:** panel shows correspondence; file has complete rows matching candidate count.

---

## 8) Golden AOI & Tests

**Golden AOI:** one small tile + 10–30 thermal frames with decent pose

**Test:** `tests/test_golden_aoi.py` asserts:

* Output file existence (GPKG, JSON, PNG, VRT)
* Non-empty candidate count
* Re-run gives identical `rollup_counts.json`

**Makefile Targets:**

```makefile
.PHONY: env harvest golden lidar thermal fusion qc

env:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

harvest:
	python scripts/harvest_legacy.py --config manifests/harvest_rules.yml

golden: harvest lidar thermal fusion qc

lidar:
	python scripts/run_lidar_hag.py ... (as above)

thermal:
	python scripts/run_thermal_ortho_pilot.py ... (subset)

fusion:
	python scripts/run_fusion_join.py ... (as above)

qc:
	python -m pytest -q tests/test_golden_aoi.py
```

---

## 9) Triage & Inventory Templates

**Triage CSV columns (fill manually or scripted):**

```
project,path,purpose,inputs,outputs,status(✅/⚠️/❌/🔍),runtime_min,
truth_source(field/vendor/peer/LLM),risks,production_ready(Y/N)
```

**STATUS.md skeleton:**

```markdown
# Project Status (YYYY-MM-DD)

## Proven Working
- [Name] — What it does; results on golden AOI; command

## Needs Validation at Zoo
- [Name] — Why; planned gate

## Archived (Not Production-Ready)
- [Name] — Reason; link to manifest rows

## Critical Unknowns
- [Question] — How we’ll answer (zoo/Argentina)
```

---

## 10) QC Report Outline (`manifests/qc_report.md`)

* **AOI & data versions** (hashes, sizes, timestamps)
* **LiDAR HAG results** (map panel, counts, params)
* **Thermal ortho** (RMSE table, residual map, sample frame panels)
* **Fusion table** (counts by label, example overlays)
* **Performance** (runtime by stage on machine specs)
* **Recommendations** (tuning, capture adjustments)

---

## 11) Decision Gates & Tracks

**Gate 1 — Today:**

* LiDAR HAG smoke test on golden AOI passes (deterministic outputs) → **Track A**
* Else → **Track B**

**Track A (HAG green; DSM/pose usable):**

* Proceed with thermal pilot + fusion for zoo (subset)
* Zoo readout includes LiDAR counts + thermal RMSE + fusion labels

**Track B (HAG wobbly OR DSM/pose missing/iffy):**

* Ship **LiDAR-only** baseline for zoo & Argentina
* Thermal is **Phase 2** pending pose fidelity + RMSE ≤ 2 px + time

---

## 12) Timeline & Deliverables

**Today (Wed)**

* Create repo scaffold; mount legacy → `data/legacy_ro/`
* Run harvest (dry-run then real); produce `harvest_manifest.csv`
* Smoke test LiDAR HAG on golden AOI; update `STATUS.md`
* Send **Hardware SOP** (capture checklist)

**Thu–Fri**

* Thermal pilot on subset; compute RMSE; build `thermal.vrt`
* Fusion join; draft Zoo **48h readout** template

**Weekend (Zoo)**

* Capture per SOP; ingest immediately
* Run `make golden`; populate QC panels; ship **48h readout**

**Argentina (later this month)**

* Day 0: ingest + quicklook VRT + LiDAR rollup
* Day 1: fusion on 1–2 AOIs
* Day 2: **72h readout** + scale recommendation

**Deliverables**

* `processed/lidar/candidates.gpkg`, `rollup_counts.json`, LiDAR QC PNG
* `processed/thermal/thermal.vrt`, `index.gpkg`, Thermal QC PNG
* `processed/fusion/fusion.csv`, Fusion QC PNG
* `manifests/qc_report.md` (one-pager for client)

---

## 13) Client Comms (pasteable)

**Subject:** Zoo test flight settings + 48-hour readout plan
**Body:**
For this weekend’s zoo test, please use the attached checklist. Key items: thermal **radiometric ON (16-bit)**, emissivity **0.98**, fixed gain, **70%/60% overlap**, nadir or ≤20°, **5–10 min warm-up**, and time-sync with GNSS/IMU; LiDAR with **RTK/PPK**, cross-lines, target **≥150–300 pts/m²**.
We will deliver a **48-hour readout**: LiDAR candidate counts and maps, thermal alignment RMSE (if applicable), and a fusion table (**LiDAR-only / Thermal-only / Both**). Findings will drive any parameter tweaks before Argentina.

---

## 14) Risks & Mitigations

* **Pose/metadata gaps (thermal):** Mitigation = tie-points + subset pilot; document RMSE; don’t block LiDAR.
* **Environment drift:** Mitigation = pinned requirements.txt, Makefile targets, CI test.
* **Provenance collapse:** Mitigation = read-only legacy; harvest manifest with checksums.
* **Time crunch:** Mitigation = Track B fallback (LiDAR-only) with honest gates.

---

## 15) RUNBOOK (authoritative commands)

Populate `RUNBOOK.md` with the exact, copy-runnable commands you will actually use (examples above). This file is the **single source of truth** for Claude/Codex agents.

---

## 16) Where AI Agents May Assist (and must not)

**Allowed:**

* Propose harvest regex rules; summarize `md_hits.txt` into a table
* Draft docs; suggest parameter sweeps; generate plots from outputs

**Forbidden:**

* Modifying files in `data/legacy_ro/`
* Silent parameter changes outside `RUNBOOK.md`
* Non-deterministic “autofix” transforms on geodata

---

## 17) Glossary (short)

* **HAG:** Height Above Ground from LiDAR (DEM-normalized point heights)
* **DSM:** Digital Surface Model (terrain + objects)
* **COG:** Cloud-Optimized GeoTIFF
* **VRT:** GDAL Virtual Raster Mosaic
* **RMSE:** Root Mean Square Error (pixels), control/tie point residual

---

### End of PRD

> Principle: **One blessed path, hard gates, perfect provenance.**
