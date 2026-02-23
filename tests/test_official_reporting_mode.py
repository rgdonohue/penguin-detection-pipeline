import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_lidar_hag as lidar  # noqa: E402


def _write_registry(path: Path, *, aoi_id: str, status: str, reason: str = "") -> None:
    payload = {
        "schema_version": "1",
        "purpose": "aoi_registry",
        "aois": {
            aoi_id: {
                "aoi_id": aoi_id,
                "status": status,
                "blocked_since": "2026-02-23",
                "reason": reason or f"status={status}",
            }
        },
    }
    path.write_text(json.dumps(payload))


def _set_cli(monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["run_lidar_hag.py", *args])


def _minimal_monkeypatches(
    monkeypatch: pytest.MonkeyPatch,
    *,
    files: list[Path],
    autodetected_epsg: int = 32720,
) -> None:
    monkeypatch.setattr(lidar, "LASPY_AVAILABLE", True)
    monkeypatch.setattr(lidar, "find_lidar_files", lambda _root: files)
    monkeypatch.setattr(
        lidar,
        "_autodetect_crs_from_files",
        lambda _files: {"epsg": int(autodetected_epsg)},
    )
    monkeypatch.setattr(lidar, "write_provenance", lambda *_a, **_k: None)
    monkeypatch.setattr(lidar, "append_timings", lambda *_a, **_k: None)


def test_official_blocks_multi_tile_without_dedupe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    out_path = tmp_path / "summary.json"
    manifest_path = tmp_path / "manifest.json"
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path, aoi_id="caleta_tiny_island", status="ACTIVE")

    _minimal_monkeypatches(
        monkeypatch,
        files=[tmp_path / "tile_a.las", tmp_path / "tile_b.las"],
    )
    monkeypatch.setattr(
        lidar,
        "process_file",
        lambda *_a, **_k: pytest.fail("process_file should not run when preflight blocks"),
    )
    _set_cli(
        monkeypatch,
        [
            "--data-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--official-reporting",
            "--aoi-id",
            "caleta_tiny_island",
            "--aoi-registry",
            str(registry_path),
            "--run-manifest-path",
            str(manifest_path),
        ],
    )

    with pytest.raises(SystemExit):
        lidar.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["run_status"] == "BLOCKED"
    assert any("dedupe-radius-m" in reason for reason in manifest["blocked_reasons"])


def test_official_blocks_registry_marked_aoi(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    out_path = tmp_path / "summary.json"
    manifest_path = tmp_path / "manifest.json"
    registry_path = tmp_path / "registry.json"
    _write_registry(
        registry_path,
        aoi_id="san_lorenzo_box_bushes",
        status="BLOCKED",
        reason="Client coordinates missing",
    )

    _minimal_monkeypatches(monkeypatch, files=[tmp_path / "tile_a.las"])
    monkeypatch.setattr(
        lidar,
        "process_file",
        lambda *_a, **_k: pytest.fail("process_file should not run when AOI is blocked"),
    )
    _set_cli(
        monkeypatch,
        [
            "--data-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--official-reporting",
            "--aoi-id",
            "san_lorenzo_box_bushes",
            "--aoi-registry",
            str(registry_path),
            "--run-manifest-path",
            str(manifest_path),
        ],
    )

    with pytest.raises(SystemExit):
        lidar.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["run_status"] == "BLOCKED"
    assert any("BLOCKED" in reason for reason in manifest["blocked_reasons"])


def test_official_preflight_degraded_exits_without_allow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    out_path = tmp_path / "summary.json"
    manifest_path = tmp_path / "manifest.json"
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path, aoi_id="caleta_tiny_island", status="ACTIVE")

    _minimal_monkeypatches(
        monkeypatch,
        files=[tmp_path / "tile_a.las"],
        autodetected_epsg=5345,
    )
    monkeypatch.setattr(
        lidar,
        "process_file",
        lambda *_a, **_k: pytest.fail("process_file should not run on degraded preflight block"),
    )
    _set_cli(
        monkeypatch,
        [
            "--data-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--official-reporting",
            "--aoi-id",
            "caleta_tiny_island",
            "--aoi-registry",
            str(registry_path),
            "--crs-epsg",
            "32720",
            "--run-manifest-path",
            str(manifest_path),
        ],
    )

    with pytest.raises(SystemExit):
        lidar.main()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["run_status"] == "DEGRADED"
    assert any("CLI CRS differs" in reason for reason in manifest["degraded_reasons"])


def test_official_allow_degraded_writes_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    out_path = tmp_path / "summary.json"
    manifest_path = tmp_path / "manifest.json"
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path, aoi_id="caleta_tiny_island", status="ACTIVE")

    _minimal_monkeypatches(
        monkeypatch,
        files=[tmp_path / "tile_a.las"],
        autodetected_epsg=5345,
    )
    monkeypatch.setattr(
        lidar,
        "process_file",
        lambda *_a, **_k: {
            "path": str(tmp_path / "tile_a.las"),
            "count": 1,
            "time_s": 0.01,
            "detections": [
                {
                    "id": "tile_a:001",
                    "tile": "tile_a",
                    "file": "tile_a.las",
                    "x": 500000.0,
                    "y": 5300000.0,
                }
            ],
        },
    )
    _set_cli(
        monkeypatch,
        [
            "--data-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--official-reporting",
            "--allow-degraded",
            "--aoi-id",
            "caleta_tiny_island",
            "--aoi-registry",
            str(registry_path),
            "--crs-epsg",
            "32720",
            "--run-manifest-path",
            str(manifest_path),
        ],
    )

    lidar.main()

    summary = json.loads(out_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    assert summary["official_reporting"] is True
    assert summary["run_status"] == "DEGRADED"
    assert summary["reporting_counts"]["official_count_basis"] == "raw_single_tile_no_dedupe"
    assert manifest["run_status"] == "DEGRADED"
