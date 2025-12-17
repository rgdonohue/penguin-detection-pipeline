import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_lidar_hag as lidar  # noqa: E402


def _patch_lidar_stream(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mins=(0.0, 0.0, 0.0),
    maxs=(1.0, 1.0, 0.0),
    chunks=(),
):
    mins_arr = np.array(mins, dtype=float)
    maxs_arr = np.array(maxs, dtype=float)

    def fake_read_bounds_and_counts(_las_path: Path, _chunk_size: int):
        npts = 0
        for x, _y, _z in chunks:
            npts += len(x)
        return mins_arr, maxs_arr, npts

    def fake_stream_points(_las_path: Path, _chunk_size: int):
        for x, y, z in chunks:
            yield np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64), np.asarray(
                z, dtype=np.float64
            )

    monkeypatch.setattr(lidar, "read_bounds_and_counts", fake_read_bounds_and_counts)
    monkeypatch.setattr(lidar, "_stream_points", fake_stream_points)


def test_empty_tile_ground_dem_falls_back(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _patch_lidar_stream(monkeypatch, mins=(0.0, 0.0, 0.0), maxs=(0.0, 0.0, 0.0), chunks=())
    dem, meta = lidar.build_ground_dem(
        tmp_path / "empty.las", cell_res=0.25, chunk_size=10, verbose=False
    )
    assert dem.shape == (1, 1)
    assert np.isfinite(dem).all()
    assert float(dem[0, 0]) == pytest.approx(0.0)
    assert meta["shape"] == [1, 1]

    hag = lidar.build_hag_grid(tmp_path / "empty.las", dem, meta, chunk_size=10)
    assert hag.shape == (1, 1)
    assert float(hag[0, 0]) == pytest.approx(0.0)

    count, labeled, dets = lidar.detect_penguins_from_hag(
        hag,
        hag_min=0.2,
        hag_max=0.6,
        min_area_cells=2,
        max_area_cells=80,
    )
    assert count == 0
    assert labeled.shape == hag.shape
    assert dets == []


def test_degenerate_bounds_produce_single_cell(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _patch_lidar_stream(
        monkeypatch,
        mins=(100.0, 200.0, 0.0),
        maxs=(100.0, 200.0, 0.0),
        chunks=(
            ([100.0], [200.0], [10.0]),
        ),
    )
    dem, meta = lidar.build_ground_dem(
        tmp_path / "one.las", cell_res=0.25, chunk_size=10, verbose=False
    )
    assert dem.shape == (1, 1)
    assert float(dem[0, 0]) == pytest.approx(10.0)
    assert meta["mins"][:2] == [100.0, 200.0]


def test_single_point_cell_hag_is_zero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _patch_lidar_stream(
        monkeypatch,
        mins=(0.0, 0.0, 0.0),
        maxs=(0.25, 0.25, 0.0),
        chunks=(
            ([0.1], [0.1], [5.0]),
        ),
    )
    dem, meta = lidar.build_ground_dem(
        tmp_path / "single.las", cell_res=0.25, chunk_size=10, verbose=False
    )
    hag = lidar.build_hag_grid(tmp_path / "single.las", dem, meta, chunk_size=10, top_method="max")
    assert hag.shape == dem.shape
    assert np.isfinite(hag).all()
    assert float(hag.max()) == pytest.approx(0.0)


@pytest.mark.xfail(
    reason="Known issue: online quantile update is order-dependent when multiple points land in the same cell.",
    strict=False,
)
def test_quantile_ground_is_order_invariant_for_duplicate_cell_hits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    mins = (0.0, 0.0, 0.0)
    maxs = (0.25, 0.25, 0.0)
    pts_a = ([0.1, 0.1, 0.1], [0.1, 0.1, 0.1], [0.0, 10.0, 20.0])
    pts_b = ([0.1, 0.1, 0.1], [0.1, 0.1, 0.1], [20.0, 10.0, 0.0])

    _patch_lidar_stream(monkeypatch, mins=mins, maxs=maxs, chunks=(pts_a,))
    dem_a, _meta_a = lidar.build_ground_dem(
        tmp_path / "dup_a.las",
        cell_res=0.25,
        chunk_size=10,
        verbose=False,
        ground_method="p05",
        quantile_lr=0.05,
    )

    _patch_lidar_stream(monkeypatch, mins=mins, maxs=maxs, chunks=(pts_b,))
    dem_b, _meta_b = lidar.build_ground_dem(
        tmp_path / "dup_b.las",
        cell_res=0.25,
        chunk_size=10,
        verbose=False,
        ground_method="p05",
        quantile_lr=0.05,
    )

    assert np.allclose(dem_a, dem_b)

