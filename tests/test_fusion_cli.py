import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj))


def test_run_fusion_join_cli(tmp_path: Path):
    lidar_path = tmp_path / "lidar.json"
    thermal_path = tmp_path / "thermal.json"
    out_path = tmp_path / "fusion.json"

    _write_json(lidar_path, {"crs": "EPSG:32720", "detections": [{"x": 0.0, "y": 0.0}]})
    _write_json(thermal_path, {"crs": "EPSG:32720", "detections": [{"x": 0.1, "y": 0.0}]})

    script = Path("scripts/run_fusion_join.py").resolve()
    result = subprocess.run(
        [sys.executable, str(script), "--lidar-summary", str(lidar_path), "--thermal-summary", str(thermal_path), "--out", str(out_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert out_path.exists()

    out = json.loads(out_path.read_text())
    assert out["lidar_count"] == 1
    assert out["thermal_count"] == 1
    assert out["lidar_matched_count"] == 1

