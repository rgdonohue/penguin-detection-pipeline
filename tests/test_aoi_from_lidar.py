import numpy as np

from pipelines.aoi_from_lidar import polygonize_mask


def test_polygonize_mask_simple_rectangle() -> None:
    # 10x20 rectangle in a 50x50 grid
    mask = np.zeros((50, 50), dtype=bool)
    mask[10:20, 15:35] = True
    ring = polygonize_mask(mask, origin_xy=(1000.0, 2000.0), cell_res_m=1.0)
    assert len(ring) >= 4
    assert ring[0] == ring[-1]  # closed

    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    # Bounds should be near the rectangle extents (within a couple cells due to contouring at 0.5)
    assert min(xs) <= 1000.0 + 15.5
    assert max(xs) >= 1000.0 + 34.5
    assert min(ys) <= 2000.0 + 10.5
    assert max(ys) >= 2000.0 + 19.5


