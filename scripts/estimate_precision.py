#!/usr/bin/env python3
"""
Estimate detection precision from labeled samples.

Reads completed label CSVs (from export_lidar_label_sample.py), computes
precision = TP / (TP + FP) with Wilson score confidence interval, and
produces adjusted count estimates per site.

Usage:
    python scripts/estimate_precision.py \
        --label-csvs data/interim/lidar_label_samples/bushes_box/label_sample.csv \
                     data/interim/lidar_label_samples/caleta_tiny/label_sample.csv \
        --site-labels "Bushes Box" "Caleta Tiny" \
        --raw-counts 55 321 \
        --candidate-counts 45 315 \
        --out data/processed/precision_estimates.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def wilson_ci(
    n_success: int,
    n_total: int,
    z: float = 1.96,
) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Returns (lower, upper) bounds at the given z-level (default 95%).
    """
    if n_total <= 0:
        return (0.0, 0.0)
    p = n_success / n_total
    denom = 1 + z * z / n_total
    center = (p + z * z / (2 * n_total)) / denom
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n_total)) / n_total) / denom
    return (max(0.0, center - spread), min(1.0, center + spread))


def compute_precision_from_labels(label_csv: Path) -> Dict:
    """Read a label CSV and compute precision statistics."""
    counts = {"TP": 0, "FP_rock": 0, "FP_vegetation": 0, "FP_burrow_empty": 0, "uncertain": 0, "other": 0}
    total_labeled = 0
    unlabeled = 0

    with open(label_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = (row.get("label") or "").strip()
            if not label:
                unlabeled += 1
                continue
            total_labeled += 1
            if label in counts:
                counts[label] += 1
            else:
                counts["other"] += 1

    tp = counts["TP"]
    fp = counts["FP_rock"] + counts["FP_vegetation"] + counts["FP_burrow_empty"] + counts["other"]
    n_classified = tp + fp  # excludes uncertain

    precision = tp / n_classified if n_classified > 0 else None
    ci_lower, ci_upper = wilson_ci(tp, n_classified) if n_classified > 0 else (None, None)

    return {
        "label_csv": str(label_csv),
        "total_rows": total_labeled + unlabeled,
        "total_labeled": total_labeled,
        "unlabeled": unlabeled,
        "counts": counts,
        "n_classified": n_classified,
        "n_tp": tp,
        "n_fp": fp,
        "precision": round(precision, 4) if precision is not None else None,
        "wilson_ci_95": {
            "lower": round(ci_lower, 4) if ci_lower is not None else None,
            "upper": round(ci_upper, 4) if ci_upper is not None else None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate detection precision from labeled samples")
    parser.add_argument("--label-csvs", nargs="+", required=True, help="Labeled sample CSV files")
    parser.add_argument("--site-labels", nargs="+", default=None, help="Site names (same order as CSVs)")
    parser.add_argument("--raw-counts", nargs="+", type=int, default=None, help="Ground truth counts per site")
    parser.add_argument("--candidate-counts", nargs="+", type=int, default=None, help="Pipeline candidate counts per site")
    parser.add_argument("--out", default="data/processed/precision_estimates.json", help="Output JSON path")
    args = parser.parse_args()

    csvs = [Path(p) for p in args.label_csvs]
    labels = args.site_labels or [p.parent.name for p in csvs]
    raw_counts = args.raw_counts or [None] * len(csvs)
    candidate_counts = args.candidate_counts or [None] * len(csvs)

    if len(labels) != len(csvs):
        raise SystemExit("Number of site labels must match number of label CSVs")

    results = []
    print(f"\n{'Site':<25} {'Precision':>10} {'95% CI':>18} {'Adjusted':>12} {'Notes'}")
    print("-" * 80)

    for label_csv, site, raw, candidates in zip(csvs, labels, raw_counts, candidate_counts):
        if not label_csv.exists():
            print(f"{site:<25} {'N/A':>10} {'file not found':>18}")
            results.append({"site": site, "error": f"File not found: {label_csv}"})
            continue

        stats = compute_precision_from_labels(label_csv)
        stats["site"] = site

        prec = stats["precision"]
        ci = stats["wilson_ci_95"]

        # Adjusted count = raw_candidate_count * precision
        adjusted = None
        adjusted_ci = None
        if prec is not None and candidates is not None:
            adjusted = round(candidates * prec)
            adjusted_ci = (
                round(candidates * ci["lower"]) if ci["lower"] is not None else None,
                round(candidates * ci["upper"]) if ci["upper"] is not None else None,
            )
            stats["candidate_count"] = candidates
            stats["adjusted_count"] = adjusted
            stats["adjusted_count_ci"] = {"lower": adjusted_ci[0], "upper": adjusted_ci[1]} if adjusted_ci else None

        if raw is not None:
            stats["ground_truth_count"] = raw

        prec_str = f"{prec:.2%}" if prec is not None else "N/A"
        ci_str = f"[{ci['lower']:.2%}, {ci['upper']:.2%}]" if ci["lower"] is not None else "N/A"
        adj_str = str(adjusted) if adjusted is not None else "N/A"
        notes = f"n={stats['n_classified']}, {stats['counts']['uncertain']} uncertain"

        print(f"{site:<25} {prec_str:>10} {ci_str:>18} {adj_str:>12} {notes}")
        results.append(stats)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"results": results}, indent=2))
    print(f"\nPrecision estimates written to: {out_path}")


if __name__ == "__main__":
    main()
