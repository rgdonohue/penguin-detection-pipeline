#!/usr/bin/env python3
"""
Golden AOI Smoke Tests — Penguin Detection Pipeline

Validates that the core LiDAR detection pipeline produces reproducible,
expected outputs on the golden test dataset (cloud3.las sample).

These tests embody DORA principles:
- Fast feedback (< 5 min)
- Reproducibility checks
- Small batch validation

Run with: pytest -v tests/test_golden_aoi.py
"""

import json
import subprocess
from pathlib import Path
import pytest
import shutil


# Test configuration
GOLDEN_DATA_ROOT = Path("data/legacy_ro/penguin-2.0/data/raw/LiDAR/sample")
GOLDEN_LAZ_FILE = GOLDEN_DATA_ROOT / "cloud3.las"
TEST_OUTPUT_DIR = Path("data/interim/test_golden")
EXPECTED_DETECTION_COUNT = 879
TOLERANCE = 5  # Allow ±5 detections for minor numerical variations


@pytest.fixture(scope="module", autouse=True)
def setup_test_env():
    """Set up test environment, clean up after."""
    # Clean test output directory before tests
    if TEST_OUTPUT_DIR.exists():
        shutil.rmtree(TEST_OUTPUT_DIR)
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    yield

    # Keep test outputs for inspection (don't clean up)
    # This helps with debugging if tests fail


