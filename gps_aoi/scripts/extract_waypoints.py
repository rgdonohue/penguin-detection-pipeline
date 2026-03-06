#!/usr/bin/env python3
"""
Extract GPS waypoints for AOI polygons from the Ground Truthing PDF.

Provides CSV templates for manual entry and validates coordinates.
Argentina survey area: lat ~-42 to -43, lon ~-64 to -66.

Usage:
  # Emit empty CSV templates for all sites
  python extract_waypoints.py --templates --out-dir ../data/waypoints

  # Extract waypoints from PDF text and write per-site CSVs
  python extract_waypoints.py --from-pdf-text ../data/raw/pdf_extract.txt --out-dir ../data/waypoints

  # Validate and normalize an existing CSV
  python extract_waypoints.py --validate ../data/waypoints/san_lorenzo_caves.csv

  # Parse DMS or decimal+hemisphere line to decimal degrees
  python extract_waypoints.py --parse-dms "42.085273 S, 63.866958 W"
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


def parse_decimal_hemisphere(s: str) -> tuple[float, float] | None:
    """Parse decimal degrees with hemisphere letters, e.g. '42.085273 S, 63.866958 W'.

    Returns (lat, lon) in signed decimal degrees, or None if not matched.
    """
    s = s.strip()
    # One pair: 42.085273 S, 63.866958 W (lat N/S, lon E/W)
    m = re.search(
        r"(\d+\.?\d*)\s*([NS])\s*[,;]\s*(\d+\.?\d*)\s*([EW])",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None
    lat_val = float(m.group(1))
    lat_hem = m.group(2).upper()
    lon_val = float(m.group(3))
    lon_hem = m.group(4).upper()
    lat = -lat_val if lat_hem == "S" else lat_val
    lon = -lon_val if lon_hem == "W" else lon_val
    return (lat, lon)


def parse_coord_pairs(line: str) -> list[tuple[float, float]]:
    """Extract all decimal+hemisphere coordinate pairs from a line.

    Handles 'Start: 42.086263 S, 63.874072 W and 42.086285 S, 63.874350 W'
    or single '42.085273 S, 63.866958 W'. Returns list of (lat, lon).
    """
    pairs: list[tuple[float, float]] = []
    # Match one or more "num S, num W" or "num N, num E" (with optional "and" between)
    pattern = re.compile(
        r"(\d+\.?\d*)\s*([NS])\s*[,;]\s*(\d+\.?\d*)\s*([EW])",
        re.IGNORECASE,
    )
    for m in pattern.finditer(line):
        lat_val = float(m.group(1))
        lat_hem = m.group(2).upper()
        lon_val = float(m.group(3))
        lon_hem = m.group(4).upper()
        lat = -lat_val if lat_hem == "S" else lat_val
        lon = -lon_val if lon_hem == "W" else lon_val
        pairs.append((lat, lon))
    return pairs


def dms_to_decimal(dms_str: str) -> tuple[float, float] | None:
    """Parse DMS or decimal string to (lat, lon) decimal degrees.

    Accepts formats like:
      - 42.085273 S, 63.866958 W (decimal + hemisphere)
      - 42°05'12.3"S 63°52'20.1"W
      - 42 05 12.3 S, 63 52 20.1 W
      - -42.0867, -63.8736 (pass-through)
    """
    s = dms_str.strip()
    # Decimal + hemisphere (PDF style)
    dec_hem = parse_decimal_hemisphere(s)
    if dec_hem is not None:
        return dec_hem
    # Already decimal (signed)
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


def extract_waypoints_from_pdf_text(text: str) -> dict[str, list[tuple[float, float, str, str]]]:
    """Parse PDF-derived text and return waypoints per site.

    Returns dict: site_id -> list of (lat, lon, point_type, description).
    Handles: COORDINATES (box caves — listed under Caves heading in PDF),
    High Density Caves, The Plains, The Road.
    Applies known typo fix: Plains last bottom_edge 63.860152 -> 63.870152.
    """
    result: dict[str, list[tuple[float, float, str, str]]] = {
        "san_lorenzo_box_caves": [],
        "san_lorenzo_caves": [],
        "san_lorenzo_plains": [],
        "san_lorenzo_road": [],
    }
    lines = [ln.strip() for ln in text.splitlines()]
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        # COORDINATES: then 4 lines -> Box Caves corners (PDF p.4, under Caves heading)
        if "COORDINATES:" in line.upper():
            i += 1
            for k in range(4):
                if i + k >= n:
                    break
                pair = parse_decimal_hemisphere(lines[i + k])
                if pair is not None:
                    lat, lon = pair
                    result["san_lorenzo_box_caves"].append(
                        (lat, lon, "point", f"Corner {k + 1}")
                    )
            i += 4
            continue

        # High Density Caves Total Count Area: Start, End, Along Right edge
        if "High Density Caves" in line and "908" in line:
            i += 1
            edge_count = 0
            while i < n and "The Plains" not in lines[i]:
                ln = lines[i]
                if ln.startswith("Start:"):
                    for idx, (lat, lon) in enumerate(parse_coord_pairs(ln), 1):
                        result["san_lorenzo_caves"].append(
                            (lat, lon, "start", f"Start point {idx}")
                        )
                elif ln.startswith("End:"):
                    for idx, (lat, lon) in enumerate(parse_coord_pairs(ln), 1):
                        result["san_lorenzo_caves"].append(
                            (lat, lon, "end", f"End point {idx}")
                        )
                elif "Right edge" in ln or "Along Right" in ln:
                    pass  # next lines are edge coords
                else:
                    pair = parse_decimal_hemisphere(ln)
                    if pair is not None:
                        lat, lon = pair
                        edge_count += 1
                        result["san_lorenzo_caves"].append(
                            (lat, lon, "edge", f"Right edge {edge_count}")
                        )
                i += 1
            continue  # i now at "The Plains" or end

        # The Plains Total Count Area: Start, End, Along Top Edge, Along Bottom Edge
        if "The Plains" in line and "453" in line:
            i += 1
            section = "start"  # start | top_edge | bottom_edge
            top_edge: list[tuple[float, float, str, str]] = []
            bottom_edge: list[tuple[float, float, str, str]] = []
            while i < n and "The Road" not in lines[i]:
                ln = lines[i]
                if ln.startswith("Start:"):
                    for idx, (lat, lon) in enumerate(parse_coord_pairs(ln), 1):
                        result["san_lorenzo_plains"].append(
                            (lat, lon, "start", f"Start point {idx}")
                        )
                elif ln.startswith("End:"):
                    for idx, (lat, lon) in enumerate(parse_coord_pairs(ln), 1):
                        result["san_lorenzo_plains"].append(
                            (lat, lon, "end", f"End point {idx}")
                        )
                elif "Along Top Edge" in ln or "Top Edge" in ln:
                    section = "top_edge"
                elif "Along Bottom Edge" in ln or "Bottom Edge" in ln:
                    section = "bottom_edge"
                else:
                    pair = parse_decimal_hemisphere(ln)
                    if pair is not None:
                        lat, lon = pair
                        if section == "bottom_edge":
                            if abs(lon - (-63.860152)) < 1e-5:
                                lon = -63.870152  # typo fix
                            bottom_edge.append((lat, lon, "bottom_edge", f"Bottom edge {len(bottom_edge) + 1}"))
                        if section == "top_edge":
                            top_edge.append((lat, lon, "top_edge", f"Top edge {len(top_edge) + 1}"))
                i += 1
            result["san_lorenzo_plains"].extend(top_edge)
            result["san_lorenzo_plains"].extend(bottom_edge)
            continue

        # The Road — no coordinates in PDF
        if "The Road" in line and "359" in line:
            i += 1
            continue

        i += 1

    return result


def write_extracted_waypoints(
    extracted: dict[str, list[tuple[float, float, str, str]]],
    out_dir: Path,
) -> None:
    """Write extracted waypoints to per-site CSVs. Overwrites only sites present in extracted."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for site_id, rows in extracted.items():
        if not rows:
            continue
        path = out_dir / f"{site_id}.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            w.writeheader()
            for lat, lon, point_type, description in rows:
                w.writerow({"lat": lat, "lon": lon, "point_type": point_type, "description": description})
        print(f"  {path.name} ({len(rows)} rows)")
    return None


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
    ap.add_argument(
        "--from-pdf-text",
        type=Path,
        metavar="FILE",
        help="Extract waypoints from PDF text file and write per-site CSVs to --out-dir",
    )
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

    if args.from_pdf_text is not None:
        path = Path(args.from_pdf_text)
        if not path.exists():
            print(f"File not found: {path}", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        extracted = extract_waypoints_from_pdf_text(text)
        script_dir = Path(__file__).resolve().parent
        out_dir = (script_dir / args.out_dir).resolve() if not args.out_dir.is_absolute() else args.out_dir.resolve()
        if not out_dir.exists() and not args.out_dir.is_absolute():
            out_dir = (Path.cwd() / args.out_dir).resolve()
        print(f"Writing extracted waypoints to {out_dir}")
        write_extracted_waypoints(extracted, out_dir)
        return 0

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
