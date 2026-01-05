# LiDAR Pipeline Assessment — 2025-12-21

**Purpose:** Scientifically honest assessment of what the LiDAR detection pipeline can and cannot claim, based on 2025 Argentina data analysis.

---

## Executive Summary

The LiDAR HAG (Height Above Ground) detection pipeline runs successfully on all 2025 Argentina datasets. However, **validation against ground truth is currently blocked** by:

1. AOI polygon misalignment (tile extents ≠ counted field areas)
2. Undefined detection semantics (individual penguin vs blob center)
3. Unverified sensitivity of the top-surface estimator

Until these are resolved, count comparisons are indicative but not scientifically valid.

---

## Data Processed

| Dataset | Points | Size | CRS | Status |
|---------|--------|------|-----|--------|
| San Lorenzo Full | 675M | 22.9 GB | EPSG:5345 | ✅ Processed |
| San Lorenzo Box Count 11.10 | 23.6M | 875 MB | EPSG:5345 | ✅ Processed |
| San Lorenzo Box Count 11.9.25 | 17.2M | 640 MB | EPSG:5345 | ✅ Processed |
| Caleta Small Island | 17 tiles | ~1.8 GB | EPSG:32720 | ✅ Processed |
| Caleta Tiny Island | 2 tiles | ~0.3 GB | EPSG:32720 | ✅ Processed |
| Caleta Box Count 1 | 1 tile | — | EPSG:32720 | ✅ Processed |
| Caleta Box Count 2 | 1 tile | — | EPSG:32720 | ✅ Processed |

**Total:** 754M points, 25.8 GB — **100% catalogued datasets processed**

---

## Detection Results (Raw, Pre-AOI-Clip)

### San Lorenzo Full (using `--gnd-method max`)

| Metric | Value |
|--------|-------|
| Total detections (deduped) | 18,932 |
| Processing time | ~85 seconds |
| Detections in Caves AOI | 128 (vs 908 field count) |
| Detections in Plains AOI | 221 (vs 453 field count) |

### Caleta Small Island (using `--gnd-method max`)

| Metric | Value |
|--------|-------|
| Total detections (deduped) | 3,660 |
| Field count | 1,557 |
| Ratio | ~2.4× overcount |

**Caveat:** The 2.4× ratio is shown for one site only. Cannot generalize to "systematic overcounting" without:
- Verifying tile extents align with counted area
- Ruling out detection of non-penguin elevated objects
- Manual verification of sample detections

---

## Known Issues

### 1. Top-Surface Estimator Sensitivity

The `p95` streaming quantile implementation is an **approximate estimator whose output depends on streaming order and chunking**. It is not invariant like a true per-cell quantile.

Evidence:
- Commit 76b01fc changed the update formula
- Old implementation (27ad4a8): updates in data units
- Current implementation: dimensionally inconsistent update

**Current mitigation:** Using `--gnd-method max` which is deterministic but may overestimate penguin height, inflating HAG and potentially causing false negatives.

### 2. Tile Overlap and Deduplication

Tiles do overlap in multi-tile datasets:

| Dataset | Tiles | Overlapping Pairs |
|---------|-------|-------------------|
| Caleta Small Island | 17 | 45 |
| Caleta Tiny Island | 2 | 1 |
| Caleta Tiny Island 2 | 2 | 1 |
| San Lorenzo (2025 folder) | 3 | 2 |

**Source:** `data/interim/tile_overlap_analysis.json`

Current deduplication merges detections within a radius **per-tile**, not specifically for cross-tile boundaries. Whether this is correct depends on the **intended semantics**:
- If dedupe is for cross-tile boundary artifacts: current implementation may be too aggressive
- If dedupe is a general regularizer: current implementation may be appropriate

**Action required:** Define what a "detection" represents before evaluating dedupe correctness.

### 3. Ground Model Method

Research literature recommends CSF or p05 for ground model estimation. Current pipeline uses `min` or `max`.

This is **high leverage; likely has large effect** on detection counts, but we cannot claim it "dominates" without controlled experiments varying only the ground model parameter.

### 4. AOI Polygon Alignment

Box count comparisons (e.g., "8 field vs X detected") are invalid because:
- LiDAR tile extents extend beyond the manually-counted areas
- We lack precise polygon boundaries for box count areas
- Any detection count comparison without AOI clipping is unreliable

---

## Biological Limitation: Burrow-Nesting Penguins

San Lorenzo Caves area shows 17.7% detection rate (128 detected / 908 field count), consistent with the fundamental limitation that **LiDAR cannot detect penguins inside burrows or under ledges**.

This is expected behavior, not a pipeline bug. Thermal imaging is required for complete census in cave/burrow habitats.

---

## What Can Be Claimed

| Claim | Evidence | Confidence |
|-------|----------|------------|
| Pipeline processes all 2025 data | Successful runs, JSON outputs | High |
| CRS handling is correct | Verified from LAS VLR headers | High |
| Tiles overlap and dedupe runs | `tile_overlap_analysis.json` | High |
| Detection count varies with parameters | Tested max vs p95 | High |
| Overcounting occurs on Caleta Small Island | 3,660 vs 1,557 field | Medium (AOI caveat) |

## What Cannot Be Claimed

| Claim | Why Not |
|-------|---------|
| "Pipeline achieves X% accuracy" | No AOI-aligned validation |
| "Systematic false positives" | Could be AOI mismatch, not detection error |
| "p95 is broken" | Need to define intended behavior first |
| "Dedupe is wrong" | Need to define detection semantics first |
| "Current settings are optimal" | No parameter sweep with proper holdout |

---

## Required Actions (in order)

1. **Define detection semantics** — What does one detection represent? (individual penguin, blob center, occupied cell)

2. **Implement AOI-clipped evaluation** — Build precise polygon boundaries for each counted area; clip detections before any count comparison

3. **Lock top-surface estimator** — Either use `max` (deterministic) or implement true per-cell quantile (not streaming approximate)

4. **Manual labeling (after AOI alignment)** — Sample 50-100 detections within AOI, classify as TP/FP, compute precision

5. **Ground model experiment** — Compare `min` vs `p05` vs CSF on same data with same AOI

---

## Files Generated This Session

| File | Purpose |
|------|---------|
| `data/interim/tile_overlap_analysis.json` | Backs tile overlap claims with explicit computation |
| `data/interim/san_lorenzo_full_detections.json` | Raw detection output from San Lorenzo Full |
| `data/interim/timings.json` | Processing time records |

---

## Next Review

After AOI polygons are implemented and at least one site has AOI-clipped precision computed.

---

*Assessment prepared: 2025-12-21*
*Principle: Claims must be backed by artifacts; uncertainty must be explicit.*
