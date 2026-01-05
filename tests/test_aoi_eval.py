import json
from pathlib import Path

import pytest

from pipelines.aoi_eval import AoiEvalParams, run


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def test_aoi_eval_counts_and_area(tmp_path: Path) -> None:
    lidar = tmp_path / "lidar.json"
    aoi = tmp_path / "aoi.geojson"
    out = tmp_path / "out.json"

    _write_json(
        lidar,
        {
            "schema_version": "1",
            "purpose": "lidar_candidates",
            "crs": {"epsg": 32720},
            "files": [
                {
                    "path": "tile.las",
                    "detections": [
                        {"id": "a", "x": 0.5, "y": 0.5},
                        {"id": "b", "x": 1.5, "y": 1.5},
                        {"id": "c", "x": 5.0, "y": 5.0},
                    ],
                }
            ],
        },
    )

    # Square from (0,0) to (2,2) area=4.
    _write_json(
        aoi,
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "box"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
                    },
                }
            ],
        },
    )

    run(AoiEvalParams(lidar_summary=lidar, aoi_geojson=aoi, out_path=out, aoi_crs_epsg=32720))
    payload = json.loads(out.read_text())
    assert payload["purpose"] == "lidar_aoi_eval"
    assert payload["crs"] == "EPSG:32720"
    assert payload["results"][0]["aoi_id"] == "box"
    assert payload["results"][0]["count"] == 2
    assert payload["results"][0]["area_m2"] == pytest.approx(4.0)
    assert payload["results"][0]["density_per_ha"] == pytest.approx(2 / (4.0 / 10_000.0))


def test_aoi_eval_hole_excludes_points(tmp_path: Path) -> None:
    lidar = tmp_path / "lidar.json"
    aoi = tmp_path / "aoi.geojson"
    out = tmp_path / "out.json"

    _write_json(
        lidar,
        {
            "schema_version": "1",
            "purpose": "lidar_candidates",
            "crs": {"epsg": 32720},
            "detections": [
                {"id": "inside_hole", "x": 1.0, "y": 1.0},
                {"id": "inside_shell", "x": 0.25, "y": 0.25},
            ],
        },
    )

    # Outer square (0,0)-(2,2), hole square (0.5,0.5)-(1.5,1.5)
    _write_json(
        aoi,
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"id": "donut"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]],
                            [[0.5, 0.5], [1.5, 0.5], [1.5, 1.5], [0.5, 1.5], [0.5, 0.5]],
                        ],
                    },
                }
            ],
        },
    )

    run(AoiEvalParams(lidar_summary=lidar, aoi_geojson=aoi, out_path=out, aoi_crs_epsg=32720))
    payload = json.loads(out.read_text())
    assert payload["results"][0]["count"] == 1


def test_aoi_eval_crs_mismatch_raises(tmp_path: Path) -> None:
    lidar = tmp_path / "lidar.json"
    aoi = tmp_path / "aoi.geojson"
    out = tmp_path / "out.json"

    _write_json(lidar, {"crs": {"epsg": 32720}, "detections": [{"x": 0.0, "y": 0.0}]})
    _write_json(aoi, {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}}]})

    with pytest.raises(ValueError, match="CRS mismatch"):
        run(AoiEvalParams(lidar_summary=lidar, aoi_geojson=aoi, out_path=out, aoi_crs_epsg=4326))


def test_aoi_eval_geojson_crs84_is_detected_and_guarded(tmp_path: Path) -> None:
    lidar = tmp_path / "lidar.json"
    aoi = tmp_path / "aoi.geojson"
    out = tmp_path / "out.json"

    # Use EPSG:4326 so we exercise the explicit "geographic CRS" guard rather than CRS mismatch.
    _write_json(lidar, {"crs": {"epsg": 4326}, "detections": [{"id": "d0", "x": 0.0, "y": 0.0}]})
    _write_json(
        aoi,
        {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
            "features": [
                {
                    "type": "Feature",
                    "properties": {"id": "aoi"},
                    "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
                }
            ],
        },
    )

    # CRS84 implies degrees → must fail unless explicitly allowed.
    with pytest.raises(ValueError, match="geographic"):
        run(AoiEvalParams(lidar_summary=lidar, aoi_geojson=aoi, out_path=out, aoi_crs_epsg=None))


def test_aoi_eval_allow_geographic_crs_omits_area_and_density(tmp_path: Path) -> None:
    lidar = tmp_path / "lidar.json"
    aoi = tmp_path / "aoi.geojson"
    out = tmp_path / "out.json"

    _write_json(lidar, {"crs": {"epsg": 4326}, "detections": [{"id": "d0", "x": 0.5, "y": 0.5}]})
    _write_json(
        aoi,
        {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
            "features": [
                {
                    "type": "Feature",
                    "properties": {"id": "aoi"},
                    "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
                }
            ],
        },
    )

    run(AoiEvalParams(lidar_summary=lidar, aoi_geojson=aoi, out_path=out, aoi_crs_epsg=None, allow_geographic_crs=True))
    payload = json.loads(out.read_text())
    assert payload["results"][0]["count"] == 1
    assert payload["results"][0]["area_m2"] is None
    assert payload["results"][0]["density_per_ha"] is None


def test_aoi_eval_epsg_urn_normalization(tmp_path: Path) -> None:
    lidar = tmp_path / "lidar.json"
    aoi = tmp_path / "aoi.geojson"
    out = tmp_path / "out.json"

    _write_json(lidar, {"crs": {"epsg": 32720}, "detections": [{"id": "d0", "x": 0.5, "y": 0.5}]})
    _write_json(
        aoi,
        {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32720"}},
            "features": [
                {
                    "type": "Feature",
                    "properties": {"id": "aoi"},
                    "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]},
                }
            ],
        },
    )

    run(AoiEvalParams(lidar_summary=lidar, aoi_geojson=aoi, out_path=out))
    payload = json.loads(out.read_text())
    assert payload["aoi_crs"] == "EPSG:32720"



