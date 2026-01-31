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

    def test_rotation_from_ypr_shape_and_det(self):
        """Rotation matrix should be 3x3 with det=+1 at all orientations."""
        from pipelines.thermal import rotation_from_ypr
        import numpy as np

        cases = [
            (0, 0, 0),      # horizontal north
            (0, -90, 0),    # nadir
            (0, -45, 0),    # oblique 45°
            (90, -90, 0),   # nadir, yaw east
            (-88.4, -45, 0),  # oblique, yaw ~west (image 0076)
            (180, -30, 5),  # oblique south with roll
        ]
        for yaw, pitch, roll in cases:
            R = rotation_from_ypr(yaw_deg=yaw, pitch_deg=pitch, roll_deg=roll)
            assert R.shape == (3, 3), f"Bad shape at ({yaw},{pitch},{roll})"
            assert np.allclose(np.linalg.det(R), 1.0), (
                f"det(R)={np.linalg.det(R):.4f} at ({yaw},{pitch},{roll})"
            )
            assert np.allclose(R @ R.T, np.eye(3), atol=1e-12), (
                f"R not orthogonal at ({yaw},{pitch},{roll})"
            )

    def test_rotation_horizontal_north(self):
        """At yaw=0, pitch=0 (horizontal, facing North): camera axes map correctly in ENU."""
        from pipelines.thermal import rotation_from_ypr
        import numpy as np

        R = rotation_from_ypr(yaw_deg=0, pitch_deg=0, roll_deg=0)
        # Camera forward (z) = North = ENU [0, 1, 0]
        assert np.allclose(R @ [0, 0, 1], [0, 1, 0], atol=1e-12)
        # Camera right (x) = East = ENU [1, 0, 0]
        assert np.allclose(R @ [1, 0, 0], [1, 0, 0], atol=1e-12)
        # Camera down (y) = Down = ENU [0, 0, -1]
        assert np.allclose(R @ [0, 1, 0], [0, 0, -1], atol=1e-12)

    def test_rotation_nadir(self):
        """At yaw=0, pitch=-90 (nadir): optical axis points straight down."""
        from pipelines.thermal import rotation_from_ypr
        import numpy as np

        R = rotation_from_ypr(yaw_deg=0, pitch_deg=-90, roll_deg=0)
        # Camera forward (z) = Down = ENU [0, 0, -1]
        assert np.allclose(R @ [0, 0, 1], [0, 0, -1], atol=1e-12)
        # Camera right (x) = East = ENU [1, 0, 0]
        assert np.allclose(R @ [1, 0, 0], [1, 0, 0], atol=1e-12)
        # Camera down (y) = South = ENU [0, -1, 0]
        assert np.allclose(R @ [0, 1, 0], [0, -1, 0], atol=1e-12)

    def test_rotation_oblique_45(self):
        """At yaw=0, pitch=-45: optical axis 45° below horizontal, northward."""
        from pipelines.thermal import rotation_from_ypr
        import numpy as np

        R = rotation_from_ypr(yaw_deg=0, pitch_deg=-45, roll_deg=0)
        s = np.sqrt(2) / 2  # sin/cos(45°)
        # Camera forward (z) = 45° below horizontal toward North
        # = (0, cos45, -sin45) in ENU = (0, s, -s)
        assert np.allclose(R @ [0, 0, 1], [0, s, -s], atol=1e-10)
        # Camera right (x) = East
        assert np.allclose(R @ [1, 0, 0], [1, 0, 0], atol=1e-10)

    def test_rotation_yaw_east(self):
        """At yaw=90 (East), pitch=0 (horizontal): forward = East."""
        from pipelines.thermal import rotation_from_ypr
        import numpy as np

        R = rotation_from_ypr(yaw_deg=90, pitch_deg=0, roll_deg=0)
        # Camera forward (z) = East = ENU [1, 0, 0]
        assert np.allclose(R @ [0, 0, 1], [1, 0, 0], atol=1e-10)
        # Camera right (x) = South = ENU [0, -1, 0]
        assert np.allclose(R @ [1, 0, 0], [0, -1, 0], atol=1e-10)
        # Camera down (y) = Down = ENU [0, 0, -1]
        assert np.allclose(R @ [0, 1, 0], [0, 0, -1], atol=1e-10)

    def test_rotation_yaw_south(self):
        """At yaw=180, pitch=0: forward = South."""
        from pipelines.thermal import rotation_from_ypr
        import numpy as np

        R = rotation_from_ypr(yaw_deg=180, pitch_deg=0, roll_deg=0)
        # Camera forward (z) = South = ENU [0, -1, 0]
        assert np.allclose(R @ [0, 0, 1], [0, -1, 0], atol=1e-10)
        # Camera right (x) = West = ENU [-1, 0, 0]
        assert np.allclose(R @ [1, 0, 0], [-1, 0, 0], atol=1e-10)

    def test_rotation_ned_frame(self):
        """NED frame output: at zero angles, camera axes map to NED correctly."""
        from pipelines.thermal import rotation_from_ypr
        import numpy as np

        R = rotation_from_ypr(yaw_deg=0, pitch_deg=0, roll_deg=0, frame="NED")
        # Camera forward (z) = North = NED [1, 0, 0]
        assert np.allclose(R @ [0, 0, 1], [1, 0, 0], atol=1e-12)
        # Camera right (x) = East = NED [0, 1, 0]
        assert np.allclose(R @ [1, 0, 0], [0, 1, 0], atol=1e-12)
        # Camera down (y) = Down = NED [0, 0, 1]
        assert np.allclose(R @ [0, 1, 0], [0, 0, 1], atol=1e-12)

    def test_nadir_projection_center(self):
        """At nadir, a point directly below the camera projects to image center."""
        from pipelines.thermal import rotation_from_ypr
        import numpy as np

        R = rotation_from_ypr(yaw_deg=0, pitch_deg=-90, roll_deg=0)
        # Camera at altitude 50m, point directly below in ENU
        V_world = np.array([0.0, 0.0, -50.0])
        V_cam = R.T @ V_world
        # Should have xc=0, yc=0, zc>0 → projects to (cx, cy)
        assert abs(V_cam[0]) < 1e-10, f"xc should be 0, got {V_cam[0]}"
        assert abs(V_cam[1]) < 1e-10, f"yc should be 0, got {V_cam[1]}"
        assert V_cam[2] > 0, f"zc should be positive, got {V_cam[2]}"

    def test_oblique_projection_on_axis(self):
        """At pitch=-45°, a point along the optical axis projects to image center."""
        from pipelines.thermal import rotation_from_ypr
        import numpy as np

        R = rotation_from_ypr(yaw_deg=0, pitch_deg=-45, roll_deg=0)
        # Optical axis at 45° below horizontal toward North:
        # Point 50m north and 50m below camera (along optical axis)
        V_world = np.array([0.0, 50.0, -50.0])
        V_cam = R.T @ V_world
        assert abs(V_cam[0]) < 1e-8, f"xc should be ~0, got {V_cam[0]}"
        assert abs(V_cam[1]) < 1e-8, f"yc should be ~0, got {V_cam[1]}"
        assert V_cam[2] > 0, f"zc should be positive, got {V_cam[2]}"

    def test_nadir_projection_offcenter(self):
        """At nadir, a point 10m East of nadir projects right of image center."""
        from pipelines.thermal import rotation_from_ypr
        import numpy as np

        R = rotation_from_ypr(yaw_deg=0, pitch_deg=-90, roll_deg=0)
        V_world = np.array([10.0, 0.0, -50.0])  # 10m East, 50m below
        V_cam = R.T @ V_world
        # xc > 0 (right in image), zc > 0 (visible)
        assert V_cam[0] > 0, f"xc should be positive (rightward), got {V_cam[0]}"
        assert V_cam[2] > 0, f"zc should be positive, got {V_cam[2]}"
        # Projection: u = fx * xc/zc + cx → u > cx
        fx = 1000.0
        cx = 320.0
        u = fx * V_cam[0] / V_cam[2] + cx
        assert u > cx, f"Should project right of center, got u={u}"


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


