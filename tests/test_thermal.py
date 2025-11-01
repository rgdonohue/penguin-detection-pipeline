"""
Tests for thermal orthorectification pipeline.

NOTE: These tests require GDAL/rasterio which has complex installation.
Tests are skipped if GDAL is not available. See RUNBOOK.md for setup.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Check GDAL availability
try:
    from pipelines.thermal import GDAL_AVAILABLE, check_dependencies
except ImportError:
    GDAL_AVAILABLE = False
    pytestmark = pytest.mark.skip("pipelines.thermal not importable")

# Skip all tests if GDAL not available
if GDAL_AVAILABLE:
    try:
        check_dependencies()
    except ImportError:
        GDAL_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not GDAL_AVAILABLE,
    reason="GDAL/rasterio not installed. See RUNBOOK.md for installation."
)


class TestThermalDependencies:
    """Test that thermal dependencies are available."""

    def test_gdal_available(self):
        """Test that GDAL/rasterio can be imported."""
        import rasterio
        import pyproj
        assert rasterio is not None
        assert pyproj is not None

    def test_thermal_pipeline_imports(self):
        """Test that thermal pipeline modules can be imported."""
        from pipelines.thermal import (
            ortho_one,
            verify_grid,
            nested_grid,
            load_poses,
            hv_from_dfov,
            rotation_from_ypr,
        )
        # Basic smoke test
        assert callable(ortho_one)
        assert callable(verify_grid)
        assert callable(nested_grid)


class TestCameraModel:
    """Test camera model functions."""

    def test_hv_from_dfov(self):
        """Test HFOV/VFOV computation from diagonal FOV."""
        from pipelines.thermal import hv_from_dfov

        # H20T thermal: 640x512, DFOV ≈ 40.6°
        hfov, vfov = hv_from_dfov(40.6, 640, 512)

        # Expected approximate values
        assert 32 < hfov < 34  # ~33°
        assert 26 < vfov < 28  # ~27°

    def test_rotation_from_ypr(self):
        """Test rotation matrix generation."""
        from pipelines.thermal import rotation_from_ypr
        import numpy as np

        # Test nadir (straight down)
        R = rotation_from_ypr(yaw_deg=0, pitch_deg=-90, roll_deg=0)
        assert R.shape == (3, 3)
        assert np.allclose(np.linalg.det(R), 1.0)  # Proper rotation

        # Test identity-ish (north-facing horizontal)
        R = rotation_from_ypr(yaw_deg=0, pitch_deg=0, roll_deg=0)
        assert R.shape == (3, 3)


class TestPoseParsing:
    """Test pose CSV parsing (mock data)."""

    def test_load_poses_schema(self, tmp_path):
        """Test that pose loading handles expected CSV schema."""
        from pipelines.thermal import load_poses
        import pandas as pd

        # Create minimal mock poses CSV
        csv_path = tmp_path / "poses.csv"
        df = pd.DataFrame({
            "SourceFile": ["DJI_0001_T.JPG"],
            "GPSLatitude": [40.7128],
            "GPSLongitude": [-74.0060],
            "AbsoluteAltitude": [100.0],
            "FlightYawDegree": [45.0],
            "FlightPitchDegree": [0.0],
            "FlightRollDegree": [0.0],
            "GimbalYawDegree": [0.0],
            "GimbalPitchDegree": [-90.0],
            "GimbalRollDegree": [0.0],
        })
        df.to_csv(csv_path, index=False)

        # Load and verify
        loaded_df, cols = load_poses(csv_path)
        assert len(loaded_df) == 1
        assert "GPSLatitude" in cols
        assert cols["GPSLatitude"] == "GPSLatitude"


# Placeholder for integration tests (requires real data)
class TestThermalIntegration:
    """Integration tests for thermal pipeline (requires real data)."""

    @pytest.mark.skip("Requires real thermal data and DSM")
    def test_ortho_one_golden_aoi(self):
        """Test orthorectification on golden AOI thermal frame."""
        # TODO: Add when golden AOI thermal data is available
        pass

    @pytest.mark.skip("Requires real data")
    def test_verify_grid_alignment(self):
        """Test grid verification on real ortho output."""
        # TODO: Add when thermal outputs are available
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
