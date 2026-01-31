#!/usr/bin/env python3
"""
Extract GPS waypoints for AOI polygons from the Ground Truthing PDF.

Provides CSV templates for manual entry and validates coordinates.
Argentina survey area: lat ~-42 to -43, lon ~-64 to -66.

Usage:
  # Emit empty CSV templates for all sites
  python extract_waypoints.py --templates --out-dir ../data/waypoints

  # Validate and normalize an existing CSV
  python extract_waypoints.py --validate ../data/waypoints/san_lorenzo_caves.csv

  # Parse DMS line like "42°05'12.3\"S 63°52'20.1\"W" to decimal
  python extract_waypoints.py --parse-dms "42°05'12.3\"S 63°52'20.1\"W"
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

# Argentina Patagonia bounds (loose)
LAT_MIN, LAT_MAX = -43.5, -41.0
LON_MIN, LON_MAX = -66.0, -62.0

SITES = [
    ("caleta_tiny_island", "Caleta Tiny Island", "boundary"),
    ("caleta_small_island", "Caleta Small Island", "boundary"),
    ("caleta_box1", "Caleta Box Count 1", "point"),
    ("caleta_box2", "Caleta Box Count 2", "point"),
    ("san_lorenzo_caves", "San Lorenzo Caves", "edge"),
    ("san_lorenzo_plains", "San Lorenzo Plains", "edge"),
    ("san_lorenzo_road", "San Lorenzo Road", "edge"),
    ("san_lorenzo_box_caves", "San Lorenzo Box Caves", "point"),
    ("san_lorenzo_box_bushes", "San Lorenzo Box Bushes", "point"),
]

CSV_COLUMNS = ["lat", "lon", "point_type", "description"]


def dms_to_decimal(dms_str: str) -> tuple[float, float] | None:
    """Parse DMS string to (lat, lon) decimal degrees.

    Accepts formats like:
      - 42°05'12.3"S 63°52'20.1"W
      - 42 05 12.3 S, 63 52 20.1 W
      - -42.0867, -63.8736 (pass-through)
    """
    s = dms_str.strip()
    # Already decimal
    m = re.match(r"^(-?\d+\.?\d*)\s*[,;\s]\s*(-?\d+\.?\d*)\s*$", s)
    if m:
        return (float(m.group(1)), float(m.group(2)))

    # DMS lat
    lat_m = re.search(
        r"(\d+)\s*[°º]\s*(\d+)\s*['′]?\s*(\d*(?:\.\d+)?)\s*[\"″]?\s*([NS])",
        s,
        re.IGNORECASE,
    )
    # DMS lon
    lon_m = re.search(
        r"(\d+)\s*[°º]\s*(\d+)\s*['′]?\s*(\d*(?:\.\d+)?)\s*[\"″]?\s*([EW])",
        s,
        re.IGNORECASE,
    )
    if not lat_m or not lon_m:
        return None

    def dms_to_dec(deg: int, min_: int, sec: float, hem: str) -> float:
        dec = float(deg) + float(min_) / 60 + float(sec or 0) / 3600
        if hem.upper() in ("S", "W"):
            dec = -dec
        return dec

    lat = dms_to_dec(
        int(lat_m.group(1)), int(lat_m.group(2)), float(lat_m.group(3) or 0), lat_m.group(4)
    )
    lon = dms_to_dec(
        int(lon_m.group(1)), int(lon_m.group(2)), float(lon_m.group(3) or 0), lon_m.group(4)
    )
    return (lat, lon)


def in_bounds(lat: float, lon: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


def validate_row(row: dict) -> list[str]:
    """Return list of validation error messages for a row."""
    errs = []
    lat_s = (row.get("lat") or "").strip()
    lon_s = (row.get("lon") or "").strip()
    if not lat_s or not lon_s:
        return []  # skip empty
    try:
        lat = float(lat_s)
        lon = float(lon_s)
    except ValueError:
        errs.append(f"Invalid numbers: lat={lat_s!r} lon={lon_s!r}")
        return errs
    if not in_bounds(lat, lon):
        errs.append(f"Out of Argentina bounds: ({lat}, {lon})")
    return errs


def emit_templates(out_dir: Path) -> None:
    """Write empty CSV templates for each site."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for site_id, name, _ in SITES:
        path = out_dir / f"{site_id}.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            w.writeheader()
        print(f"  {path}")


def validate_file(path: Path) -> bool:
    """Validate CSV file; print errors. Return True if all valid."""
    path = Path(path)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return False
    ok = True
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if r.fieldnames and set(CSV_COLUMNS) - set(r.fieldnames or []):
            print(f"Expected columns: {CSV_COLUMNS}", file=sys.stderr)
        for i, row in enumerate(r, start=2):
            errs = validate_row(row)
            if errs:
                ok = False
                for e in errs:
                    print(f"  Row {i}: {e}", file=sys.stderr)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="GPS waypoint extraction and validation")
    ap.add_argument("--templates", action="store_true", help="Emit empty CSV templates")
    ap.add_argument("--out-dir", type=Path, default=Path("../data/waypoints"), help="Output dir for templates")
    ap.add_argument("--validate", type=Path, metavar="CSV", help="Validate a waypoints CSV")
    ap.add_argument("--parse-dms", type=str, metavar="STR", help="Parse DMS string to lat,lon")
    args = ap.parse_args()

    if args.parse_dms:
        res = dms_to_decimal(args.parse_dms)
        if res is None:
            print("Parse failed.", file=sys.stderr)
            return 1
        print(f"{res[0]:.6f}, {res[1]:.6f}")
        return 0

    if args.validate is not None:
        return 0 if validate_file(args.validate) else 1

    if args.templates:
        script_dir = Path(__file__).resolve().parent
        out = (script_dir / args.out_dir).resolve()
        print(f"Writing templates to {out}")
        emit_templates(out)
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
