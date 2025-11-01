# Repository Guidelines

## Project Structure & Module Organization
Keep the layout aligned with `PRD.md`. Library-style pipeline logic belongs in `pipelines/`, while thin CLI wrappers live in `scripts/`. Harvested inputs flow from `data/legacy_ro/` (read-only) into `data/intake/` with hashes recorded in `manifests/harvest_manifest.csv`; intermediate and blessed outputs go to `data/interim/` and `data/processed/`. QC panels land under `qc/panels/`, and reproducibility checks plus fixtures live in `tests/`. Update `RUNBOOK.md` whenever you add or retire a blessed command.

## Build, Test, and Development Commands
Set up the environment via `requirements.txt` (`make env && source .venv/bin/activate`). The Makefile targets called out in `PRD.md` are the authoritative interface: `make harvest`, `make lidar`, `make thermal`, `make fusion`, and `make golden`. For iterative debugging you may invoke stage wrappers directly, e.g.
```bash
python scripts/run_lidar_hag.py \
  --tiles data/intake/golden/cloud3.las \
  --out-dir data/processed/lidar --plots --rollup
```
Always rerun the golden AOI guardrail with `python -m pytest -q tests/test_golden_aoi.py` before shipping changes.

## Coding Style & Naming Conventions
Target Python 3.11, four-space indentation, and snake_case for modules, files, functions, and variables; reserve PascalCase for dataclasses or typed containers. Keep stage parameters and IO contracts encapsulated inside `pipelines/<stage>.py`, exposing a single `run()` entry point that the script imports. Run `ruff check` and `ruff format`; add type hints and short docstrings noting inputs, side effects, and outputs.

## Testing Guidelines
Place unit and integration tests beside the stage they exercise; name files `test_<stage>.py` and keep fixtures in helper modules suffixed `_fixtures.py`. Golden AOI tests must assert the presence, schema, and hashes (when available) of outputs such as `candidates.gpkg`, `rollup_counts.json`, and QC PNGs. Add regression coverage whenever parameters, schemas, or filenames change, and mirror new QC metrics in `manifests/qc_report.md`.

## Commit & Pull Request Guidelines
Write concise, imperative commit subjects (`stage: action`, e.g. `lidar: clamp hag thresholds`) and include provenance notes (legacy source path, SHA) in the body when harvesting. Every PR should: (1) link the tracked task or issue, (2) summarize parameter or schema changes, (3) attach before/after QC thumbnails when relevant, and (4) confirm `make golden` plus pytest ran cleanly. Never commit harvested data—reference manifest entries instead.

## Security & Data Handling
Treat `data/legacy_ro/` as immutable. Copy artifacts through harvesting scripts only, populate `manifests/harvest_manifest.csv` with SHA256 and size, and keep credentials or API tokens out of the repo. Scrub logs before sharing externally and note any sensitive paths in PR descriptions.
