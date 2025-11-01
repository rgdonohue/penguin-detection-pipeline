#!/usr/bin/env python3
"""
Thermal Orthorectification CLI

Wrapper for thermal orthorectification pipeline. Requires GDAL/rasterio.

INSTALLATION:
    This script requires GDAL which has complex installation requirements.
    See RUNBOOK.md for detailed instructions.

    Quick install (conda recommended):
        conda install -c conda-forge gdal rasterio pyproj

USAGE:
    # Estimate boresight calibration (recommended first step)
    python scripts/run_thermal_ortho.py boresight \\
        --poses data/thermal/poses.csv

    # Single frame orthorectification (8-bit JPEG preview)
    python scripts/run_thermal_ortho.py ortho-one \\
        --image data/thermal/DJI_0001_T.JPG \\
        --poses data/thermal/poses.csv \\
        --dsm data/processed/lidar/dsm.tif \\
        --out data/processed/thermal/ortho_0001.tif \\
        --boresight "-24.18,6.66,0" \\
        --snap-grid

    # Radiometric orthorectification (16-bit thermal data -> float32 Celsius)
    python scripts/run_thermal_ortho.py ortho-one \\
        --image data/thermal/DJI_0001_T.JPG \\
        --poses data/thermal/poses.csv \\
        --dsm data/processed/lidar/dsm.tif \\
        --out data/processed/thermal/ortho_0001_radiometric.tif \\
        --boresight "-24.18,6.66,0" \\
        --snap-grid \\
        --radiometric

    # Verify grid alignment
    python scripts/run_thermal_ortho.py verify-grid \\
        --dsm data/processed/lidar/dsm.tif \\
        --ortho data/processed/thermal/ortho_0001.tif

NOTES:
    - Poses CSV should be exported via exiftool (see RUNBOOK.md)
    - Boresight calibration improves alignment accuracy
    - Use --snap-grid to ensure pixel-perfect DSM alignment
    - CLI exits with error before --help if GDAL unavailable (by design)
"""

import sys
import json
from pathlib import Path
from typing import Optional

# Ensure project root is on PYTHONPATH so we can import pipelines/*
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import click

# Check for GDAL availability before importing pipeline
try:
    from pipelines.thermal import (
        ortho_one,
        verify_grid,
        estimate_boresight,
        check_dependencies,
        GDAL_AVAILABLE,
    )
except ImportError as e:
    print(f"Error importing thermal pipeline: {e}", file=sys.stderr)
    print("\nThis script requires the penguins pipeline to be installed.", file=sys.stderr)
    print("Make sure you're running from the project root directory.", file=sys.stderr)
    sys.exit(1)


def emit_json(d: dict, pretty: bool = True):
    """Print dict as JSON."""
    print(json.dumps(d, indent=2) if pretty else json.dumps(d))


@click.group()
def cli():
    """Thermal orthorectification tools for penguin pipeline."""
    # Check dependencies when CLI is invoked
    try:
        check_dependencies()
    except ImportError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("\nSee RUNBOOK.md for installation instructions.", err=True)
        sys.exit(1)


