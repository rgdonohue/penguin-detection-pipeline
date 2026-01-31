#!/usr/bin/env python3
"""
Analyze LiDAR return intensity features across detections.

Loads detection JSONs (with intensity features from --extract-intensity),
produces distribution plots and statistical summaries to evaluate whether
905nm NIR intensity discriminates penguins from rock/vegetation/guano.

Usage:
    python scripts/analyze_lidar_intensity.py \
        --inputs data/interim/caleta_tiny_island.json data/interim/caleta_small_island.json \
        --labels "Caleta Tiny" "Caleta Small" \
        --out-dir qc/panels/intensity_analysis
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False


def load_detections_with_intensity(json_path: Path) -> List[Dict]:
    """Load detections from a LiDAR summary JSON, keeping only those with intensity."""
    obj = json.loads(json_path.read_text())
    dets = []
    for fi in obj.get("files", []):
        for d in fi.get("detections", []) or []:
            if "intensity_mean" in d:
                dets.append(d)
    # Also support flat format
    if not dets and isinstance(obj.get("detections"), list):
        for d in obj["detections"]:
            if "intensity_mean" in d:
                dets.append(d)
    return dets


def plot_intensity_distributions(
    site_data: Dict[str, List[Dict]],
    out_dir: Path,
) -> None:
    """Plot intensity histograms per site."""
    if not MATPLOTLIB_AVAILABLE:
        print("WARNING: matplotlib not available, skipping plots")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    # Histogram of intensity_mean per site
    fig, ax = plt.subplots(figsize=(10, 6))
    for label, dets in site_data.items():
        vals = [d["intensity_mean"] for d in dets if "intensity_mean" in d]
        if vals:
            ax.hist(vals, bins=50, alpha=0.6, label=f"{label} (n={len(vals)})")
    ax.set_xlabel("Mean Intensity (905nm NIR)")
    ax.set_ylabel("Count")
    ax.set_title("LiDAR Return Intensity Distribution by Site")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "intensity_histogram.png", dpi=150)
    plt.close(fig)

    # 2D scatter: HAG_mean vs intensity_mean
    fig, ax = plt.subplots(figsize=(10, 7))
    for label, dets in site_data.items():
        hag = [d.get("hag_mean", 0) for d in dets if "intensity_mean" in d]
        inten = [d["intensity_mean"] for d in dets if "intensity_mean" in d]
        if hag and inten:
            ax.scatter(hag, inten, alpha=0.4, s=15, label=f"{label} (n={len(hag)})")
    ax.set_xlabel("HAG Mean (m)")
    ax.set_ylabel("Mean Intensity")
    ax.set_title("HAG vs Intensity per Detection")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "hag_vs_intensity.png", dpi=150)
    plt.close(fig)

    # Box plot: intensity by site
    fig, ax = plt.subplots(figsize=(8, 6))
    box_data = []
    box_labels = []
    for label, dets in site_data.items():
        vals = [d["intensity_mean"] for d in dets if "intensity_mean" in d]
        if vals:
            box_data.append(vals)
            box_labels.append(label)
    if box_data:
        ax.boxplot(box_data, labels=box_labels)
        ax.set_ylabel("Mean Intensity")
        ax.set_title("Intensity by Site")
    fig.tight_layout()
    fig.savefig(out_dir / "intensity_boxplot.png", dpi=150)
    plt.close(fig)

    print(f"Plots saved to {out_dir}")


def print_summary_table(site_data: Dict[str, List[Dict]]) -> None:
    """Print a statistical summary table."""
    print(f"\n{'Site':<25} {'N':>6} {'Int Mean':>10} {'Int Std':>10} {'Int Min':>10} {'Int Max':>10}")
    print("-" * 75)
    for label, dets in site_data.items():
        vals = np.array([d["intensity_mean"] for d in dets if "intensity_mean" in d])
        if vals.size == 0:
            print(f"{label:<25} {'0':>6} {'N/A':>10} {'N/A':>10} {'N/A':>10} {'N/A':>10}")
            continue
        print(f"{label:<25} {vals.size:>6} {np.mean(vals):>10.1f} {np.std(vals):>10.1f} "
              f"{np.min(vals):>10.1f} {np.max(vals):>10.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze LiDAR intensity features across sites")
    parser.add_argument("--inputs", nargs="+", required=True, help="LiDAR summary JSON files with intensity features")
    parser.add_argument("--labels", nargs="+", default=None, help="Labels for each input (same order)")
    parser.add_argument("--out-dir", default="qc/panels/intensity_analysis", help="Output directory for plots")
    parser.add_argument("--json-out", default=None, help="Optional JSON summary output")
    args = parser.parse_args()

    inputs = [Path(p) for p in args.inputs]
    labels = args.labels or [p.stem for p in inputs]
    if len(labels) != len(inputs):
        raise SystemExit(f"Number of labels ({len(labels)}) must match inputs ({len(inputs)})")

    site_data: Dict[str, List[Dict]] = {}
    for path, label in zip(inputs, labels):
        if not path.exists():
            print(f"WARNING: {path} not found, skipping")
            continue
        dets = load_detections_with_intensity(path)
        site_data[label] = dets
        print(f"Loaded {len(dets)} detections with intensity from {path.name}")

    if not any(site_data.values()):
        print("No detections with intensity features found. Run pipeline with --extract-intensity first.")
        return

    print_summary_table(site_data)
    plot_intensity_distributions(site_data, Path(args.out_dir))

    if args.json_out:
        summary = {}
        for label, dets in site_data.items():
            vals = [d["intensity_mean"] for d in dets if "intensity_mean" in d]
            summary[label] = {
                "n": len(vals),
                "mean": float(np.mean(vals)) if vals else None,
                "std": float(np.std(vals)) if vals else None,
                "min": float(np.min(vals)) if vals else None,
                "max": float(np.max(vals)) if vals else None,
            }
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
