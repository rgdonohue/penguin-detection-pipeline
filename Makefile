# Penguin Detection Pipeline — Working Makefile
# Principle: Only include targets that actually work

.PHONY: help env validate test golden test-lidar thermal official-run fusion-sample clean

help:
	@echo "Penguin Detection Pipeline — Available Targets"
	@echo ""
	@echo "Setup:"
	@echo "  make env          - Create/update virtual environment"
	@echo "  make validate     - Validate environment + run golden AOI tests"
	@echo ""
	@echo "Working:"
	@echo "  make test         - Run golden AOI test suite"
	@echo "  make golden       - Run golden AOI guardrail (QC harness)"
	@echo "  make test-lidar   - Run LiDAR detection on sample data"
	@echo "  make official-run - Run LiDAR in official reporting mode (gated)"
	@echo "  make thermal      - Run H30T thermal smoke test on staged frames"
	@echo "  make fusion-sample - Run fusion join + thermal window sampling"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean        - Remove interim files"

# Environment setup
PYTHON ?= python3.12
OFFICIAL_DATA_ROOT ?= data/2025/Caleta Tiny Island
OFFICIAL_OUT ?= data/interim/official/lidar_official.json
OFFICIAL_AOI_ID ?= caleta_tiny_island
OFFICIAL_AOI_GEOJSON ?= data/processed/aoi_caleta_tiny_island_epsg32720.geojson
OFFICIAL_CRS_EPSG ?= 32720
OFFICIAL_DEDUPE_RADIUS_M ?= 0.5
OFFICIAL_CELL_RES ?= 0.25
OFFICIAL_HAG_MIN ?= 0.28
OFFICIAL_HAG_MAX ?= 0.48
OFFICIAL_MIN_AREA ?= 3
OFFICIAL_MAX_AREA ?= 60

FUSION_LIDAR_SUMMARY ?= data/interim/official/lidar_official.json
FUSION_THERMAL_SUMMARY ?= data/interim/thermal_smoketest.json
FUSION_THERMAL_RASTER ?=
FUSION_OUT ?= data/interim/fusion/fusion_rollup.json
FUSION_MATCH_RADIUS_M ?= 0.5
FUSION_CORE_RADIUS_M ?= 0.5
FUSION_NEIGHBORHOOD_INNER_M ?= 1.0
FUSION_NEIGHBORHOOD_OUTER_M ?= 2.0
FUSION_Z_METHOD ?= robust

env:
	@echo "Setting up virtual environment..."
	@if ! command -v "$(PYTHON)" >/dev/null 2>&1; then \
		echo "✗ $(PYTHON) not found in PATH"; \
		echo "  Install Python 3.12.x and re-run (or override: make env PYTHON=/path/to/python3.12)"; \
		exit 1; \
	fi
	@$(PYTHON) -c 'import sys; v=sys.version_info; assert (v.major,v.minor)==(3,12), f\"Expected Python 3.12, got {v.major}.{v.minor}\"'
	@if [ ! -d ".venv" ]; then \
		$(PYTHON) -m venv .venv; \
		echo "✓ Virtual environment created"; \
	else \
		.venv/bin/python -c 'import sys; v=sys.version_info; assert (v.major,v.minor)==(3,12), f\".venv is not Python 3.12 (got {v.major}.{v.minor}). Remove .venv and rerun make env.\"'; \
	fi
	@.venv/bin/pip install -q -r requirements.txt
	@echo "✓ Dependencies installed"
	@echo ""
	@echo "Activate with: source .venv/bin/activate"

# Validate environment and run tests
validate:
	@echo "Running environment validation..."
	@./scripts/validate_environment.sh

# Run golden AOI test suite (venv required)
test:
	@echo "Running golden AOI test suite..."
	@if [ ! -x ".venv/bin/python" ]; then \
		echo "Missing .venv. Run: make env"; \
		exit 1; \
	fi
	@.venv/bin/python -m pytest tests/test_golden_aoi.py -v

