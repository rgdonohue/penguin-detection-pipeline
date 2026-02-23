import json
from pathlib import Path
from typing import Optional

import numpy as np
import pytest

from pipelines.fusion import FusionParams, run


rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin  # noqa: E402


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj))


def _write_raster(path: Path, values: np.ndarray, *, epsg: int, nodata: Optional[float] = None) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=values.shape[0],
        width=values.shape[1],
        count=1,
        dtype=values.dtype,
        crs=f"EPSG:{int(epsg)}",
        transform=from_origin(0.0, 5.0, 1.0, 1.0),
        nodata=nodata,
    ) as ds:
        ds.write(values, 1)


def test_thermal_window_sampling_mean_max_and_z(tmp_path: Path):
    lidar_path = tmp_path / "lidar.json"
    thermal_path = tmp_path / "thermal.json"
    raster_path = tmp_path / "thermal.tif"
    out_path = tmp_path / "fusion.json"

    _write_json(
        lidar_path,
        {
            "crs": "EPSG:32720",
            "detections": [{"id": "lidar_1", "x": 2.5, "y": 2.5}],
        },
    )
    _write_json(thermal_path, {"crs": "EPSG:32720", "detections": []})
    _write_raster(raster_path, np.arange(25, dtype=np.float32).reshape(5, 5), epsg=32720)

    run(
        FusionParams(
            lidar_summary=lidar_path,
            thermal_summary=thermal_path,
            out_path=out_path,
            thermal_raster=raster_path,
            thermal_core_radius_m=0.6,
            thermal_neighborhood_inner_radius_m=1.0,
            thermal_neighborhood_outer_radius_m=1.5,
            thermal_z_method="robust",
        )
    )

    out = json.loads(out_path.read_text())
    det = out["lidar"][0]
    assert det["thermal_mean_c"] == pytest.approx(12.0)
    assert det["thermal_max_c"] == pytest.approx(12.0)
    assert det["thermal_z_local"] == pytest.approx(0.0)
    assert det["thermal_sample_reason"] is None
    assert det["thermal_n_core"] == 1
    assert det["thermal_n_neighborhood"] == 8


def test_thermal_sampling_marks_core_nodata(tmp_path: Path):
    lidar_path = tmp_path / "lidar.json"
    thermal_path = tmp_path / "thermal.json"
    raster_path = tmp_path / "thermal_nodata.tif"
    out_path = tmp_path / "fusion.json"

    values = np.arange(25, dtype=np.float32).reshape(5, 5)
    values[2, 2] = -9999.0

    _write_json(
        lidar_path,
        {
            "crs": "EPSG:32720",
            "detections": [{"id": "lidar_1", "x": 2.5, "y": 2.5}],
        },
    )
    _write_json(thermal_path, {"crs": "EPSG:32720", "detections": []})
    _write_raster(raster_path, values, epsg=32720, nodata=-9999.0)

    run(
        FusionParams(
            lidar_summary=lidar_path,
            thermal_summary=thermal_path,
            out_path=out_path,
            thermal_raster=raster_path,
            thermal_core_radius_m=0.6,
            thermal_neighborhood_inner_radius_m=1.0,
            thermal_neighborhood_outer_radius_m=1.5,
        )
    )

    out = json.loads(out_path.read_text())
    det = out["lidar"][0]
    assert det["thermal_mean_c"] is None
    assert det["thermal_max_c"] is None
    assert det["thermal_z_local"] is None
    assert det["thermal_sample_reason"] == "core_nodata"


def test_thermal_sampling_rejects_crs_mismatch_with_raster(tmp_path: Path):
    lidar_path = tmp_path / "lidar.json"
    thermal_path = tmp_path / "thermal.json"
    raster_path = tmp_path / "thermal_bad_crs.tif"
    out_path = tmp_path / "fusion.json"

    _write_json(
        lidar_path,
        {
            "crs": "EPSG:32720",
            "detections": [{"id": "lidar_1", "x": 2.5, "y": 2.5}],
        },
    )
    _write_json(thermal_path, {"crs": "EPSG:32720", "detections": []})
    _write_raster(raster_path, np.arange(25, dtype=np.float32).reshape(5, 5), epsg=5345)

    with pytest.raises(ValueError, match="CRS mismatch"):
        run(
            FusionParams(
                lidar_summary=lidar_path,
                thermal_summary=thermal_path,
                out_path=out_path,
                thermal_raster=raster_path,
            )
        )
