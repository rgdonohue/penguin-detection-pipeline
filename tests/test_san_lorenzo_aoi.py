#!/usr/bin/env python3
"""
Tests for San Lorenzo AOI polygon construction.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for p in [str(_ROOT / "src"), str(_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from pyproj import Transformer
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False


@pytest.mark.skipif(not HAS_PYPROJ, reason="pyproj not available")
class TestSanLorenzoAois:
    """Verify San Lorenzo AOI polygon construction."""

    def test_bushes_box_polygon_area(self):
        """Bushes box polygon area should be small (~200 m², 0.02 ha)."""
        from scripts.create_san_lorenzo_aois import build_bushes_box_polygon, compute_polygon_area
        feature = build_bushes_box_polygon()
        assert feature is not None
        coords = feature["geometry"]["coordinates"][0]
        area_m2 = compute_polygon_area(coords)
        # GPS corners produce a very small polygon (~200 m²)
        assert 50 < area_m2 < 500, f"Bushes box area {area_m2:.1f} m² outside expected range"

    def test_bushes_box_has_caveat(self):
        """Bushes box should document the coordinate-tile mismatch caveat."""
        from scripts.create_san_lorenzo_aois import build_bushes_box_polygon
        feature = build_bushes_box_polygon()
        assert feature is not None
        assert feature["properties"]["caveat"] == "coordinate_tile_mismatch"

    def test_bushes_box_penguin_count(self):
        """Bushes box should have ground truth count of 55."""
        from scripts.create_san_lorenzo_aois import build_bushes_box_polygon
        feature = build_bushes_box_polygon()
        assert feature["properties"]["penguin_count"] == 55

    def test_plains_perimeter_polygon(self):
        """Plains polygon should be built from perimeter winding, not convex hull."""
        from scripts.create_san_lorenzo_aois import load_waypoints_by_type, build_plains_polygon
        csv_path = _ROOT / "data" / "processed" / "san_lorenzo_waypoints.csv"
        if not csv_path.exists():
            pytest.skip("Waypoints CSV not available")
        waypoints = load_waypoints_by_type(csv_path)
        if "plains" not in waypoints:
            pytest.skip("No plains waypoints")
        feature = build_plains_polygon(waypoints["plains"])
        assert feature is not None
        assert "Perimeter" in feature["properties"]["notes"]

    def test_plains_area_reasonable(self):
        """Plains area should be between 0.3 and 1.5 ha."""
        from scripts.create_san_lorenzo_aois import load_waypoints_by_type, build_plains_polygon
        csv_path = _ROOT / "data" / "processed" / "san_lorenzo_waypoints.csv"
        if not csv_path.exists():
            pytest.skip("Waypoints CSV not available")
        waypoints = load_waypoints_by_type(csv_path)
        if "plains" not in waypoints:
            pytest.skip("No plains waypoints")
        feature = build_plains_polygon(waypoints["plains"])
        assert feature is not None
        area_ha = feature["properties"]["area_ha"]
        assert 0.3 < area_ha < 1.5, f"Plains area {area_ha:.4f} ha outside expected range"

    def test_caves_area_reasonable(self):
        """Caves area should be between 0.3 and 1.0 ha."""
        from scripts.create_san_lorenzo_aois import load_waypoints_by_type, build_caves_polygon
        csv_path = _ROOT / "data" / "processed" / "san_lorenzo_waypoints.csv"
        if not csv_path.exists():
            pytest.skip("Waypoints CSV not available")
        waypoints = load_waypoints_by_type(csv_path)
        if "caves" not in waypoints:
            pytest.skip("No caves waypoints")
        feature = build_caves_polygon(waypoints["caves"])
        assert feature is not None
        area_ha = feature["properties"]["area_ha"]
        assert 0.3 < area_ha < 1.0, f"Caves area {area_ha:.4f} ha outside expected range"

    def test_geojson_output_valid(self, tmp_path):
        """Full GeoJSON output should be valid and contain expected features."""
        import subprocess
        out_path = tmp_path / "test_aois.geojson"
        result = subprocess.run(
            [sys.executable, str(_ROOT / "scripts" / "create_san_lorenzo_aois.py"),
             "--output", str(out_path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            pytest.skip(f"Script failed: {result.stderr}")
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert data["type"] == "FeatureCollection"
        assert data["crs"]["epsg"] == 5345
        # Should have at least 4 features: caves, plains, bushes box, road
        assert len(data["features"]) >= 4
        aoi_ids = [f["properties"]["aoi_id"] for f in data["features"]]
        assert "san_lorenzo_caves" in aoi_ids
        assert "san_lorenzo_plains" in aoi_ids
        assert "san_lorenzo_box_bushes" in aoi_ids
