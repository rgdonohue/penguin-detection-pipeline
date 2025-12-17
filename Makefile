# Penguin Detection Pipeline — Working Makefile
# Principle: Only include targets that actually work

.PHONY: help env validate test golden test-lidar thermal clean

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
	@echo "  make thermal      - Run H30T thermal smoke test on staged frames"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean        - Remove interim files"

# Environment setup
env:
	@echo "Setting up virtual environment..."
	@if [ ! -d ".venv" ]; then \
		python3 -m venv .venv; \
		echo "✓ Virtual environment created"; \
	fi
	@.venv/bin/pip install -q -r requirements.txt
	@echo "✓ Dependencies installed"
	@echo ""
	@echo "Activate with: source .venv/bin/activate"

# Validate environment and run tests
validate:
	@echo "Running environment validation..."
	@./scripts/validate_environment.sh

# Run golden AOI test suite (requires venv active)
test:
	@echo "Running golden AOI test suite..."
	@if [ -z "$$VIRTUAL_ENV" ]; then \
		echo "⚠️  Warning: Virtual environment not active"; \
		echo "   Run: source .venv/bin/activate"; \
		echo "   Or use: .venv/bin/pytest tests/test_golden_aoi.py -v"; \
		exit 1; \
	fi
	@pytest tests/test_golden_aoi.py -v

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
		MPLCONFIGDIR="data/interim/mplconfig" python3 scripts/run_lidar_hag.py \
			--data-root "$$tmpdir" \
			--out data/interim/lidar_test.json \
			--cell-res 0.25 \
			--hag-min 0.2 --hag-max 0.6 \
			--min-area-cells 2 --max-area-cells 80 \
			--emit-geojson --plots; \
		rm -rf "$$tmpdir"
	@echo ""
	@echo "✓ LiDAR detection complete"
	@echo "  Results: data/interim/lidar_test.json"
	@echo "  GeoJSON: data/interim/lidar_hag_geojson/"
	@echo "  Plots: data/interim/lidar_hag_plots/"

thermal:
	@echo "Running thermal smoke test on staged H30T frames..."
	@python3 scripts/run_thermal_smoketest.py \
		--input-dir data/intake/h30t \
		--selection-mode per-dir \
		--limit 0 \
		--output data/interim/thermal_smoketest.json
	@echo ""
	@echo "✓ Thermal smoke test complete"
	@echo "  Summary: data/interim/thermal_smoketest.json"

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