# Golden AOI guardrail (QC harness; does not imply calibrated thermal counts)
golden:
	@echo "Running golden AOI guardrail (QC harness)..."
	@if [ ! -x ".venv/bin/python" ]; then \
		echo "Missing .venv. Run: make env"; \
		exit 1; \
	fi
	@.venv/bin/python -m pytest -q tests/test_golden_aoi.py

# Test LiDAR detection on golden AOI (cloud3.las)
test-lidar:
	@echo "Running LiDAR HAG detection on golden AOI (cloud3.las)..."
	@tmpdir=$$(mktemp -d); \
		src=$$(python3 -c "from pathlib import Path; print(Path('data/legacy_ro/penguin-2.0/data/raw/LiDAR/cloud3.las').resolve())"); \
		if [ ! -f "$$src" ]; then echo "Missing golden AOI file: $$src"; rm -rf "$$tmpdir"; exit 1; fi; \
		ln -sf "$$src" "$$tmpdir/cloud3.las"; \
		MPLCONFIGDIR="data/interim/mplconfig" .venv/bin/python scripts/run_lidar_hag.py \
			--data-root "$$tmpdir" \
			--out data/interim/lidar_test.json \
			--cell-res 0.25 \
			--hag-min 0.2 --hag-max 0.6 \
			--min-area-cells 2 --max-area-cells 80 \
			--emit-geojson --crs-epsg 32720 --plots --strict-outputs; \
		rm -rf "$$tmpdir"
	@echo ""
	@echo "✓ LiDAR detection complete"
	@echo "  Results: data/interim/lidar_test.json"
	@echo "  GeoJSON: data/interim/lidar_hag_geojson/"
	@echo "  Plots: data/interim/lidar_hag_plots/"

thermal:
	@echo "Running thermal smoke test on staged H30T frames..."
	@.venv/bin/python scripts/run_thermal_smoketest.py \
		--input-dir data/intake/h30t \
		--selection-mode per-dir \
		--limit 0 \
		--output data/interim/thermal_smoketest.json
	@echo ""
	@echo "✓ Thermal smoke test complete"
	@echo "  Summary: data/interim/thermal_smoketest.json"

official-run:
	@echo "Running LiDAR official reporting mode..."
	@if [ ! -x ".venv/bin/python" ]; then \
		echo "Missing .venv. Run: make env"; \
		exit 1; \
	fi
	@if [ ! -d "$(OFFICIAL_DATA_ROOT)" ]; then \
		echo "Missing OFFICIAL_DATA_ROOT: $(OFFICIAL_DATA_ROOT)"; \
		exit 1; \
	fi
	@if [ ! -f "$(OFFICIAL_AOI_GEOJSON)" ]; then \
		echo "Missing OFFICIAL_AOI_GEOJSON: $(OFFICIAL_AOI_GEOJSON)"; \
		exit 1; \
	fi
	@mkdir -p "$$(dirname "$(OFFICIAL_OUT)")"
	@MPLCONFIGDIR="data/interim/mplconfig" .venv/bin/python scripts/run_lidar_hag.py \
		--data-root "$(OFFICIAL_DATA_ROOT)" \
		--out "$(OFFICIAL_OUT)" \
		--cell-res "$(OFFICIAL_CELL_RES)" \
		--hag-min "$(OFFICIAL_HAG_MIN)" --hag-max "$(OFFICIAL_HAG_MAX)" \
		--min-area-cells "$(OFFICIAL_MIN_AREA)" --max-area-cells "$(OFFICIAL_MAX_AREA)" \
		--crs-epsg "$(OFFICIAL_CRS_EPSG)" \
		--dedupe-radius-m "$(OFFICIAL_DEDUPE_RADIUS_M)" \
		--aoi-id "$(OFFICIAL_AOI_ID)" \
		--aoi-registry manifests/aoi_registry.json \
		--aoi-geojson "$(OFFICIAL_AOI_GEOJSON)" \
		--official-reporting \
		--strict-outputs
	@echo "✓ Official run complete"
	@echo "  Summary: $(OFFICIAL_OUT)"
	@echo "  Manifest: $$(dirname "$(OFFICIAL_OUT)")/lidar_run_manifest.json"