class TestLiDARPipeline:
    """Test suite for LiDAR HAG detection pipeline."""

    def test_golden_data_exists(self):
        """Verify golden test data is accessible."""
        assert GOLDEN_DATA_ROOT.exists(), f"Golden data root not found: {GOLDEN_DATA_ROOT}"
        assert GOLDEN_LAZ_FILE.exists(), f"Golden LAZ file not found: {GOLDEN_LAZ_FILE}"

        # Check file is non-empty
        assert GOLDEN_LAZ_FILE.stat().st_size > 0, "Golden LAZ file is empty"

    def test_lidar_script_runs(self):
        """Test that LiDAR detection script runs without errors."""
        cmd = [
            "python3", "scripts/run_lidar_hag.py",
            "--data-root", str(GOLDEN_DATA_ROOT),
            "--out", str(TEST_OUTPUT_DIR / "golden_results.json"),
            "--cell-res", "0.25",
            "--hag-min", "0.2",
            "--hag-max", "0.6",
            "--min-area-cells", "2",
            "--max-area-cells", "80",
            "--emit-geojson",
            "--plots",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 min timeout
        )

        # Check script succeeded
        assert result.returncode == 0, (
            f"LiDAR script failed with return code {result.returncode}\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

    def test_output_json_exists(self):
        """Verify main JSON output file was created."""
        json_path = TEST_OUTPUT_DIR / "golden_results.json"
        assert json_path.exists(), f"Output JSON not found: {json_path}"
        assert json_path.stat().st_size > 0, "Output JSON is empty"

    def test_detection_count(self):
        """Verify expected number of detections (879 ± tolerance)."""
        json_path = TEST_OUTPUT_DIR / "golden_results.json"

        with open(json_path) as f:
            data = json.load(f)

        assert "total_count" in data, "Missing 'total_count' in output JSON"
        count = data["total_count"]

        # Allow small tolerance for numerical variations
        assert abs(count - EXPECTED_DETECTION_COUNT) <= TOLERANCE, (
            f"Detection count {count} outside tolerance of {EXPECTED_DETECTION_COUNT} ± {TOLERANCE}"
        )

    def test_detection_data_structure(self):
        """Verify output JSON has expected structure."""
        json_path = TEST_OUTPUT_DIR / "golden_results.json"

        with open(json_path) as f:
            data = json.load(f)

        # Check required keys
        assert "files" in data, "Missing 'files' key"
        assert "total_count" in data, "Missing 'total_count' key"
        assert "params" in data, "Missing 'params' key"

        # Check file results
        assert len(data["files"]) == 1, f"Expected 1 file result, got {len(data['files'])}"

        file_result = data["files"][0]
        assert "path" in file_result, "Missing 'path' in file result"
        assert "count" in file_result, "Missing 'count' in file result"
        assert "detections" in file_result, "Missing 'detections' in file result"

        # Verify detections have required fields
        detections = file_result["detections"]
        assert len(detections) > 0, "No detections in results"

        first_detection = detections[0]
        required_fields = ["x", "y", "area_m2", "hag_mean", "hag_max", "circularity", "solidity"]
        for field in required_fields:
            assert field in first_detection, f"Missing field '{field}' in detection"

    def test_geojson_output_exists(self):
        """Verify GeoJSON output was created."""
        geojson_dir = TEST_OUTPUT_DIR / "lidar_hag_geojson"
        assert geojson_dir.exists(), f"GeoJSON directory not found: {geojson_dir}"

        geojson_files = list(geojson_dir.glob("*.geojson"))
        assert len(geojson_files) > 0, "No GeoJSON files generated"

        # Check first GeoJSON has content
        with open(geojson_files[0]) as f:
            geojson = json.load(f)

        assert geojson["type"] == "FeatureCollection", "Invalid GeoJSON type"
        assert "features" in geojson, "Missing 'features' in GeoJSON"
        assert len(geojson["features"]) > 0, "No features in GeoJSON"

    def test_plots_generated(self):
        """Verify QC plots were generated."""
        plots_dir = TEST_OUTPUT_DIR / "lidar_hag_plots"
        assert plots_dir.exists(), f"Plots directory not found: {plots_dir}"

        # Check for expected plot files
        hag_plot = plots_dir / "cloud3_hag.png"
        detect_plot = plots_dir / "cloud3_hag_detect.png"

        assert hag_plot.exists(), f"HAG plot not found: {hag_plot}"
        assert detect_plot.exists(), f"Detection plot not found: {detect_plot}"

        # Check files are non-empty
        assert hag_plot.stat().st_size > 0, "HAG plot is empty"
        assert detect_plot.stat().st_size > 0, "Detection plot is empty"

    def test_provenance_tracking(self):
        """Verify provenance metadata was recorded."""
        provenance_path = TEST_OUTPUT_DIR / "provenance_lidar.json"
        assert provenance_path.exists(), f"Provenance file not found: {provenance_path}"

        with open(provenance_path) as f:
            prov = json.load(f)

        # Check required provenance fields
        assert "timestamp" in prov, "Missing timestamp in provenance"
        assert "script" in prov, "Missing script name in provenance"
        assert "params" in prov, "Missing params in provenance"

    def test_reproducibility(self):
        """Verify pipeline produces identical results across runs."""
        # Run pipeline a second time
        cmd = [
            "python3", "scripts/run_lidar_hag.py",
            "--data-root", str(GOLDEN_DATA_ROOT),
            "--out", str(TEST_OUTPUT_DIR / "golden_results_run2.json"),
            "--cell-res", "0.25",
            "--hag-min", "0.2",
            "--hag-max", "0.6",
            "--min-area-cells", "2",
            "--max-area-cells", "80",
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=300)
        assert result.returncode == 0, "Second run failed"

        # Compare counts
        with open(TEST_OUTPUT_DIR / "golden_results.json") as f:
            run1 = json.load(f)

        with open(TEST_OUTPUT_DIR / "golden_results_run2.json") as f:
            run2 = json.load(f)

        count1 = run1["total_count"]
        count2 = run2["total_count"]

        assert count1 == count2, (
            f"Non-reproducible results: run1={count1}, run2={count2}"
        )

    def test_processing_time_reasonable(self):
        """Verify processing completes in reasonable time (< 2 min for golden AOI)."""
        json_path = TEST_OUTPUT_DIR / "golden_results.json"

        with open(json_path) as f:
            data = json.load(f)

        # Check timing data
        if "files" in data and len(data["files"]) > 0:
            time_s = data["files"][0].get("time_s", 0)
            assert time_s < 120, f"Processing took too long: {time_s:.1f}s (expected < 120s)"


class TestEnvironmentValidation:
    """Validate environment and dependencies."""

    def test_required_python_modules(self):
        """Check that required Python modules can be imported."""
        required_modules = [
            "laspy",
            "numpy",
            "scipy",
            "skimage",
            "matplotlib",
        ]

        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                pytest.fail(f"Required module '{module}' not available")

    def test_legacy_data_accessible(self):
        """Verify legacy data mounts are accessible."""
        legacy_root = Path("data/legacy_ro")
        assert legacy_root.exists(), "Legacy data root not found"

        expected_projects = [
            "penguin-2.0",
            "penguin-3.0",
            "penguin-thermal-og",
            "thermal-lidar-fusion",
        ]

        for project in expected_projects:
            project_path = legacy_root / project
            assert project_path.exists(), f"Legacy project not found: {project}"


# Pytest configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
