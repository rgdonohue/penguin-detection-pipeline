# Legacy Project Harvest Notes

Generated: 2025-10-08

## Summary

Found **working LiDAR detection script** in `penguin-2.0` project with proven parameters and test data.

---

## Key Findings

### 1. LiDAR Detection Script ✅

**Location:** `data/legacy_ro/penguin-2.0/scripts/lidar_detect_penguins.py`

**Status:** Working script with all required parameters

**Proven Parameters (from METHODOLOGY.md:330-340):**
```bash
python scripts/lidar_detect_penguins.py \
  --data-root data/raw/LiDAR/ \
  --out results/lidar_detections.json \
  --cell-res 0.25 \
  --hag-min 0.2 \
  --hag-max 0.6 \
  --min-area-cells 2 \
  --max-area-cells 80 \
  --plots \
  --watershed
```

**Available Features:**
- HAG detection with configurable thresholds
- Circularity and solidity filtering (optional)
- Watershed splitting for colony detection
- GeoJSON, CSV, and JSON outputs
- QC plots generation
- Multiple ground/top surface methods

**Confidence:** `field` (documented in METHODOLOGY.md, DEMO_RUNBOOK)

---

### 2. Test Data Available ✅

**Location:** `data/legacy_ro/penguin-2.0/data/raw/LiDAR/`

**Files:**
- cloud0.copc.laz (1.6 GB) - Cloud Optimized format
- cloud0.las (7.1 GB)
- cloud1.las (8.0 GB)
- cloud2.las (8.7 GB)
- cloud3.las (4.4 GB)
- cloud4.las (6.1 GB)
- sample/cloud3.las - Smaller test file

**Recommendation:** Use cloud3.las from sample/ directory for golden AOI testing

---

### 3. Parameter Comparison: Legacy vs PRD

| Parameter | Legacy (Proven) | PRD (Proposed) | Notes |
|-----------|-----------------|----------------|-------|
| cell-res | 0.25 m | 0.5 m | Legacy used finer resolution |
| hag-min | 0.2 m | 0.3 m | Legacy slightly lower |
| hag-max | 0.6 m | 0.7 m | Legacy slightly lower |
| min-area-cells | 2 | 2 | Same |
| max-area-cells | 80 | 30 | Legacy allowed larger regions |

**Recommendation:** Start with legacy parameters (proven to work), then tune if needed

---

### 4. Supporting Library Code

**Location:** `data/legacy_ro/penguin-2.0/src/lidar/`

Contains library-style implementations that `lidar_detect_penguins.py` likely imports.

---

### 5. Other Relevant Scripts Found

From `penguin-2.0/scripts/`:
- `detect_penguins_simple.py` - Simplified detection variant
- `lidar_cluster_colonies.py` - Colony clustering
- `thermal_ortho.py` - Thermal orthorectification
- `fusion_analysis.py` - Multi-source fusion
- `compute_validation_metrics.py` - Validation with labels

---

## Thermal Processing Discovery

**CRITICAL:** Full radiometric data IS encoded in thermal images. Previous assumptions about missing radiometric data were incorrect. Proper thermal processing tools can extract this data.

Source: User confirmation based on later analysis with better tools.

---

## Next Steps

1. Copy `lidar_detect_penguins.py` to `scripts/run_lidar_hag.py` (wrapper)
2. Copy supporting library code from `src/lidar/` to `pipelines/lidar_hag.py`
3. Test on cloud3.las from sample directory
4. Create golden AOI with smallest working dataset
5. Validate outputs match expected format (candidates.gpkg, rollup_counts.json, QC plots)

---

## Decision: Track A Confirmed ✅

We have:
- Working LiDAR detector script with proven parameters
- Test data available
- Documentation of successful runs
- Supporting library code

**Proceed with Track A:** Full pipeline (LiDAR + Thermal + Fusion)
