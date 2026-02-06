#!/usr/bin/env python3
"""Export a ground DEM from a LAS file as a Cloud-Optimized GeoTIFF.

Reuses the streaming ``build_ground_dem()`` from ``run_lidar_hag`` so it
handles arbitrarily large files (tested up to 23 GB).

Example::

    python3 scripts/export_dem.py \
        "data/2025/San Lorenzo Full LiDAR LAS.las" \
        -o data/processed/san_lorenzo_full_dem.tif \
        --cell-res 0.30 --ground-method min --verbose
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Imports from the existing LiDAR pipeline script
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_lidar_hag import build_ground_dem, _autodetect_crs_from_las  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Export ground DEM from LAS → GeoTIFF")
    ap.add_argument("las_file", type=Path, help="Input LAS/LAZ file")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output GeoTIFF path")
    ap.add_argument("--cell-res", type=float, default=0.30, help="Grid cell size in metres (default: 0.30)")
    ap.add_argument("--ground-method", default="min", choices=["min", "p05", "csf"],
                    help="Ground estimation method (default: min)")
    ap.add_argument("--crs-epsg", type=int, default=None, help="Override CRS EPSG code")
    ap.add_argument("--chunk-size", type=int, default=4_000_000, help="Points per streaming chunk")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    if not args.las_file.exists():
        sys.exit(f"ERROR: LAS file not found: {args.las_file}")

    # ------------------------------------------------------------------
    # 1. Build ground DEM (streaming)
    # ------------------------------------------------------------------
    if args.verbose:
        print(f"Building ground DEM from {args.las_file.name} "
              f"(cell_res={args.cell_res}, method={args.ground_method})")
    dem, meta = build_ground_dem(
        args.las_file,
        cell_res=args.cell_res,
        chunk_size=args.chunk_size,
        verbose=args.verbose,
        ground_method=args.ground_method,
    )
    mins = meta["mins"]  # [x_min, y_min, z_min]
    ny, nx = meta["shape"]

    if args.verbose:
        finite = np.isfinite(dem)
        print(f"    DEM range: {dem[finite].min():.2f} – {dem[finite].max():.2f} m"
              if finite.any() else "    DEM: all no-data")

    # ------------------------------------------------------------------
    # 2. Resolve CRS
    # ------------------------------------------------------------------
    crs = None
    if args.crs_epsg is not None:
        import rasterio.crs
        crs = rasterio.crs.CRS.from_epsg(args.crs_epsg)
        if args.verbose:
            print(f"    CRS override: EPSG:{args.crs_epsg}")
    else:
        crs_info = _autodetect_crs_from_las(args.las_file)
        if crs_info is not None:
            import rasterio.crs
            if "epsg" in crs_info:
                crs = rasterio.crs.CRS.from_epsg(crs_info["epsg"])
            elif "wkt" in crs_info:
                crs = rasterio.crs.CRS.from_wkt(crs_info["wkt"])
            if args.verbose:
                print(f"    CRS auto-detected: {crs}")
        else:
            print("WARNING: no CRS detected; output will have no spatial reference",
                  file=sys.stderr)

    # ------------------------------------------------------------------
    # 3. Write Cloud-Optimized GeoTIFF
    # ------------------------------------------------------------------
    import rasterio
    from rasterio.transform import from_origin

    # Grid row 0 = y_min, but GeoTIFF row 0 = y_max → flip vertically
    dem_flipped = np.flipud(dem)

    # Affine: top-left corner is (x_min, y_min + ny * cell_res)
    transform = from_origin(
        west=mins[0],
        north=mins[1] + ny * args.cell_res,
        xsize=args.cell_res,
        ysize=args.cell_res,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)

    profile = {
        "driver": "GTiff",
        "width": nx,
        "height": ny,
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "compress": "DEFLATE",
        "predictor": 3,       # float predictor
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "BIGTIFF": "IF_SAFER",
    }

    with rasterio.open(args.output, "w", **profile) as dst:
        dst.write(dem_flipped, 1)

    size_mb = args.output.stat().st_size / 1_048_576
    print(f"Wrote {args.output}  ({nx}×{ny}, {size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
