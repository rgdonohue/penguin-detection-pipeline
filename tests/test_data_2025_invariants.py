import json
from pathlib import Path

import pytest


CATALOGUE_PATH = Path("data/2025/lidar_catalogue_full.json")
SAN_LORENZO_ANALYSIS_PATH = Path("data/processed/san_lorenzo_analysis.json")


def _read_json(path: Path) -> dict:
    if not path.exists():
        pytest.skip(f"Missing required file: {path}")
    return json.loads(path.read_text())


def test_lidar_catalogue_full_invariants():
    catalogue = _read_json(CATALOGUE_PATH)
    assert catalogue.get("total_files") == 24

    sites = catalogue.get("sites")
    assert isinstance(sites, dict) and sites, "Expected non-empty 'sites' mapping"

    total_files = 0
    total_points = 0
    total_size_mb = 0.0

    for site_name, meta in sites.items():
        assert isinstance(site_name, str) and site_name
        assert isinstance(meta, dict)
        assert "files" in meta, f"Site missing files: {site_name}"
        assert "sensor" in meta, f"Site missing sensor: {site_name}"
        assert "crs" in meta, f"Site missing CRS: {site_name}"

        files = meta["files"]
        assert isinstance(files, list) and files, f"Site has no files: {site_name}"
        total_files += len(files)

        total_points += int(meta.get("total_points", 0))
        total_size_mb += float(meta.get("total_size_mb", 0.0))

        sensor = meta["sensor"]
        for entry in files:
            assert "file" in entry, f"File entry missing path in {site_name}"
            assert "crs_name" in entry, f"File entry missing CRS name in {site_name}"

            crs_name = str(entry.get("crs_name", ""))
            if sensor == "DJI L2":
                # DJI L2 is expected to be delivered in UTM 20S (EPSG:32720).
                assert entry.get("crs_epsg") == 32720, (
                    f"Expected EPSG:32720 for DJI L2 in {site_name}; "
                    f"got {entry.get('crs_epsg')} ({crs_name})"
                )
                assert "UTM zone 20S" in crs_name
            elif sensor == "GeoCue TrueView 515":
                # TrueView 515 is expected in POSGAR 2007 / Argentina 3 (commonly EPSG:5345).
                assert "POSGAR" in crs_name, (
                    f"Expected POSGAR CRS for TrueView 515 in {site_name}; got {crs_name}"
                )

    assert total_files == 24
    assert total_points == 753_786_458
    assert total_size_mb == pytest.approx(25_822.7, abs=0.2)


def test_san_lorenzo_analysis_invariants():
    analysis = _read_json(SAN_LORENZO_ANALYSIS_PATH)
    totals = analysis.get("totals")
    assert isinstance(totals, dict)

    assert totals.get("grand_total") == 3705
    assert totals.get("san_lorenzo") + totals.get("caleta") == totals.get("grand_total")

    # Guard against silent structure drift (9 site groups).
    assert isinstance(analysis.get("san_lorenzo"), dict)
    assert isinstance(analysis.get("caleta"), dict)
    assert len(analysis["san_lorenzo"]) == 5
    assert len(analysis["caleta"]) == 4


def test_san_lorenzo_utm_reprojected_las_files_present():
    reprojected_dir = Path("data/2025/San_Lorenzo_UTM")
    if not reprojected_dir.exists():
        pytest.skip("Reprojected San Lorenzo UTM directory not present")

    expected = [
        reprojected_dir / "box_count_11.9.las",
        reprojected_dir / "box_count_11.10.las",
    ]
    for path in expected:
        assert path.exists(), f"Missing expected reprojected file: {path}"
        assert path.stat().st_size > 0, f"Empty reprojected file: {path}"

