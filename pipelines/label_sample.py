"""
Deterministic label-sample selection for LiDAR candidate detections.

Goal: produce a small, reviewable subset to estimate precision / FP rate without
requiring full ground truth.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np


def select_label_sample(
    detections: Sequence[Mapping[str, Any]],
    *,
    n_total: int,
    seed: str = "0",
    hag_key: str = "hag_max",
    area_key: str = "area_m2",
) -> List[Dict[str, Any]]:
    if n_total <= 0:
        return []

    dets: List[Dict[str, Any]] = []
    for i, d in enumerate(detections):
        if "x" not in d or "y" not in d:
            continue
        det = dict(d)
        det.setdefault("id", str(d.get("id") or f"det:{i:06d}"))
        dets.append(det)

    if not dets:
        return []

    hag = np.asarray([_safe_float(d.get(hag_key)) for d in dets], dtype=np.float64)
    area = np.asarray([_safe_float(d.get(area_key)) for d in dets], dtype=np.float64)

    hag_bin = _quantile_bins(hag, bins=4)
    area_bin = _quantile_bins(area, bins=4)

    strata: Dict[str, List[Dict[str, Any]]] = {}
    stratum_by_id: Dict[str, str] = {}
    for d, hb, ab in zip(dets, hag_bin, area_bin):
        s = f"hag_q{hb}_area_q{ab}"
        d2 = dict(d)
        d2["stratum"] = s
        stratum_by_id[str(d2.get("id", ""))] = s
        strata.setdefault(s, []).append(d2)

    # Deterministic allocation: even split across strata, with any remainder
    # assigned to strata in sorted order.
    keys = sorted(strata.keys())
    base = n_total // len(keys)
    rem = n_total % len(keys)

    chosen: List[Dict[str, Any]] = []
    chosen_ids: set[str] = set()
    for idx, k in enumerate(keys):
        want = base + (1 if idx < rem else 0)
        if want <= 0:
            continue
        group = strata[k]
        # Deterministic random-like order via hash(seed, id)
        group_sorted = sorted(group, key=lambda d: _hash_key(seed, str(d.get("id", ""))))
        picked = group_sorted[: min(want, len(group_sorted))]
        chosen.extend(picked)
        for d in picked:
            chosen_ids.add(str(d.get("id", "")))

    # Backfill: if any strata are sparse, top up from remaining detections across all strata.
    want_total = min(int(n_total), int(len(dets)))
    if len(chosen) < want_total:
        remaining: List[Dict[str, Any]] = []
        for d in dets:
            det_id = str(d.get("id", ""))
            if det_id in chosen_ids:
                continue
            # Keep stratum label if it exists on the per-stratum copy, else compute a minimal one.
            d2 = dict(d)
            d2.setdefault("stratum", stratum_by_id.get(det_id))
            remaining.append(d2)
        remaining_sorted = sorted(remaining, key=lambda d: _hash_key(seed, str(d.get("id", ""))))
        needed = want_total - len(chosen)
        chosen.extend(remaining_sorted[:needed])

    # Final stable ordering for reproducible CSV diffs.
    chosen.sort(key=lambda d: (str(d.get("file", "")), str(d.get("tile", "")), str(d.get("id", ""))))
    return chosen


def _hash_key(seed: str, det_id: str) -> str:
    h = hashlib.sha256(f"{seed}:{det_id}".encode("utf-8")).hexdigest()
    return h


def _safe_float(x: object) -> float:
    try:
        v = float(x)  # type: ignore[arg-type]
        if np.isfinite(v):
            return v
    except Exception:
        pass
    return 0.0


def _quantile_bins(values: np.ndarray, *, bins: int) -> np.ndarray:
    if values.size == 0:
        return np.zeros((0,), dtype=int)
    if bins <= 1:
        return np.zeros_like(values, dtype=int)
    qs = [i / bins for i in range(1, bins)]
    cuts = np.quantile(values, qs).astype(np.float64)
    out = np.zeros((values.shape[0],), dtype=int)
    for i, c in enumerate(cuts, start=0):
        out += (values >= c).astype(int)
    return out


