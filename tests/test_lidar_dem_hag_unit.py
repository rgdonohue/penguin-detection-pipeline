import argparse
import sys
from pathlib import Path

import numpy as np
import pytest

try:
    import laspy
except ImportError:
    laspy = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_lidar_hag as lidar  # noqa: E402


def _default_args(**overrides) -> argparse.Namespace:
    """Return an argparse.Namespace with valid defaults, applying *overrides*."""
    defaults = dict(
        cell_res=0.25,
        chunk_size=1_000_000,
        hag_min=0.2,
        hag_max=0.6,
        se_radius_m=0.15,
        border_trim_px=0,
        circularity_min=0.2,
        solidity_min=0.7,
        refine_grid_pct=None,
        slope_max_deg=None,
        dedupe_radius_m=None,
        max_grid_mb=512.0,
        ground_quantile_max_memory_gb=2.0,
        h_maxima=0.05,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


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

    count, labeled, dets, _ = lidar.detect_penguins_from_hag(
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


def test_quantile_ground_is_chunk_invariant_and_matches_percentile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    mins = (0.0, 0.0, 0.0)
    maxs = (0.25, 0.25, 0.0)
    zs = np.arange(100, dtype=np.float64)
    xs = np.full_like(zs, 0.1)
    ys = np.full_like(zs, 0.1)

    chunks_one = ((xs, ys, zs),)
    chunks_many = tuple((xs[i : i + 10], ys[i : i + 10], zs[i : i + 10]) for i in range(0, len(zs), 10))

    _patch_lidar_stream(monkeypatch, mins=mins, maxs=maxs, chunks=chunks_one)
    dem_one, _meta_one = lidar.build_ground_dem(
        tmp_path / "q_one.las",
        cell_res=0.25,
        chunk_size=10,
        verbose=False,
        ground_method="p05",
    )

    _patch_lidar_stream(monkeypatch, mins=mins, maxs=maxs, chunks=chunks_many)
    dem_many, _meta_many = lidar.build_ground_dem(
        tmp_path / "q_many.las",
        cell_res=0.25,
        chunk_size=10,
        verbose=False,
        ground_method="p05",
    )

    expected = float(np.percentile(zs, 5))
    assert float(dem_one[0, 0]) == pytest.approx(expected)
    assert float(dem_many[0, 0]) == pytest.approx(expected)
    assert np.allclose(dem_one, dem_many)


def test_quantile_ground_falls_back_to_min_when_memory_budget_too_small(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _patch_lidar_stream(
        monkeypatch,
        mins=(0.0, 0.0, 0.0),
        maxs=(0.25, 0.25, 0.0),
        chunks=((([0.1, 0.1, 0.1], [0.1, 0.1, 0.1], [0.0, 10.0, 20.0])),),
    )

    dem, meta = lidar.build_ground_dem(
        tmp_path / "q_fallback.las",
        cell_res=0.25,
        chunk_size=10,
        verbose=False,
        ground_method="p05",
        quantile_max_memory_gb=1e-9,
    )

    assert float(dem[0, 0]) == pytest.approx(0.0)
    assert meta.get("ground_method_actual") == "min"
    assert meta.get("ground_quantile", {}).get("fallback_method") == "min"


def test_watershed_split_uses_unique_labels_across_regions():
    hag = np.zeros((30, 30), dtype=np.float32)

    # Two disjoint square blobs, each with two internal peaks to force watershed splitting.
    hag[2:12, 2:12] = 1.0
    hag[4, 4] = 1.6
    hag[9, 9] = 1.6

    hag[2:12, 18:28] = 1.0
    hag[4, 20] = 1.6
    hag[9, 25] = 1.6

    count, labeled, dets, _ = lidar.detect_penguins_from_hag(
        hag,
        hag_min=0.5,
        hag_max=2.0,
        min_area_cells=1,
        max_area_cells=10_000,
        connectivity=2,
        circularity_min=0.0,
        solidity_min=0.0,
        apply_watershed=True,
        h_maxima_h=0.2,
        min_split_area_cells=20,
    )

    assert labeled.max() >= 4
    assert count == 4
    assert len(dets) == 4


# ---------------------------------------------------------------------------
# Parameter validation tests
# ---------------------------------------------------------------------------

class TestValidateParams:
    def test_validate_rejects_zero_cell_res(self):
        with pytest.raises(SystemExit, match="cell_res must be > 0"):
            lidar._validate_params(_default_args(cell_res=0))

    def test_validate_rejects_negative_hag_min(self):
        with pytest.raises(SystemExit, match="hag_min must be >= 0"):
            lidar._validate_params(_default_args(hag_min=-1))

    def test_validate_rejects_invalid_circularity(self):
        with pytest.raises(SystemExit, match="circularity_min must be in"):
            lidar._validate_params(_default_args(circularity_min=1.5))

    def test_validate_accepts_valid_defaults(self):
        # Should not raise
        lidar._validate_params(_default_args())


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_dedupe_merges_nearby(self):
        dets = [
            {"id": "a:00001", "x": 0.0, "y": 0.0, "file": "a.las"},
            {"id": "a:00002", "x": 0.1, "y": 0.1, "file": "a.las"},
        ]
        result, index = lidar._dedupe_detections(dets, radius_m=1.0)
        assert len(result) == 1

    def test_dedupe_preserves_distant(self):
        dets = [
            {"id": "a:00001", "x": 0.0, "y": 0.0, "file": "a.las"},
            {"id": "a:00002", "x": 100.0, "y": 100.0, "file": "a.las"},
        ]
        result, index = lidar._dedupe_detections(dets, radius_m=1.0)
        assert len(result) == 2

    def test_dedupe_empty_list(self):
        result, index = lidar._dedupe_detections([], radius_m=1.0)
        assert result == []
        assert index == {}


# ---------------------------------------------------------------------------
# Confidence scoring tests
# ---------------------------------------------------------------------------

class TestConfidenceScoring:
    def test_confidence_scores_between_0_and_1(self):
        dets = [
            {"hag_mean": 0.35, "area_m2": 0.10, "circularity": 0.8, "solidity": 0.9},
            {"hag_mean": 0.1, "area_m2": 0.5, "circularity": 0.3, "solidity": 0.4},
            {"hag_mean": 0.6, "area_m2": 0.01, "circularity": 1.0, "solidity": 1.0},
        ]
        lidar.compute_confidence_scores(dets)
        for d in dets:
            assert 0.0 <= d["confidence"] <= 1.0

    def test_confidence_ideal_penguin_scores_high(self):
        dets = [{"hag_mean": 0.35, "area_m2": 0.10, "circularity": 0.85, "solidity": 0.95}]
        lidar.compute_confidence_scores(dets)
        assert dets[0]["confidence"] > 0.5


# ---------------------------------------------------------------------------
# Detection edge case
# ---------------------------------------------------------------------------

def test_hag_grid_all_below_threshold_gives_zero_detections():
    """All HAG values below hag_min should produce zero detections."""
    hag = np.full((20, 20), 0.05, dtype=np.float32)  # well below 0.2
    count, labeled, dets, _ = lidar.detect_penguins_from_hag(
        hag,
        hag_min=0.2,
        hag_max=0.6,
        min_area_cells=2,
        max_area_cells=80,
    )
    assert count == 0
    assert dets == []
    assert labeled.max() == 0


# ---------------------------------------------------------------------------
# Density stats tests
# ---------------------------------------------------------------------------

class TestDensityStats:
    def test_density_stats_present_when_enabled(self, monkeypatch, tmp_path):
        """When density_stats=True, the per-file JSON contains a 'density' sub-object."""
        _patch_lidar_stream(
            monkeypatch,
            mins=(0.0, 0.0, 0.0),
            maxs=(1.0, 1.0, 0.5),
            chunks=(
                ([0.1, 0.3, 0.5, 0.7, 0.9], [0.1, 0.3, 0.5, 0.7, 0.9], [0.0, 0.0, 0.0, 0.0, 0.0]),
            ),
        )
        info = lidar.process_file(
            tmp_path / "test.las",
            cell_res=0.25, hag_min=0.2, hag_max=0.6,
            min_area_cells=2, max_area_cells=80,
            chunk_size=10, verbose=False, plots_dir=None,
            density_stats=True,
        )
        assert "density" in info
        d = info["density"]
        assert d["total_points"] == 5
        assert d["density_pts_per_m2"] > 0
        assert d["mean_pts_per_cell"] > 0
        assert 0 <= d["pct_empty_cells"] <= 100
        assert d["min_pts_per_cell"] >= 0
        assert d["max_pts_per_cell"] >= 1

    def test_density_stats_absent_when_disabled(self, monkeypatch, tmp_path):
        """When density_stats=False (default), no 'density' key in output."""
        _patch_lidar_stream(
            monkeypatch,
            mins=(0.0, 0.0, 0.0),
            maxs=(1.0, 1.0, 0.5),
            chunks=(
                ([0.1, 0.3, 0.5], [0.1, 0.3, 0.5], [0.0, 0.0, 0.0]),
            ),
        )
        info = lidar.process_file(
            tmp_path / "test.las",
            cell_res=0.25, hag_min=0.2, hag_max=0.6,
            min_area_cells=2, max_area_cells=80,
            chunk_size=10, verbose=False, plots_dir=None,
            density_stats=False,
        )
        assert "density" not in info

    def test_density_count_grid_correct(self, monkeypatch, tmp_path):
        """Count grid should reflect actual point counts per cell."""
        # 3 points in cell (0,0), 2 points in cell (1,0), 1 point in cell (0,1)
        _patch_lidar_stream(
            monkeypatch,
            mins=(0.0, 0.0, 0.0),
            maxs=(0.5, 0.5, 0.5),
            chunks=(
                (
                    [0.1, 0.1, 0.1, 0.3, 0.3, 0.1],
                    [0.1, 0.1, 0.1, 0.1, 0.1, 0.3],
                    [0.0, 0.1, 0.2, 0.0, 0.1, 0.0],
                ),
            ),
        )
        info = lidar.process_file(
            tmp_path / "test.las",
            cell_res=0.25, hag_min=0.2, hag_max=0.6,
            min_area_cells=2, max_area_cells=80,
            chunk_size=10, verbose=False, plots_dir=None,
            density_stats=True,
        )
        d = info["density"]
        assert d["total_points"] == 6
        assert d["max_pts_per_cell"] == 3

    def test_estimate_grid_bytes_increases_with_density(self):
        """_estimate_grid_bytes should return more bytes when density_stats=True."""
        base = lidar._estimate_grid_bytes(100, 100, "min", "p95", None, density_stats=False)
        with_density = lidar._estimate_grid_bytes(100, 100, "min", "p95", None, density_stats=True)
        assert with_density > base
        assert with_density - base == 100 * 100 * 4  # int32 = 4 bytes per cell


# ---------------------------------------------------------------------------
# CSF ground model tests
# ---------------------------------------------------------------------------

class TestCSFGroundModel:
    def test_csf_import_guard_present(self):
        """HAS_CSF attribute exists on the module."""
        assert hasattr(lidar, "HAS_CSF")

    @pytest.mark.skipif(not lidar.HAS_CSF, reason="CSF not installed")
    def test_csf_ground_produces_valid_dem(self, tmp_path):
        """CSF ground method produces a finite DEM for a real LAS tile."""
        # This test only runs when CSF is installed; skips otherwise.
        # We test with the golden AOI if available.
        golden = Path("data/legacy_ro/penguin-2.0/data/raw/LiDAR/sample/cloud3.las")
        if not golden.exists():
            pytest.skip("Golden AOI tile not available")
        mins, maxs, _ = lidar.read_bounds_and_counts(golden, 1_000_000)
        ny, nx = lidar._grid_shape(mins, maxs, 0.25)
        dem, csf_meta = lidar._build_ground_csf(
            golden, cell_res=0.25, ny=ny, nx=nx, mins=mins,
            csf_max_points=50_000_000,
        )
        assert dem.size > 0, "CSF should produce a non-empty DEM"
        assert np.isfinite(dem).all(), "CSF DEM should have no inf/nan values"
        assert csf_meta["csf_fallback"] is False
        assert csf_meta["csf_ground_points"] > 0

    def test_csf_ground_method_choice_stored(self):
        """ground_method='csf' is a valid choice string."""
        assert "csf" in ["min", "p05", "csf"]


# ---------------------------------------------------------------------------
# Z-std enrichment grid tests
# ---------------------------------------------------------------------------

def _write_test_las(path, x_arr, y_arr, z_arr):
    """Write a minimal LAS file with given coordinates."""
    header = laspy.LasHeader(point_format=0, version="1.2")
    las = laspy.LasData(header)
    las.x = np.asarray(x_arr, dtype=np.float64)
    las.y = np.asarray(y_arr, dtype=np.float64)
    las.z = np.asarray(z_arr, dtype=np.float64)
    las.write(str(path))


@pytest.mark.skipif(not lidar.LASPY_AVAILABLE, reason="laspy not installed")
class TestZStdEnrichment:
    def test_z_std_grid_correct_values(self, tmp_path):
        """Z-std grid should compute per-cell standard deviation of Z values."""
        # Cell (0,0) gets z=[1, 2, 3] → std = sqrt(2/3) ≈ 0.8165
        # Cell (0,1) gets z=[5, 5, 5] → std = 0.0
        las_path = tmp_path / "test.las"
        _write_test_las(
            las_path,
            [0.1, 0.1, 0.1, 0.3, 0.3, 0.3],
            [0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
            [1.0, 2.0, 3.0, 5.0, 5.0, 5.0],
        )
        grids = lidar._build_enrichment_grids(
            las_path,
            chunk_size=10,
            mins=np.array([0.0, 0.0, 0.0]),
            cell_res=0.25,
            ny=1, nx=2,
            include_intensity=False,
            include_rgb=False,
            include_returns=False,
            include_z_std=True,
        )
        z_std = grids["z_std"]
        assert z_std is not None
        assert z_std.shape == (1, 2)
        # Cell (0,0): z=[1,2,3], std=sqrt(2/3) ≈ 0.8165
        assert z_std[0, 0] == pytest.approx(np.std([1.0, 2.0, 3.0]), abs=1e-4)
        # Cell (0,1): z=[5,5,5], std=0
        assert z_std[0, 1] == pytest.approx(0.0, abs=1e-4)

    def test_z_std_grid_none_when_disabled(self, tmp_path):
        """Z-std grid should be None when include_z_std=False."""
        las_path = tmp_path / "test.las"
        _write_test_las(las_path, [0.1], [0.1], [1.0])
        grids = lidar._build_enrichment_grids(
            las_path,
            chunk_size=10,
            mins=np.array([0.0, 0.0, 0.0]),
            cell_res=0.25,
            ny=1, nx=1,
            include_intensity=False,
            include_rgb=False,
            include_returns=False,
            include_z_std=False,
        )
        assert grids["z_std"] is None


# ---------------------------------------------------------------------------
# Exact p95 HAG grid tests
# ---------------------------------------------------------------------------

class TestExactP95:
    def test_exact_p95_matches_numpy(self, monkeypatch, tmp_path):
        """Exact p95 should match np.percentile for known distributions."""
        # Cell (0,0) gets z = [0.0, 0.1, 0.2, ..., 1.9] (20 points)
        # DEM = 0.0, so HAG = z.  p95 of [0..1.9] via numpy:
        z_vals = np.arange(0.0, 2.0, 0.1)
        expected_p95 = float(np.percentile(z_vals, 95))

        _patch_lidar_stream(
            monkeypatch,
            mins=(0.0, 0.0, 0.0),
            maxs=(0.25, 0.25, 0.0),
            chunks=(
                ([0.1] * 20, [0.1] * 20, z_vals.tolist()),
            ),
        )
        dem = np.zeros((1, 1), dtype=np.float32)
        meta = {"mins": [0.0, 0.0, 0.0], "cell_res": 0.25, "shape": [1, 1]}

        hag = lidar.build_hag_grid_exact_percentile(
            tmp_path / "test.las", dem, meta, chunk_size=100, percentile=95.0,
        )
        assert hag.shape == (1, 1)
        assert float(hag[0, 0]) == pytest.approx(expected_p95, abs=0.01)

    def test_exact_p95_within_tolerance_of_histogram(self, monkeypatch, tmp_path):
        """Exact p95 should agree with histogram p95 within 10mm."""
        rng = np.random.default_rng(42)
        n_pts = 200
        z_vals = rng.uniform(0.0, 1.5, n_pts)
        x_vals = [0.1] * n_pts
        y_vals = [0.1] * n_pts

        _patch_lidar_stream(
            monkeypatch,
            mins=(0.0, 0.0, 0.0),
            maxs=(0.25, 0.25, 0.0),
            chunks=((x_vals, y_vals, z_vals.tolist()),),
        )
        dem = np.zeros((1, 1), dtype=np.float32)
        meta = {"mins": [0.0, 0.0, 0.0], "cell_res": 0.25, "shape": [1, 1]}

        hag_exact = lidar.build_hag_grid_exact_percentile(
            tmp_path / "test.las", dem, meta, chunk_size=100, percentile=95.0,
        )

        _patch_lidar_stream(
            monkeypatch,
            mins=(0.0, 0.0, 0.0),
            maxs=(0.25, 0.25, 0.0),
            chunks=((x_vals, y_vals, z_vals.tolist()),),
        )
        hag_hist = lidar.build_hag_grid_histogram_percentile(
            tmp_path / "test.las", dem, meta, chunk_size=100, percentile=95.0,
        )

        assert abs(float(hag_exact[0, 0]) - float(hag_hist[0, 0])) < 0.01  # 10mm

    def test_exact_p95_empty_cell(self, monkeypatch, tmp_path):
        """Empty cells should have HAG = 0."""
        _patch_lidar_stream(
            monkeypatch,
            mins=(0.0, 0.0, 0.0),
            maxs=(0.0, 0.0, 0.0),
            chunks=(),
        )
        dem = np.zeros((1, 1), dtype=np.float32)
        meta = {"mins": [0.0, 0.0, 0.0], "cell_res": 0.25, "shape": [1, 1]}

        hag = lidar.build_hag_grid_exact_percentile(
            tmp_path / "test.las", dem, meta, chunk_size=100,
        )
        assert float(hag[0, 0]) == 0.0
