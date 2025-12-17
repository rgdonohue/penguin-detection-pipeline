import subprocess
from pathlib import Path

import pytest

from pipelines.lidar import LidarParams, run


def test_lidar_wrapper_invokes_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    params = LidarParams(
        data_root=Path("data/2025"),
        out_path=tmp_path / "out.json",
        emit_geojson=True,
        plots=True,
        timeout_s=12.5,
    )
    out = run(params)

    assert out == params.out_path
    assert calls["kwargs"]["check"] is True
    assert calls["kwargs"]["capture_output"] is True
    assert calls["kwargs"]["text"] is True
    assert calls["kwargs"]["timeout"] == 12.5
    assert calls["cmd"][0].endswith("python") or "python" in Path(calls["cmd"][0]).name
    assert "scripts/run_lidar_hag.py" in calls["cmd"][1]
    assert "--data-root" in calls["cmd"]
    assert "--emit-geojson" in calls["cmd"]
    assert "--plots" in calls["cmd"]


def test_lidar_wrapper_surfaces_stderr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def fake_run(_cmd, **_kwargs):
        raise subprocess.CalledProcessError(
            returncode=2, cmd=["python"], output="", stderr="boom"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    params = LidarParams(data_root=Path("data/2025"), out_path=tmp_path / "out.json")
    with pytest.raises(RuntimeError, match="stderr: boom"):
        run(params)

