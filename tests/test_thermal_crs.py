from pipelines.thermal_crs import apply_geotransform, detections_px_to_crs


def test_apply_geotransform_north_up():
    # x = 100 + 2*col, y = 200 - 3*row (typical north-up with negative pixel height)
    gt = (100.0, 2.0, 0.0, 200.0, 0.0, -3.0)
    x, y = apply_geotransform(gt, col=5.0, row=7.0)
    assert x == 110.0
    assert y == 179.0


def test_apply_geotransform_with_rotation_terms():
    gt = (0.0, 1.0, 0.5, 0.0, 0.25, -2.0)
    x, y = apply_geotransform(gt, col=4.0, row=10.0)
    assert x == 9.0
    assert y == -19.0


def test_detections_px_to_crs_adds_xy_and_metadata():
    gt = (100.0, 1.0, 0.0, 200.0, 0.0, -1.0)
    dets = [{"row": 2.0, "col": 3.0, "score": 0.5}, {"row": 0.0, "col": 0.0}]
    out = detections_px_to_crs(dets, geotransform=gt, crs="EPSG:32720")

    assert out.crs == "EPSG:32720"
    assert out.schema_version == "1"
    assert out.purpose == "qc_alignment"
    assert out.temperature_calibrated is False
    assert len(out.detections) == 2
    assert out.detections[0]["x"] == 103.0
    assert out.detections[0]["y"] == 198.0

