# Repository Guidelines

## Project Structure & Module Organization
- `pipelines/`: library-style stage wrappers (`lidar.py`, `thermal.py`, `fusion.py`, `golden.py`) used for orchestration and stable APIs.
- `scripts/`: thin CLIs and one-off utilities (e.g., `scripts/run_lidar_hag.py`, `scripts/run_thermal_smoketest.py`).
- `tests/`: pytest suite; regression guardrails live in `tests/test_golden_aoi.py`.
- `data/`: inputs/outputs. Treat `data/legacy_ro/` as immutable; write outputs to `data/interim/` (scratch) or `data/processed/` (blessed).
- `qc/` and `verification_images/`: QC panels and ground-truth/verification assets.
- `RUNBOOK.md`: “commands that actually work” reference; update when adding/retiring workflows.

## Build, Test, and Development Commands
- `make env`: create/update `.venv` and install `requirements.txt`.
- `source .venv/bin/activate`: activate the project virtualenv for local runs.
- `make validate`: run `./scripts/validate_environment.sh` (sanity checks + golden AOI smoke tests).
- `make test`: run the golden AOI test suite (requires activated venv).
- `make golden`: fast guardrail (`python -m pytest -q tests/test_golden_aoi.py`).
- `make test-lidar`: run LiDAR detection on the golden tile and emit QC outputs under `data/interim/`.
- `make thermal`: thermal smoke test (requires staged frames under `data/intake/h30t`; thermal deps are documented in `requirements-full.txt`).

## Coding Style & Naming Conventions
- Python 3.12.x baseline, 4-space indentation, `snake_case` for files/functions/variables; `PascalCase` for classes/dataclasses.
- Keep stage parameters and I/O contracts inside `pipelines/<stage>.py` (prefer a typed `run()` entry point).
- Lint/format with Ruff: `ruff check .` and `ruff format .` (or `pre-commit run --all-files`).

## Testing Guidelines
- Use pytest; keep new tests in `tests/` and name files `test_*.py`.
- When changing algorithms, parameters, schemas, or output filenames, update/extend the guardrails and rerun `tests/test_golden_aoi.py`.

## Commit & Pull Request Guidelines
- Follow the existing subject style: `<area>: <imperative>` (examples in `git log`: `lidar: …`, `qc: …`, `docs: …`, `fix: …`).
- PRs should include: intent + scope, linked issue/task, and QC evidence (plots/GeoJSON screenshots) when outputs change.
- Avoid committing large artifacts; `pre-commit` blocks files >1MB and prevents edits under `data/legacy_ro/`.

## Security & Data Handling
- Do not commit secrets (API keys, credentials) or raw survey data. Record provenance in `manifests/` and prefer deterministic, reproducible transforms.