@cli.command("ortho-one")
@click.option(
    "--image", type=click.Path(exists=True, path_type=Path), required=True,
    help="Thermal image path (single frame)"
)
@click.option(
    "--poses", type=click.Path(exists=True, path_type=Path), required=True,
    help="Poses CSV from exiftool"
)
@click.option(
    "--dsm", type=click.Path(exists=True, path_type=Path), required=True,
    help="LiDAR DSM GeoTIFF"
)
@click.option(
    "--out", type=click.Path(path_type=Path), required=True,
    help="Output ortho GeoTIFF path"
)
@click.option(
    "--boresight", type=str, default="0,0,0",
    help="Δyaw,Δpitch,Δroll degrees (comma-separated). Example: '-24.18,6.66,0'"
)
@click.option(
    "--dfov", type=float, default=40.6,
    help="Diagonal FOV in degrees (H20T thermal ≈ 40.6)"
)
@click.option(
    "--pixel-size", type=float, default=None,
    help="Output pixel size (meters). Default=DSM pixel size"
)
@click.option(
    "--margin", type=float, default=1.25,
    help="AOI expansion factor (>1.0)"
)
@click.option(
    "--z-offset", type=float, default=0.0,
    help="Altitude bias to add to AbsoluteAltitude (meters)"
)
@click.option(
    "--mono/--color", default=True,
    help="Convert to grayscale (mono) or keep color"
)
@click.option(
    "--pre-blur", type=float, default=0.0,
    help="Gaussian blur radius before resampling"
)
@click.option(
    "--strict-bounds/--no-strict-bounds", default=True,
    help="Treat out-of-image samples as nodata"
)
@click.option(
    "--snap-grid/--no-snap-grid", "snap_to_dsm_grid", default=False,
    help="Align output ortho grid to DSM grid for pixel-perfect alignment"
)
@click.option(
    "--radiometric/--no-radiometric", default=False,
    help="Extract 16-bit radiometric thermal data (DJI H20T). If enabled, "
         "extracts ThermalData blob and outputs float32 GeoTIFF in Celsius. "
         "Requires exiftool. Default: use 8-bit JPEG preview."
)
def cmd_ortho_one(
    image: Path,
    poses: Path,
    dsm: Path,
    out: Path,
    boresight: str,
    dfov: float,
    pixel_size: Optional[float],
    margin: float,
    z_offset: float,
    mono: bool,
    pre_blur: float,
    strict_bounds: bool,
    snap_to_dsm_grid: bool,
    radiometric: bool,
):
    """Orthorectify a single thermal image via DSM back-projection."""
    try:
        by, bp, br = [float(x) for x in boresight.split(",")]
    except ValueError:
        click.echo(f"Error: Invalid boresight format: {boresight}", err=True)
        click.echo("Expected format: 'yaw,pitch,roll' (e.g., '-24.18,6.66,0')", err=True)
        sys.exit(1)

    try:
        info = ortho_one(
            image_path=image,
            poses_csv=poses,
            dsm_path=dsm,
            out_path=out,
            boresight=(by, bp, br),
            dfov_deg=dfov,
            pixel_size=pixel_size,
            margin=margin,
            z_offset=z_offset,
            mono=mono,
            pre_blur=pre_blur,
            strict_bounds=strict_bounds,
            tight_crop=True,
            snap_to_dsm_grid=snap_to_dsm_grid,
            radiometric=radiometric,
        )
        emit_json(info, pretty=True)

        if radiometric:
            click.echo(f"\n✅ Radiometric orthorectification complete: {out}", err=True)
            click.echo(f"   Output: float32 temperature data (Celsius)", err=True)
        else:
            click.echo(f"\n✅ Orthorectification complete: {out}", err=True)

    except Exception as e:
        click.echo(f"Error during orthorectification: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command("verify-grid")
@click.option(
    "--dsm", type=str, required=True,
    help="DSM GeoTIFF path"
)
@click.option(
    "--ortho", type=str, required=True,
    help="Ortho GeoTIFF path to verify"
)
def cmd_verify_grid(dsm: str, ortho: str):
    """Verify ortho aligns to DSM grid (integer nesting + zero remainders)."""
    try:
        info = verify_grid(dsm, ortho)
        emit_json(info, pretty=True)

        if info["ok"]:
            click.echo("\n✅ Grid alignment verified", err=True)
            sys.exit(0)
        else:
            click.echo("\n❌ Grid alignment failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error during verification: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command("boresight")
@click.option(
    "--poses", type=click.Path(exists=True, path_type=Path), required=True,
    help="Poses CSV from exiftool (must include LRF target data)"
)
def cmd_boresight(poses: Path):
    """
    Estimate boresight calibration from LRF (laser rangefinder) measurements.

    Computes systematic offset between reported camera pointing and actual
    pointing direction using LRF target positions. Outputs median Δyaw and
    Δpitch to use with --boresight parameter in ortho-one command.

    Example:
        python scripts/run_thermal_ortho.py boresight --poses data/thermal/poses.csv

    Output format includes suggested boresight values in [yaw, pitch, roll] format.
    """
    try:
        result = estimate_boresight(poses)
        emit_json(result, pretty=True)

        # Print suggested usage
        suggested = result["suggest_boresight_deg"]
        click.echo(
            f"\n💡 Suggested boresight: --boresight \"{suggested[0]:.2f},{suggested[1]:.2f},{suggested[2]:.2f}\"",
            err=True
        )
        click.echo(
            f"   Based on {result['yaw_bias_deg']['n']} LRF measurements",
            err=True
        )

    except Exception as e:
        click.echo(f"Error estimating boresight: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
