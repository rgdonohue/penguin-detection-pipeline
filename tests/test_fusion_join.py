import json
from pathlib import Path

import pytest

from pipelines.fusion import FusionParams, run


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
