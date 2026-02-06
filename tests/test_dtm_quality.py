"""Unit tests for pipelines/dtm_quality.py."""

import numpy as np
import pytest

from pipelines.dtm_quality import compute_local_roughness, compute_dtm_quality_metrics


class TestComputeLocalRoughness:
    def test_flat_dem_has_zero_roughness(self):
        dem = np.full((10, 10), 5.0, dtype=np.float32)
        roughness = compute_local_roughness(dem, kernel_size=3)
        assert roughness.shape == dem.shape
        assert np.allclose(roughness, 0.0, atol=1e-6)

    def test_noisy_dem_has_nonzero_roughness(self):
        rng = np.random.default_rng(42)
        dem = rng.normal(0.0, 1.0, (20, 20)).astype(np.float32)
        roughness = compute_local_roughness(dem, kernel_size=3)
        assert roughness.shape == dem.shape
        assert float(np.mean(roughness)) > 0.1


class TestComputeDtmQualityMetrics:
    def test_basic_metrics(self):
        dem = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        count_grid = np.array([[10, 5], [0, 20]], dtype=np.int32)
        result = compute_dtm_quality_metrics(dem, count_grid, cell_res=0.25)

        assert result["cell_res"] == 0.25
        ps = result["point_stats"]
        assert ps["n_cells"] == 4
        assert ps["empty_cells"] == 1
        assert ps["cells_with_data"] == 3
        assert ps["total_points"] == 35
        assert ps["pct_empty"] == 25.0
        assert ps["min_pts_per_cell"] == 0
        assert ps["max_pts_per_cell"] == 20

    def test_quality_flags_high_empty(self):
        dem = np.ones((10, 10), dtype=np.float32)
        count_grid = np.zeros((10, 10), dtype=np.int32)
        # Only 10% occupied
        count_grid[0, :] = 5
        result = compute_dtm_quality_metrics(dem, count_grid, cell_res=0.25)
        flags = result["quality_flags"]
        assert any("HIGH_EMPTY_CELLS" in f for f in flags)

    def test_quality_flags_low_support(self):
        dem = np.ones((4, 4), dtype=np.float32)
        count_grid = np.ones((4, 4), dtype=np.int32)  # median=1 < 3
        result = compute_dtm_quality_metrics(dem, count_grid, cell_res=0.25)
        flags = result["quality_flags"]
        assert any("LOW_SUPPORT" in f for f in flags)

    def test_no_flags_for_good_data(self):
        dem = np.ones((10, 10), dtype=np.float32)
        count_grid = np.full((10, 10), 50, dtype=np.int32)
        result = compute_dtm_quality_metrics(dem, count_grid, cell_res=0.25)
        assert result["quality_flags"] == []

    def test_dem_stats(self):
        dem = np.array([[0.0, 10.0], [5.0, 15.0]], dtype=np.float32)
        count_grid = np.full((2, 2), 10, dtype=np.int32)
        result = compute_dtm_quality_metrics(dem, count_grid, cell_res=0.25)
        ds = result["dem_stats"]
        assert ds["min_z"] == 0.0
        assert ds["max_z"] == 15.0
        assert ds["range_z"] == 15.0

    def test_roughness_stats_present(self):
        rng = np.random.default_rng(42)
        dem = rng.normal(0.0, 0.5, (20, 20)).astype(np.float32)
        count_grid = np.full((20, 20), 10, dtype=np.int32)
        result = compute_dtm_quality_metrics(dem, count_grid, cell_res=0.25)
        rs = result["roughness_stats"]
        assert rs["kernel_size"] == 3
        assert rs["p95"] is not None
        assert rs["p95"] > 0