class TestObliqueGCPProjection:
    """Validate rotation matrix using 16 real GCPs (4 corners × 4 oblique images).

    Uses data from Bushes box thermal labels session (2026-01-30).
    All 4 images are at -45° pitch from different cardinal directions.
    """

    # Camera EXIF data (from exiftool extraction)
    CAMERAS = [
        {"frame": "0076", "lat": -42.0852775, "lon": -63.8664954,
         "alt_msl": 59.2, "alt_agl": 35.4, "yaw": -88.4, "pitch": -45.0, "roll": 0.0},
        {"frame": "0116", "lat": -42.0857238, "lon": -63.8670125,
         "alt_msl": 56.0, "alt_agl": 32.2, "yaw": 1.4, "pitch": -45.0, "roll": 0.0},
        {"frame": "0158", "lat": -42.0853613, "lon": -63.8675492,
         "alt_msl": 58.5, "alt_agl": 34.7, "yaw": 89.5, "pitch": -45.0, "roll": 0.0},
        {"frame": "0197", "lat": -42.0849066, "lon": -63.8670938,
         "alt_msl": 59.4, "alt_agl": 35.6, "yaw": -179.3, "pitch": -45.0, "roll": 0.0},
    ]

    # Known box corners (WGS84)
    CORNERS_WGS84 = {
        "NW": (-42.085258, -63.867123),
        "NE": (-42.085273, -63.866958),
        "SE": (-42.085392, -63.866972),
        "SW": (-42.085381, -63.867161),
    }

    # Labeled corner pixels per image (order as in CSV: 4 "Box Corner" labels per image)
    CORNER_PIXELS = {
        "0076": [(618, 411), (685, 132), (128, 395), (250, 84)],
        "0116": [(654, 43), (619, 348), (68, 303), (261, 11)],
        "0158": [(237, 200), (643, 583), (691, 224), (66, 525)],
        "0197": [(184, 411), (606, 457), (733, 146), (279, 116)],
    }

    IMG_W, IMG_H = 1280, 1024
    DFOV_DEG = 41.0  # H30T thermal approximate DFOV

    @pytest.mark.skipif(not GDAL_AVAILABLE, reason="pyproj not available")
    def test_gcp_projections_within_frame(self):
        """All 4 GPS corners should forward-project within image bounds for all 4 views."""
        from pipelines.thermal import rotation_from_ypr, hv_from_dfov, intrinsics_from_fov
        from pyproj import Transformer
        import numpy as np

        t = Transformer.from_crs("EPSG:4326", "EPSG:32720", always_xy=True)

        # Convert corners to UTM
        corners_utm = {}
        for name, (lat, lon) in self.CORNERS_WGS84.items():
            e, n = t.transform(lon, lat)
            corners_utm[name] = (e, n)

        hfov, vfov = hv_from_dfov(self.DFOV_DEG, self.IMG_W, self.IMG_H)
        fx, fy, cx, cy = intrinsics_from_fov(hfov, vfov, self.IMG_W, self.IMG_H)

        total_in_frame = 0
        for cam in self.CAMERAS:
            R = rotation_from_ypr(cam["yaw"], cam["pitch"], cam["roll"])
            Ce, Cn = t.transform(cam["lon"], cam["lat"])
            # Ground elevation estimate from MSL - AGL
            z_ground = cam["alt_msl"] - cam["alt_agl"]
            Cz = cam["alt_msl"]

            for name, (ce, cn) in corners_utm.items():
                dE = ce - Ce
                dN = cn - Cn
                dU = z_ground - Cz

                Vc = R.T @ np.array([dE, dN, dU])
                xc, yc, zc = Vc

                assert zc > 0, (
                    f"Frame {cam['frame']} corner {name}: zc={zc:.1f} "
                    f"(not visible, behind camera)"
                )

                u = fx * xc / zc + cx
                v = fy * yc / zc + cy

                # All corners should be within the image frame
                # (use generous margin for altitude/FOV uncertainty)
                assert -200 < u < self.IMG_W + 200, (
                    f"Frame {cam['frame']} corner {name}: u={u:.0f} far out of frame"
                )
                assert -200 < v < self.IMG_H + 200, (
                    f"Frame {cam['frame']} corner {name}: v={v:.0f} far out of frame"
                )

                if 0 <= u <= self.IMG_W and 0 <= v <= self.IMG_H:
                    total_in_frame += 1

        # At minimum, most corners should be within frame bounds
        # (16 total = 4 images × 4 corners)
        assert total_in_frame >= 12, (
            f"Only {total_in_frame}/16 corners projected within frame"
        )

    @pytest.mark.skipif(not GDAL_AVAILABLE, reason="pyproj not available")
    def test_gcp_projection_not_degenerate(self):
        """Projected corners should span a significant portion of the image, not cluster."""
        from pipelines.thermal import rotation_from_ypr, hv_from_dfov, intrinsics_from_fov
        from pyproj import Transformer
        import numpy as np

        t = Transformer.from_crs("EPSG:4326", "EPSG:32720", always_xy=True)
        corners_utm = {}
        for name, (lat, lon) in self.CORNERS_WGS84.items():
            e, n = t.transform(lon, lat)
            corners_utm[name] = (e, n)

        hfov, vfov = hv_from_dfov(self.DFOV_DEG, self.IMG_W, self.IMG_H)
        fx, fy, cx, cy = intrinsics_from_fov(hfov, vfov, self.IMG_W, self.IMG_H)

        for cam in self.CAMERAS:
            R = rotation_from_ypr(cam["yaw"], cam["pitch"], cam["roll"])
            Ce, Cn = t.transform(cam["lon"], cam["lat"])
            z_ground = cam["alt_msl"] - cam["alt_agl"]
            Cz = cam["alt_msl"]

            us, vs = [], []
            for name, (ce, cn) in corners_utm.items():
                Vc = R.T @ np.array([ce - Ce, cn - Cn, z_ground - Cz])
                if Vc[2] > 0:
                    us.append(fx * Vc[0] / Vc[2] + cx)
                    vs.append(fy * Vc[1] / Vc[2] + cy)

            if len(us) >= 3:
                u_span = max(us) - min(us)
                v_span = max(vs) - min(vs)
                # Corners should span at least 100 pixels in each direction
                # (they subtend ~15m at 30-35m AGL, which is substantial)
                assert u_span > 100, (
                    f"Frame {cam['frame']}: u_span={u_span:.0f}px too small"
                )
                assert v_span > 50, (
                    f"Frame {cam['frame']}: v_span={v_span:.0f}px too small"
                )


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
