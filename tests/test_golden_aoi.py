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
import hashlib
import os
import subprocess
from pathlib import Path
import sys
from typing import Optional
import pytest
import shutil


# Test configuration
TEST_OUTPUT_DIR = Path("data/interim/test_golden")
EXPECTED_DETECTION_COUNT = 802
TOLERANCE = 5  # Allow ±5 detections for minor numerical variations
EXPECTED_SIGNATURE_SHA256 = "2fa9ef298f37ef70d654c44728d69938db852cd2ee0b40e170dfea94b115c2fc"


def _find_golden_cloud3() -> Optional[Path]:
    candidates = [
        Path("data/legacy_ro/penguin-2.0/data/raw/LiDAR/sample/cloud3.las"),
        Path("data/legacy_ro/penguin-2.0/data/raw/LiDAR/cloud3.las"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    root = Path("data/legacy_ro/penguin-2.0/data/raw/LiDAR")
    if not root.exists():
        return None
    matches = list(root.rglob("cloud3.las"))
    return matches[0] if matches else None


def _link_or_skip(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(src.resolve(), dst)
    except OSError:
        try:
            os.link(src.resolve(), dst)
        except OSError as exc:
            pytest.skip(f"Cannot create symlink/hardlink for golden file: {exc}")


def _stable_signature(summary: dict) -> str:
    def norm_float(value: object) -> Optional[float]:
        if value is None:
            return None
        return round(float(value), 3)

    files = []
    for entry in summary.get("files", []):
        dets = []
        for det in entry.get("detections", []) or []:
            dets.append(
                {
                    "x": norm_float(det.get("x")),
                    "y": norm_float(det.get("y")),
                    "area_cells": int(det.get("area_cells", 0)),
                }
            )
        dets.sort(key=lambda d: (d["x"], d["y"], d["area_cells"]))
        files.append(
            {
                "count": int(entry.get("count", 0)),
                "grid_shape": entry.get("grid_shape"),
                "detections": dets,
            }
        )

    payload = {
        "params": summary.get("params"),
        "total_count": int(summary.get("total_count", 0)),
        "files": files,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@pytest.fixture(scope="module", autouse=True)
def setup_test_env(tmp_path_factory):
    """Set up test environment, clean up after."""
    # Clean test output directory before tests
    if TEST_OUTPUT_DIR.exists():
        shutil.rmtree(TEST_OUTPUT_DIR)
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Create a minimal data-root containing only the golden cloud3.las so the
    # CLI doesn't recurse over the full legacy LiDAR directory.
    golden_src = _find_golden_cloud3()
    if golden_src is None:
        pytest.skip("Golden cloud3.las not available under data/legacy_ro")

    fixture_root = tmp_path_factory.mktemp("golden_lidar_root")
    _link_or_skip(golden_src, fixture_root / "cloud3.las")
    os.environ["PENGUINS_GOLDEN_LIDAR_ROOT"] = str(fixture_root)

    yield

    # Keep test outputs for inspection (don't clean up)
    # This helps with debugging if tests fail


class TestLiDARPipeline:
    """Test suite for LiDAR HAG detection pipeline."""

    def test_golden_data_exists(self):
        """Verify golden test data is accessible."""
        golden_root = Path(os.environ["PENGUINS_GOLDEN_LIDAR_ROOT"])
        golden_file = golden_root / "cloud3.las"
        assert golden_root.exists(), f"Golden data root not found: {golden_root}"
        assert golden_file.exists(), f"Golden LAS file not found: {golden_file}"

        # Check file is non-empty
        assert golden_file.stat().st_size > 0, "Golden LAS file is empty"

    def test_lidar_script_runs(self):
        """Test that LiDAR detection script runs without errors."""
        golden_root = Path(os.environ["PENGUINS_GOLDEN_LIDAR_ROOT"])
        mpl_dir = TEST_OUTPUT_DIR / "mplconfig"
        mpl_dir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env["MPLCONFIGDIR"] = str(mpl_dir)

        cmd = [
            sys.executable, "scripts/run_lidar_hag.py",
            "--data-root", str(golden_root),
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
            env=env,
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
        """Verify expected number of detections (802 ± tolerance)."""
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
        """Verify output signature matches expected baseline without re-running."""
        with open(TEST_OUTPUT_DIR / "golden_results.json") as f:
            run1 = json.load(f)

        signature = _stable_signature(run1)
        assert signature == EXPECTED_SIGNATURE_SHA256, (
            f"Golden signature drifted: got {signature}, expected {EXPECTED_SIGNATURE_SHA256}. "
            "If this is intentional, update EXPECTED_SIGNATURE_SHA256."
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
