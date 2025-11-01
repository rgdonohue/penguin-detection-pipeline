#!/usr/bin/env python3
"""
Thermal smoke test for DJI H30T sample frames.

Iterates over staged intake frames (default: data/intake/h30t/*) and
summarises raw DN statistics, derived Celsius ranges, and any scaling
heuristics triggered by ``pipelines.thermal.extract_thermal_frame``.

Outputs a JSON report to data/interim/thermal_smoketest.json and prints
an ASCII summary so operators can quickly spot calibration issues.

Example:
    python scripts/run_thermal_smoketest.py --input-dir data/intake/h30t
"""

from __future__ import annotations

import json
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List

import click

# Ensure project root is on PYTHONPATH so we can import pipelines/*
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from pipelines.thermal import extract_thermal_frame, ThermalFrame  # noqa: E402


@dataclass
class FrameSummary:
    """Serializable summary for a processed thermal frame."""

    path: str
    raw_shape: tuple[int, int]
    scale: float
    mode: str
    raw_min: float
    raw_max: float
    raw_mean: float
    celsius_min: float
    celsius_max: float
    celsius_mean: float
    warnings: List[str]

    @classmethod
    def from_frame(cls, frame: ThermalFrame, warnings_: Iterable[warnings.WarningMessage]) -> "FrameSummary":
        temp = frame.celsius
        warn_msgs = [str(w.message) for w in warnings_]
        return cls(
            path=str(frame.source),
            raw_shape=frame.raw_shape,
            scale=float(frame.scale),
            mode=frame.mode,
            raw_min=frame.raw_stats["min"],
            raw_max=frame.raw_stats["max"],
            raw_mean=frame.raw_stats["mean"],
            celsius_min=float(temp.min()),
            celsius_max=float(temp.max()),
            celsius_mean=float(temp.mean()),
            warnings=warn_msgs,
        )


def discover_frames(input_dir: Path, pattern: str, mode: str, limit: int) -> List[Path]:
    """Collect frame paths according to selection mode."""
    frames: List[Path] = []
    if mode == "per-dir":
        for subdir in sorted(p for p in input_dir.iterdir() if p.is_dir()):
            matches = sorted(subdir.glob(pattern))
            if matches:
                frames.append(matches[0])
    else:
        frames = sorted(input_dir.rglob(pattern))

    if limit > 0:
        frames = frames[:limit]

    return frames


@click.command()
@click.option(
    "--input-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("data/intake/h30t"),
    help="Directory containing symlinked H30T frames (default: data/intake/h30t).",
)
@click.option(
    "--pattern",
    default="*_T.JPG",
    help="Glob pattern for thermal frames (default: '*_T.JPG').",
)
@click.option(
    "--selection-mode",
    type=click.Choice(["per-dir", "all"], case_sensitive=False),
    default="per-dir",
    help="Select first frame per directory or every match (default: per-dir).",
)
@click.option(
    "--limit",
    type=int,
    default=0,
    help="Maximum number of frames to process (0 = no limit).",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=Path("data/interim/thermal_smoketest.json"),
    help="Path to JSON summary output (default: data/interim/thermal_smoketest.json).",
)
def main(
    input_dir: Path,
    pattern: str,
    selection_mode: str,
    limit: int,
    output: Path,
) -> None:
    """Run thermal smoke test and emit summary statistics."""
    frames = discover_frames(input_dir, pattern, selection_mode.lower(), limit)
    if not frames:
        click.echo(f"No frames found under {input_dir} matching pattern '{pattern}'.", err=True)
        raise SystemExit(1)

    summaries: List[FrameSummary] = []
    click.echo(f"Processing {len(frames)} frame(s) from {input_dir}...")

    for frame_path in frames:
        click.echo(f"  • {frame_path}")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", RuntimeWarning)
            thermal_frame = extract_thermal_frame(frame_path)
        summaries.append(FrameSummary.from_frame(thermal_frame, caught))
        if caught:
            for w in caught:
                click.echo(f"      warning: {w.message}", err=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(summary) for summary in summaries]
    output.write_text(json.dumps(data, indent=2))

    click.echo("")
    click.echo(f"Summary written to {output}")
    for summary in summaries:
        click.echo(
            f"- {Path(summary.path).name}: {summary.mode} scale={summary.scale:.2f} "
            f"raw[{summary.raw_min:.0f},{summary.raw_max:.0f}] "
            f"temp[{summary.celsius_min:.2f},{summary.celsius_max:.2f}] "
            f"mean={summary.celsius_mean:.2f}°C"
        )


if __name__ == "__main__":
    main()
