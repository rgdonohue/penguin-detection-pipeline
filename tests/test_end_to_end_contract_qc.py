import json
from pathlib import Path

from pipelines.fusion import FusionParams, run as run_fusion
from pipelines.thermal_crs import detections_px_to_crs


def test_end_to_end_contract_qc(tmp_path: Path):
    # Synthetic thermal pixel detections on an orthorectified grid.
    gt = (1000.0, 1.0, 0.0, 2000.0, 0.0, -1.0)
    thermal_px = [{"row": 0.0, "col": 0.0}, {"row": 0.0, "col": 10.0}]
    thermal_crs = detections_px_to_crs(thermal_px, geotransform=gt, crs="EPSG:32720")

    # Synthetic LiDAR candidates already in CRS space.
    lidar_summary = {
        "schema_version": "1",
        "purpose": "lidar_candidates",
        "crs": "EPSG:32720",
        "detections": [{"x": 1000.2, "y": 2000.1}, {"x": 1010.0, "y": 2000.0}],
    }
    thermal_summary = {
        "schema_version": thermal_crs.schema_version,
        "purpose": thermal_crs.purpose,
        "temperature_calibrated": thermal_crs.temperature_calibrated,
        "crs": thermal_crs.crs,
        "detections": thermal_crs.detections,
    }

    lidar_path = tmp_path / "lidar.json"
    thermal_path = tmp_path / "thermal.json"
    out_path = tmp_path / "fusion.json"
    lidar_path.write_text(json.dumps(lidar_summary))
    thermal_path.write_text(json.dumps(thermal_summary))

    run_fusion(FusionParams(lidar_summary=lidar_path, thermal_summary=thermal_path, out_path=out_path, match_radius_m=0.5))

    out = json.loads(out_path.read_text())
    assert out["schema_version"] == "1"
    assert out["purpose"] == "qc_alignment"
    assert out["temperature_calibrated"] is False
    assert out["crs"] == "EPSG:32720"
    assert out["lidar_count"] == 2
    assert out["thermal_count"] == 2
    assert out["lidar_matched_count"] == 2

