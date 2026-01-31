#!/usr/bin/env python3
"""
Audit CRS (Coordinate Reference System) metadata across all LAS files.

Iterates all LAS/LAZ files under a root directory, reads embedded CRS info
from each file header, and reports findings. Uses laspy's parse_crs() for
header extraction and optionally pyproj for EPSG resolution.

Usage:
    python scripts/audit_crs.py --data-root data/2025/
    python scripts/audit_crs.py --data-root data/2025/ --json-out data/processed/crs_audit.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import laspy
    LASPY_AVAILABLE = True
except ImportError:
    LASPY_AVAILABLE = False

try:
    import pyproj
    PYPROJ_AVAILABLE = True
except ImportError:
    PYPROJ_AVAILABLE = False


def find_lidar_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for dp, _dns, fns in os.walk(root):
        for fn in fns:
            if Path(fn).suffix.lower() in {".las", ".laz"}:
                files.append(Path(dp) / fn)
    return sorted(files, key=str)


def audit_crs_one(las_path: Path) -> Dict[str, Any]:
    """Read CRS info from a single LAS file."""
    result: Dict[str, Any] = {
        "file": str(las_path),
        "name": las_path.name,
        "crs_raw": None,
        "epsg": None,
        "crs_name": None,
        "error": None,
    }
    try:
        with laspy.open(str(las_path)) as fh:
            h = fh.header
            result["point_count"] = int(getattr(h, "point_count", 0))
            result["point_format_id"] = int(getattr(h.point_format, "id", -1))

            if not hasattr(h, "parse_crs"):
                result["error"] = "laspy header has no parse_crs() method"
                return result

            crs_obj = h.parse_crs()
            if crs_obj is None:
                result["crs_raw"] = None
                return result

            crs_str = str(crs_obj).strip()
            result["crs_raw"] = crs_str if len(crs_str) < 500 else crs_str[:500] + "..."

            if PYPROJ_AVAILABLE and crs_str:
                try:
                    if "GEOGCS" in crs_str or "PROJCS" in crs_str or "COMPD_CS" in crs_str:
                        crs_parsed = pyproj.CRS.from_wkt(crs_str)
                    else:
                        crs_parsed = pyproj.CRS.from_user_input(crs_str)
                    epsg = crs_parsed.to_epsg()
                    result["epsg"] = int(epsg) if epsg is not None else None
                    result["crs_name"] = crs_parsed.name
                except Exception as e:
                    result["error"] = f"pyproj parse failed: {e}"
    except Exception as e:
        result["error"] = str(e)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit CRS metadata across LAS files")
    parser.add_argument("--data-root", required=True, help="Root directory containing LAS/LAZ files")
    parser.add_argument("--json-out", default=None, help="Optional JSON output path for audit results")
    args = parser.parse_args()

    if not LASPY_AVAILABLE:
        raise SystemExit("laspy not available; install with `pip install laspy`")

    data_root = Path(args.data_root).resolve()
    files = find_lidar_files(data_root)
    if not files:
        raise SystemExit(f"No LAS/LAZ files found under {data_root}")

    print(f"Auditing CRS for {len(files)} LAS/LAZ files under {data_root}")
    print("=" * 80)

    results: List[Dict[str, Any]] = []
    epsg_summary: Dict[str, int] = {}

    for f in files:
        info = audit_crs_one(f)
        results.append(info)

        epsg = info.get("epsg")
        crs_name = info.get("crs_name", "")
        error = info.get("error", "")

        rel_path = str(f.relative_to(data_root)) if str(f).startswith(str(data_root)) else str(f)

        if epsg is not None:
            key = f"EPSG:{epsg}"
            epsg_summary[key] = epsg_summary.get(key, 0) + 1
            print(f"  {rel_path}: EPSG:{epsg} ({crs_name})")
        elif info.get("crs_raw"):
            key = "WKT (no EPSG)"
            epsg_summary[key] = epsg_summary.get(key, 0) + 1
            print(f"  {rel_path}: WKT present, no EPSG resolved")
        else:
            key = "No CRS"
            epsg_summary[key] = epsg_summary.get(key, 0) + 1
            print(f"  {rel_path}: No CRS embedded" + (f" ({error})" if error else ""))

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for key, count in sorted(epsg_summary.items()):
        print(f"  {key}: {count} files")

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        audit = {
            "data_root": str(data_root),
            "file_count": len(results),
            "epsg_summary": epsg_summary,
            "files": results,
        }
        out_path.write_text(json.dumps(audit, indent=2))
        print(f"\nAudit JSON written to: {out_path}")


if __name__ == "__main__":
    main()
