import json
import warnings
from pathlib import Path

import pytest

from pipelines.fusion import FusionParams, run, _validate_coordinate_range


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj))


def test_fusion_join_basic(tmp_path: Path):
    lidar = {
        "crs": "EPSG:32720",
        "files": [
            {
                "path": "lidar_tile.las",
                "detections": [
                    {"x": 0.0, "y": 0.0},
                    {"x": 10.0, "y": 0.0},
                    {"x": 20.0, "y": 0.0},
                ],
            }
        ]
    }
    thermal = {
        "crs": "EPSG:32720",
        "files": [
            {
                "path": "thermal_frame.tif",
                "detections": [
                    {"x": 0.1, "y": 0.0},
                    {"x": 10.2, "y": 0.0},
                ],
            }
        ]
    }

    lidar_path = tmp_path / "lidar.json"
    thermal_path = tmp_path / "thermal.json"
    out_path = tmp_path / "fusion.json"
    _write_json(lidar_path, lidar)
    _write_json(thermal_path, thermal)

    run(FusionParams(lidar_summary=lidar_path, thermal_summary=thermal_path, out_path=out_path, match_radius_m=0.5))

    out = json.loads(out_path.read_text())
    assert out["crs"] == "EPSG:32720"
    assert out["purpose"] == "qc_alignment"
    assert out["temperature_calibrated"] is False
    assert out["lidar_count"] == 3
    assert out["thermal_count"] == 2
    assert out["lidar_matched_count"] == 2
    assert out["thermal_matched_count"] == 2
    assert out["lidar_only_count"] == 1
    assert out["thermal_only_count"] == 0


def test_fusion_join_many_to_one(tmp_path: Path):
    lidar = {"detections": [{"x": 0.0, "y": 0.0}, {"x": 0.2, "y": 0.1}]}
    thermal = {"detections": [{"x": 0.1, "y": 0.0}]}

    lidar_path = tmp_path / "lidar.json"
    thermal_path = tmp_path / "thermal.json"
    out_path = tmp_path / "fusion.json"
    _write_json(lidar_path, lidar)
    _write_json(thermal_path, thermal)

    run(FusionParams(lidar_summary=lidar_path, thermal_summary=thermal_path, out_path=out_path, match_radius_m=0.5))

    out = json.loads(out_path.read_text())
    assert out["lidar_matched_count"] == 2
    assert out["thermal_matched_count"] == 1
    assert out["thermal_only_count"] == 0


def test_fusion_rejects_crs_mismatch(tmp_path: Path):
    lidar_path = tmp_path / "lidar.json"
    thermal_path = tmp_path / "thermal.json"
    out_path = tmp_path / "fusion.json"
    _write_json(lidar_path, {"crs": "EPSG:32720", "detections": [{"x": 0.0, "y": 0.0}]})
    _write_json(thermal_path, {"crs": "EPSG:5345", "detections": [{"x": 0.0, "y": 0.0}]})

    with pytest.raises(ValueError, match="CRS mismatch"):
        run(FusionParams(lidar_summary=lidar_path, thermal_summary=thermal_path, out_path=out_path))


# ---------------------------------------------------------------------------
# CRS coordinate range validation tests
# ---------------------------------------------------------------------------

class TestCRSCoordinateValidation:
    def test_warns_geographic_crs_with_projected_coords(self):
        """Geographic CRS with large coordinate values should warn."""
        dets = [{"x": 500000.0, "y": 6000000.0}]
        with pytest.warns(UserWarning, match="coordinates exceed 360"):
            _validate_coordinate_range(dets, "EPSG:4326")

    def test_warns_projected_crs_with_degree_coords(self):
        """Projected CRS with degree-range coordinates should warn."""
        dets = [{"x": -65.5, "y": -42.1}]
        with pytest.warns(UserWarning, match="coordinates < 360"):
            _validate_coordinate_range(dets, "EPSG:32720")

    def test_no_warning_for_valid_projected_coords(self):
        """Projected CRS with projected coordinates should not warn."""
        dets = [{"x": 500000.0, "y": 6000000.0}]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            _validate_coordinate_range(dets, "EPSG:32720")

    def test_no_warning_for_valid_geographic_coords(self):
        """Geographic CRS with degree coordinates should not warn."""
        dets = [{"x": -65.5, "y": -42.1}]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            _validate_coordinate_range(dets, "EPSG:4326")

    def test_no_warning_when_crs_is_none(self):
        """No validation when CRS is None."""
        dets = [{"x": 500000.0, "y": 6000000.0}]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            _validate_coordinate_range(dets, None)

    def test_no_warning_for_empty_detections(self):
        """No validation when detections list is empty."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            _validate_coordinate_range([], "EPSG:32720")
