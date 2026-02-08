#!/usr/bin/env python3
"""Export a ground DTM (bare earth) from a LAS file as a Cloud-Optimized GeoTIFF.

Optionally also exports a DSM (top surface, max Z per cell) in the same
streaming pass with ``--also-dsm``.

Reuses the streaming ``build_ground_dem()`` from ``run_lidar_hag`` so it
handles arbitrarily large files (tested up to 23 GB).

Example::

    python3 scripts/export_dtm.py \
        "data/2025/San Lorenzo Full LiDAR LAS.las" \
        -o data/processed/san_lorenzo_full_dtm.tif \
        --cell-res 0.30 --ground-method min --verbose

    # DTM + DSM in one pass:
    python3 scripts/export_dtm.py \
        "data/2025/San Lorenzo Full LiDAR LAS.las" \
        -o data/processed/san_lorenzo_full_dtm.tif \
        --also-dsm --cell-res 0.30 --verbose
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


def _resolve_crs(las_file: Path, crs_epsg: int | None, verbose: bool):
    """Return a rasterio CRS object (or None) from CLI override or LAS header."""
    crs = None
    if crs_epsg is not None:
        import rasterio.crs
        crs = rasterio.crs.CRS.from_epsg(crs_epsg)
        if verbose:
            print(f"    CRS override: EPSG:{crs_epsg}")
    else:
        crs_info = _autodetect_crs_from_las(las_file)
        if crs_info is not None:
            import rasterio.crs
            if "epsg" in crs_info:
                crs = rasterio.crs.CRS.from_epsg(crs_info["epsg"])
            elif "wkt" in crs_info:
                crs = rasterio.crs.CRS.from_wkt(crs_info["wkt"])
            if verbose:
                print(f"    CRS auto-detected: {crs}")
        else:
            print("WARNING: no CRS detected; output will have no spatial reference",
                  file=sys.stderr)
    return crs


def _write_cog(raster: np.ndarray, out_path: Path, nx: int, ny: int,
               cell_res: float, mins: list, crs) -> None:
    """Write a single-band float32 Cloud-Optimized GeoTIFF."""
    import rasterio
    from rasterio.transform import from_origin

    raster_flipped = np.flipud(raster)
    transform = from_origin(
        west=mins[0],
        north=mins[1] + ny * cell_res,
        xsize=cell_res,
        ysize=cell_res,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    profile = {
        "driver": "GTiff",
        "width": nx,
        "height": ny,
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "compress": "DEFLATE",
        "predictor": 3,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "BIGTIFF": "IF_SAFER",
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(raster_flipped, 1)

    size_mb = out_path.stat().st_size / 1_048_576
    print(f"Wrote {out_path}  ({nx}x{ny}, {size_mb:.1f} MB)")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Export ground DTM (bare earth) from LAS -> GeoTIFF")
    ap.add_argument("las_file", type=Path, help="Input LAS/LAZ file")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output GeoTIFF path (DTM)")
    ap.add_argument("--also-dsm", action="store_true",
                    help="Also export a DSM (max Z per cell) alongside the DTM")
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
    # 1. Build ground DTM (+ optional DSM) in a single streaming pass
    # ------------------------------------------------------------------
    if args.verbose:
        surfaces = "DTM + DSM" if args.also_dsm else "DTM"
        print(f"Building {surfaces} from {args.las_file.name} "
              f"(cell_res={args.cell_res}, method={args.ground_method})")
    dem, meta = build_ground_dem(
        args.las_file,
        cell_res=args.cell_res,
        chunk_size=args.chunk_size,
        verbose=args.verbose,
        ground_method=args.ground_method,
        include_dsm=args.also_dsm,
    )
    mins = meta["mins"]
    ny, nx = meta["shape"]

    if args.verbose:
        finite = np.isfinite(dem)
        print(f"    DTM range: {dem[finite].min():.2f} – {dem[finite].max():.2f} m"
              if finite.any() else "    DTM: all no-data")
        if args.also_dsm and "dsm" in meta:
            dsm = meta["dsm"]
            finite_dsm = np.isfinite(dsm)
            print(f"    DSM range: {dsm[finite_dsm].min():.2f} – {dsm[finite_dsm].max():.2f} m"
                  if finite_dsm.any() else "    DSM: all no-data")

    # ------------------------------------------------------------------
    # 2. Resolve CRS
    # ------------------------------------------------------------------
    crs = _resolve_crs(args.las_file, args.crs_epsg, args.verbose)

    # ------------------------------------------------------------------
    # 3. Write Cloud-Optimized GeoTIFF(s)
    # ------------------------------------------------------------------
    _write_cog(dem, args.output, nx, ny, args.cell_res, mins, crs)

    if args.also_dsm and "dsm" in meta:
        dsm_path = args.output.with_name(
            args.output.stem.replace("_dtm", "_dsm") + args.output.suffix
        )
        # If the DTM filename didn't contain "_dtm", append "_dsm" suffix
        if dsm_path == args.output:
            dsm_path = args.output.with_stem(args.output.stem + "_dsm")
        _write_cog(meta["dsm"], dsm_path, nx, ny, args.cell_res, mins, crs)


if __name__ == "__main__":
    main()