fusion-sample:
	@echo "Running fusion sampling..."
	@if [ ! -x ".venv/bin/python" ]; then \
		echo "Missing .venv. Run: make env"; \
		exit 1; \
	fi
	@if [ -z "$(FUSION_THERMAL_RASTER)" ]; then \
		echo "Set FUSION_THERMAL_RASTER=/path/to/thermal.tif"; \
		exit 1; \
	fi
	@if [ ! -f "$(FUSION_LIDAR_SUMMARY)" ]; then \
		echo "Missing FUSION_LIDAR_SUMMARY: $(FUSION_LIDAR_SUMMARY)"; \
		exit 1; \
	fi
	@if [ ! -f "$(FUSION_THERMAL_SUMMARY)" ]; then \
		echo "Missing FUSION_THERMAL_SUMMARY: $(FUSION_THERMAL_SUMMARY)"; \
		exit 1; \
	fi
	@if [ ! -f "$(FUSION_THERMAL_RASTER)" ]; then \
		echo "Missing FUSION_THERMAL_RASTER: $(FUSION_THERMAL_RASTER)"; \
		exit 1; \
	fi
	@mkdir -p "$$(dirname "$(FUSION_OUT)")"
	@.venv/bin/python scripts/run_fusion_join.py \
		--lidar-summary "$(FUSION_LIDAR_SUMMARY)" \
		--thermal-summary "$(FUSION_THERMAL_SUMMARY)" \
		--out "$(FUSION_OUT)" \
		--match-radius-m "$(FUSION_MATCH_RADIUS_M)" \
		--thermal-raster "$(FUSION_THERMAL_RASTER)" \
		--thermal-core-radius-m "$(FUSION_CORE_RADIUS_M)" \
		--thermal-neighborhood-inner-radius-m "$(FUSION_NEIGHBORHOOD_INNER_M)" \
		--thermal-neighborhood-outer-radius-m "$(FUSION_NEIGHBORHOOD_OUTER_M)" \
		--thermal-z-method "$(FUSION_Z_METHOD)"
	@echo "✓ Fusion sampling complete"
	@echo "  Output: $(FUSION_OUT)"

# Clean interim files
clean:
	@echo "Cleaning interim files..."
	rm -rf data/interim/*
	@echo "✓ Interim files removed"

# TODO: Add these targets once scripts exist
# - make harvest (needs scripts/harvest_legacy.py)
# - make thermal-ortho (full orthorectification once GDAL workflow is ready)
# - make fusion (CLI exists; needs real input summaries with CRS x/y)
# - make rollback (needs snapshot mechanism)

# ---------------------------------------------------------------------------
# Experiment targets
# ---------------------------------------------------------------------------

.PHONY: experiment-ground experiment-resolution experiment-watershed experiment-hag

experiment-ground:
	@echo "Running ground model comparison experiment..."
	@.venv/bin/python scripts/experiments/compare_ground_models.py \
		--tile "data/2025/Caleta Tiny Island/cloud0.las" \
		--out data/interim/ground_model_comparison_caleta.json \
		--crs-epsg 32720

experiment-resolution:
	@echo "Running resolution sweep experiment..."
	@.venv/bin/python scripts/experiments/resolution_sweep.py \
		--tile "data/2025/Caleta Tiny Island/cloud0.las" \
		--out data/interim/resolution_sweep_caleta.json \
		--crs-epsg 32720

experiment-watershed:
	@echo "Running watershed parameter sweep..."
	@.venv/bin/python scripts/experiments/watershed_sweep.py \
		--data-root "data/2025/Caleta Tiny Island" \
		--aoi data/processed/aoi_caleta_tiny_island_epsg32720.geojson \
		--out data/interim/watershed_sweep_caleta_tiny.json \
		--crs-epsg 32720 --field-count 321

experiment-hag:
	@echo "Running HAG histogram analysis..."
	@.venv/bin/python scripts/experiments/hag_histogram.py \
		--tile "data/2025/Caleta Tiny Island/cloud0.las" \
		--out data/interim/hag_histogram_caleta.json \
		--plot data/interim/hag_histogram_caleta.png \
		--crs-epsg 32720
