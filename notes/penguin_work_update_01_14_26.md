# Penguin Project Update (Jan 14, 2026\) {#penguin-project-update-(jan-14,-2026)}

TOC

## Table of Contents

1. [Recap of updates since Nov 2025](#1-recap-of-updates-since-nov-2025)
    - [November: Pipeline Foundation and Guardrails](#november-pipeline-foundation-and-guardrails)
    - [December (Limited Time): Correctness and Core Pipeline Work](#december-limited-time-correctness-and-core-pipeline-work)
    - [January: AOI Evaluation, Label Sampling, and Documentation](#january-aoi-evaluation-label-sampling-and-documentation)
2. [Practical Status](#practical-status)
3. [Current Blockers and AOI Evidence](#current-blockers-and-evidence-aoi)
4. [Where the Project Can Go From Here (End of Phase Plan)](#2-where-the-project-can-go-from-here)
5. [Notes to Verify from the Nov 23 Meeting](#3-notes-to-verify-from-the-nov-23-meeting)
6. [Improving LiDAR Detections Beyond Blob Candidates](#4-improving-lidar-detections-beyond-blob-candidates)

—- 

## **1\) Recap of updates since Nov 2025** {#1)-recap-of-updates-since-nov-2025}

### **November: pipeline foundation and guardrails** {#november:-pipeline-foundation-and-guardrails}

- Standardized pipeline entry points for LiDAR, thermal, fusion, and golden tests.  
- Added an environment validation script and refreshed the runbook.  
- Updated data provenance in the harvest manifest.  
- Refreshed the LiDAR golden AOI (area of interest) baseline and related docs.

### **December (limited time): correctness and core pipeline work** {#december-(limited-time):-correctness-and-core-pipeline-work}

- Clarified the boundary between quality control (QC) milestones and scientific validity.  
- Strengthened coordinate reference system (CRS) checks and improved thermal georeferencing tools.  
  - Georeferencing/alignment maps thermal pixels into map coordinates; calibration makes temperatures physically meaningful.  
- Built an initial fusion step that can join LiDAR and thermal detections when they share the same map coordinates.  
- Improved reproducibility of LiDAR detection and expanded tests.  
- Updated the thermal camera model parsing with supporting notes.  
- Added Argentina analysis utilities and status reports (see `CLIENT_STATUS_REPORT_2025-11-20.md`).

### **January: AOI evaluation, label sampling, and documentation** {#january:-aoi-evaluation,-label-sampling,-and-documentation}

- Added tools to evaluate detections inside AOIs and export label samples for manual review.  
- Added LiDAR profile/config support for repeatable runs.  
- Tightened requirements and Makefile targets; improved `.gitignore`.  
- Refreshed `README.md`, `RUNBOOK.md`, and `docs/reports/STATUS.md`, plus the LiDAR assessment report.
- Generated shareable static QC maps with provenance + CRS + parameters embedded:
  - Caleta Small Island AOI-clipped candidate map (`qc/panels/static_maps/caleta_small_island_detections.png`): 1,255 candidates inside AOI vs 1,557 field count (candidate/field ratio 0.81; “recall” is provisional because AOI is LiDAR-derived).
  - Caleta Tiny Island AOI-clipped candidate map (`qc/panels/static_maps/caleta_tiny_island_detections.png`): 315 candidates inside AOI vs 321 field count (candidate/field ratio 0.98; “recall” is provisional because AOI is LiDAR-derived).
  - San Lorenzo full-scene AOI comparison overlay (`qc/panels/static_maps/san_lorenzo_aoi_comparison.png`): 16,965 total candidates with 2 approximate AOIs overlaid; inside-AOI candidate counts are 263 (Caves) and 86 (Plains). (AOI boundaries are approximate; candidates are not validated penguins.)

### **Practical status** {#practical-status}

- LiDAR: reproducible pipeline with guardrails, AOI-based evaluation, and label sampling for manual checks.  
  - AOI evaluation yields AOI-clipped candidate counts (and optional density), not recall/accuracy metrics.  
- Fusion: a working join by location, but still limited by thermal georeferencing.  
- Thermal: extraction and camera model work is in place, but calibration remains the main scientific blocker. Also need updated 2025 thermal data.

### **Current blockers and evidence (AOI)** {#current-blockers-and-evidence-(aoi)}

AOI boundaries are the main blocker for defensible comparisons. Below is a snapshot from the AOI-clipped draft (`docs/reports/LIDAR_VALIDATION.md`). These are **candidate counts**, not accuracy metrics.

| AOI | Field Count | LiDAR Candidates | Candidate/Field Ratio |
| :---- | ----: | ----: | ----: |
| San Lorenzo Caves | 908 | 263 | 0.29 |
| San Lorenzo Plains | 453 | 86 | 0.19 |
| Caleta Small Island | 1,557 | 1,255 | 0.81 |
| Caleta Tiny Island | 321 | 315 | 0.98 |

Notes:

- San Lorenzo AOIs are derived from GPS waypoint notes and show area mismatches vs reported areas.  
- Caleta island AOIs are derived from LiDAR coverage and are closer to reported areas, but shoreline/tide ambiguity still matters.  
- Missing AOIs: San Lorenzo Road (359) and Box Counts (32, 55; total 87), plus Caleta Box Counts (8, 12; total 20).  
- Need from client/field team: digitized polygon boundaries or annotated imagery showing exactly what areas were counted.

## **2\) Where the project can go from here** {#2)-where-the-project-can-go-from-here}

* *this phase wraps in about two weeks?*


Near-term focus (deliverables I can finish before wrap-up):

- Define and publish the detection meaning (candidate blobs vs confirmed penguins) in `pipelines/contracts.py` and in reports.  
- Produce one AOI package with an AOI polygon file, provenance/hash, overlay figure, AOI-based candidate counts, and caveats for external sharing.  
- Choose and document the official LiDAR profile used for reporting (deterministic settings).  
- Export a labeled sample and compute a first precision estimate inside a validated AOI.  
- Run thermal analysis with new data …?

Decisions to make with the team:

- Pick one site/AOI for the next validation pass.  
- Define what counts as a "validated AOI" (who signs off and which artifacts make it official).  
- Decide whether the next thermal milestone is alignment/QC (geometry) or calibration (temperature accuracy).  
- Confirm how we want to report LiDAR results in areas with caves/burrows.

Key risks to flag:

- AOI alignment is required before any "detected vs field count" claim is defensible.  
- The San Lorenzo Road count (359) has no boundary waypoints, so it cannot be evaluated yet.  
- Thermal and LiDAR were often collected on different days (needs confirmation from flight logs/timestamps), which limits fusion validation to same-day sites.

## **3\) Notes to verify from the Nov 23 meeting** {#3)-notes-to-verify-from-the-nov-23-meeting}

These points came from rough meeting notes and should be treated as tentative until confirmed with the field team.

- Ground truth counts may be tied to hand-drawn boundaries ("inside the squiggly is the total count"). If those annotated maps exist, they could be digitized into AOIs.  
- Ground truth was collected during the day; thermal flights may have happened at different times or on different days.  
- Thermal and LiDAR were often flown on different days, except for box count areas (needs confirmation from flight logs/timestamps). That would limit any fusion validation to same-day sites.  
- Time synchronization might be off, which could affect thermal calibration and detection performance.  
- Field processing may use LP360 (GeoCue) rather than DJI Terra, which could change classification conventions or intensity behavior.  
- Intensity might be a useful signal (penguin feathers reflect less at 905 nm), but it needs a quick QC study before use.  
- CloudCompare could be a free option for intensity/QC visualization.  
- EarthRanger was mentioned as a possible downstream platform, but needs a scoped evaluation to confirm fit.

## **4\) Improving LiDAR detections beyond blob candidates** {#4)-improving-lidar-detections-beyond-blob-candidates}

Anticipated path:

1) Lock the detection definition. Treat the current output as "candidate blobs" unless a promotion rule is stated, and make this explicit in the contract and client-facing language.  
2) Require AOI alignment for validation. Only compare to field counts within validated AOI polygons, and store the AOI artifact alongside results so the comparison is reproducible.  
3) Use a deterministic, documented LiDAR profile. Select a single configuration for reporting and mark all other runs as exploratory.  
4) Measure precision with labeled samples. Export a stratified sample within AOI, label a small set (50-100), and report precision with an uncertainty note.  
5) Add a simple scoring rule (optional, low overhead). Turn existing features (height, area, shape, slope) into a score and threshold so decisions stay transparent without full machine learning.  
6) Explore intensity as an extra signal (optional). If intensity is reliable across sensors, it may help separate penguins from rock/guano, but it needs a small QC study before use in reporting.  
7) Consider machine learning only after label scale-up. A classifier is feasible, but it requires more labeled data and careful cross-site validation.
