# Script Review Triage (LiDAR → Thermal → Fusion)

This note captures a repeatable way to identify which scripts/modules to audit first, plus a ranked “review-first” list for this repository.

## How the ranking works

Prioritize code based on *what actually runs* and *what is riskiest*:

1) **Execution impact**
- Referenced by `Makefile`, `RUNBOOK.md`, or `README.md`
- Entrypoints (`scripts/run_*.py`, top-level `*.sh`)
- Stage APIs (`pipelines/<stage>.py`)

2) **Risk signals**
- CRS/geo transforms, joins, unit conversions
- Shelling out (`subprocess`, `shell=True`)
- Deletes/overwrites outputs (e.g., `rm -rf`, `unlink`, `rmtree`)

3) **Complexity**
- Large files (LOC buckets) get a small bump because they hide more edge cases.

The table below is sorted in the desired audit order: **LiDAR → Thermal → Fusion → cross-cutting**.

## Ranked “review-first” table

| Priority | Stage | File | Score | LOC | Why |
|---:|---|---|---:|---:|---|
| 1 | LiDAR | `scripts/run_lidar_hag.py` | 45 | 863 | Makefile, RUNBOOK, entrypoint, CRS/geo |
| 2 | LiDAR | `pipelines/lidar.py` | 14 | 166 | stage API, subprocess |
| 3 | LiDAR | `pipelines/utils/provenance.py` | 11 | 86 | stage API |
| 4 | LiDAR | `scripts/create_detection_map.py` | 7 | 306 | CRS/geo |
| 5 | Thermal | `scripts/run_thermal_ortho.py` | 35 | 283 | RUNBOOK, entrypoint, CRS/geo |
| 6 | Thermal | `scripts/run_thermal_detection_batch.py` | 33 | 465 | RUNBOOK, entrypoint |
| 7 | Thermal | `scripts/run_thermal_smoketest.py` | 26 | 160 | Makefile, RUNBOOK, entrypoint |
| 8 | Thermal | `pipelines/thermal.py` | 20 | 1163 | stage API, CRS/geo, subprocess, deletes/writes |
| 9 | Thermal | `pipelines/thermal_crs.py` | 13 | 60 | stage API, CRS/geo |
| 10 | Thermal | `run_thermal_pipeline.sh` | 12 | 142 | entrypoint |
| 11 | Thermal | `scripts/optimize_thermal_detection.py` | 11 | 465 | RUNBOOK |
| 12 | Thermal | `scripts/mark_penguins.py` | 8 | 302 | subprocess |
| 13 | Fusion | `scripts/run_fusion_join.py` | 21 | 48 | RUNBOOK, entrypoint, CRS/geo |
| 14 | Fusion | `pipelines/fusion.py` | 13 | 176 | stage API, CRS/geo |
| 15 | Cross-cutting | `scripts/validate_environment.sh` | 28 | 6 | Makefile, RUNBOOK |
| 16 | Cross-cutting | `scripts/experiments/validate_environment.sh` | 18 | 204 | called by validate, deletes/writes |

## Suggested audit workflow

- **LiDAR first:** treat `tests/test_golden_aoi.py` as the release gate; verify determinism, schema stability, and output locations (`data/interim/`/`data/processed/`, never `data/legacy_ro/`).
- **Thermal second:** focus on radiometry scaling and CRS correctness; keep tests runnable with fixtures/synthetic arrays until updated 2025 thermal data lands.
- **Fusion third:** scrutinize CRS alignment and join semantics (units, radii, duplicate handling, deterministic output ordering).
