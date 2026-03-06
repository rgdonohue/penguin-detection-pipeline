#!/usr/bin/env python3
"""
Verify claims about TrueView 515 LAS files:
1. Z values are ellipsoidal heights (GRS 1980 via POSGAR 2007)
2. Compound CRS with VERT_CS["Ellipsoid (Meters)"]
3. Z range ~7–71 m across San Lorenzo tiles
4. EPSG:5345 alone is 2D (vertical comes from LAS WKT VLR)
5. EGM2008 geoid undulation ~+17 m at San Lorenzo

Usage:
    python scripts/verify_las_crs_claims.py --data-root data/2025/
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    import laspy
except ImportError:
    laspy = None

try:
    import pyproj
except ImportError:
    pyproj = None


def find_san_lorenzo_las(root: Path) -> list[Path]:
    """Find San Lorenzo LAS files (TrueView 515, POSGAR)."""
    files = []
    for p in root.rglob("*.las"):
        if "San Lorenzo" in p.name:
            files.append(p)
    for p in root.rglob("*.laz"):
        if "San Lorenzo" in p.name:
            files.append(p)
    return sorted(files, key=str)


def verify_compound_crs_and_z(las_path: Path) -> dict:
    """Extract full WKT and Z bounds from one LAS file."""
    out = {"path": str(las_path), "z_min": None, "z_max": None, "crs_wkt_full": None, "error": None}
    if not laspy:
        out["error"] = "laspy not available"
        return out
    try:
        with laspy.open(str(las_path)) as fh:
            h = fh.header
            out["z_min"] = float(h.z_min)
            out["z_max"] = float(h.z_max)
            if hasattr(h, "parse_crs"):
                crs_obj = h.parse_crs()
                if crs_obj is not None:
                    out["crs_wkt_full"] = str(crs_obj).strip()
    except Exception as e:
        out["error"] = str(e)
    return out


def verify_epsg_5345_is_2d() -> dict:
    """Check that EPSG:5345 (without vertical) is 2D only."""
    out = {"epsg": 5345, "axis_count": None, "name": None, "error": None}
    if not pyproj:
        out["error"] = "pyproj not available"
        return out
    try:
        crs = pyproj.CRS.from_epsg(5345)
        out["axis_count"] = len(crs.axis_info)
        out["name"] = crs.name
    except Exception as e:
        out["error"] = str(e)
    return out


def estimate_geoid_undulation() -> dict:
    """
    Estimate EGM2008 geoid undulation at San Lorenzo (roughly -45.0°S, -66.3°W).
    Uses pyproj pipeline if proj has EGM grid; otherwise reports that manual
    lookup is needed.
    """
    out = {"lat": -45.0, "lon": -66.3, "undulation_m": None, "method": None, "error": None}
    if not pyproj:
        out["error"] = "pyproj not available"
        return out
    try:
        # EGM2008 geoid height (ellipsoid - geoid)
        trans = pyproj.Transformer.from_pipeline(
            "+proj=vgridshift +grids=egm08_25.gtx +multiplier=1"
        )
        # At (lon, lat), get geoid offset: pipeline returns geoid height
        h_ellip = 50.0  # placeholder ellipsoidal height (m)
        h_geoid = trans.transform(-66.3, -45.0, h_ellip)
        out["undulation_m"] = round(float(h_ellip - h_geoid), 2)
        out["method"] = "pyproj vgridshift (egm08_25.gtx)"
    except Exception as e:
        out["error"] = str(e)
        out["method"] = "Failed; use NOAA NCEI Geoid Height Calculator or similar"
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify LAS CRS and Z claims")
    parser.add_argument("--data-root", type=Path, default=Path("data/2025"), help="Root with LAS files")
    parser.add_argument("--check-geoid", action="store_true", help="Attempt EGM2008 undulation (needs proj datum grid)")
    args = parser.parse_args()

    root = args.data_root.resolve()
    if not root.exists():
        print(f"ERROR: {root} does not exist")
        return

    print("=" * 70)
    print("1. EPSG:5345 is 2D (horizontal only)")
    print("=" * 70)
    epsg_info = verify_epsg_5345_is_2d()
    if epsg_info.get("error"):
        print(f"   Error: {epsg_info['error']}")
    else:
        print(f"   EPSG:5345 = {epsg_info['name']}")
        print(f"   Axis count: {epsg_info['axis_count']} (2 = horizontal only)")
        if epsg_info["axis_count"] == 2:
            print("   ✓ CONFIRMED: EPSG:5345 is 2D; vertical must come from LAS WKT VLR")

    print("\n" + "=" * 70)
    print("2. San Lorenzo LAS: CRS WKT and Z bounds")
    print("=" * 70)
    files = find_san_lorenzo_las(root)
    if not files:
        print(f"   No San Lorenzo LAS found under {root}")
        return
    print(f"   Found {len(files)} file(s)")

    all_z_min, all_z_max = None, None
    for p in files:
        info = verify_compound_crs_and_z(p)
        rel = p.relative_to(root) if str(p).startswith(str(root)) else p.name
        if info.get("error"):
            print(f"\n   {rel}: ERROR {info['error']}")
            continue
        print(f"\n   {rel}")
        print(f"      Z range: [{info['z_min']:.2f}, {info['z_max']:.2f}] m")
        if all_z_min is None:
            all_z_min, all_z_max = info["z_min"], info["z_max"]
        else:
            all_z_min = min(all_z_min, info["z_min"])
            all_z_max = max(all_z_max, info["z_max"])

        wkt = info.get("crs_wkt_full") or ""
        if "COMPD_CS" in wkt:
            print("      ✓ WKT contains COMPD_CS (compound CRS)")
        if "VERT_CS" in wkt and "Ellipsoid" in wkt:
            print("      ✓ WKT contains VERT_CS['Ellipsoid (Meters)']")
        if "ellipsoidal" in wkt.lower() or "Ellipsoid" in wkt:
            print("      ✓ Vertical datum: Ellipsoid (ellipsoidal height)")
        if wkt:
            print("      Full WKT (first 800 chars):")
            print("      " + wkt[:800].replace("\n", "\n      "))

    if all_z_min is not None and all_z_max is not None:
        print(f"\n   Aggregate Z range across tiles: [{all_z_min:.2f}, {all_z_max:.2f}] m")
        if 5 <= all_z_min <= 15 and 65 <= all_z_max <= 80:
            print("   ✓ Consistent with ~7–71 m claim for coastal Patagonia (ellipsoidal)")

    if args.check_geoid:
        print("\n" + "=" * 70)
        print("3. EGM2008 geoid undulation at San Lorenzo (~-45°S, -66°W)")
        print("=" * 70)
        geo = estimate_geoid_undulation()
        if geo.get("error"):
            print(f"   Error: {geo['error']}")
            print("   → Use NOAA NCEI Geoid Height Calculator for manual verification")
        else:
            print(f"   Undulation (ellipsoid - geoid): ~{geo['undulation_m']} m")
            print(f"   Method: {geo['method']}")
            if geo["undulation_m"] and 15 <= geo["undulation_m"] <= 20:
                print("   ✓ Consistent with ~+17 m claim for Patagonia")


if __name__ == "__main__":
    main()
