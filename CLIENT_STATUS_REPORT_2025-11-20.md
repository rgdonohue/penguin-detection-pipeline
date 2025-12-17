# Penguin Detection Pipeline v4.0
## Status Report - November 20, 2025

> Update (2025-12-17): The golden AOI baseline was **rebased to 802 detections** after fixing an order-dependent quantile bug in the LiDAR DEM/HAG implementation; `pytest` is now green (tests restricted to `tests/`), and a basic fusion spatial join exists in `pipelines/fusion.py` (requires CRS `x/y` inputs).

### Executive Summary

LiDAR detection is production-ready on our golden test data and has been stable across repeated runs. Your TrueView 515 data is untested and will need a quick parameter check with a sample tile. Thermal remains research-only until calibration, ground truth, and a batch script exist; no delivery date is promised there.

**Bottom Line:** We can run LiDAR now (with a short retune once we see TrueView data). Thermal is not ready for counting; treat it as experimental context only.

---

## Current Capabilities

### 1. LiDAR Detection - **PRODUCTION READY (TESTED DATA)** ✅

**What It Does:**
- Analyzes 3D point cloud data from drone surveys
- Flags penguin-sized objects (20-60cm height above ground)
- Processing speed: ~5 GB/minute on test Mac M-series laptop (4.4 GB tile in 51 seconds; throughput depends on hardware/I/O)

**Performance Metrics:**
- **879 candidate detections** on the golden tile (4.4 GB sample), reproducible across runs with fixed parameters
- **12/12 automated tests passing** (last run: Nov 5, 2025)

**Outputs Provided:**
- Detection counts with GPS coordinates (GeoJSON format)
- Visual QC plots
- Statistical summaries (JSON)
- Provenance tracking for audit trail

**Ready for Argentina?** **YES, with a quick retune once we see a TrueView 515 tile.** One-command run:
```
python scripts/run_lidar_hag.py --data-root <your_lidar_folder> --out results.json
```

---

### 2. Thermal Imaging - **RESEARCH PHASE** ⚠️

**What It Does:**
- Extracts radiometric temperature data from DJI H20T imagery (H30T untested)
- Can show warm spots for manual review; not reliable for automated counts
- Serves as supplementary context to LiDAR detections

**Current Testing:**
- Radiometric extraction validated on H20T frames
- Thermal contrast varies: **0.14°C to 11°C** between penguins and ground
- Best-case detection F1 ≈ 0.30 on high-contrast frames only

**Critical Gaps:**
- **Calibration unsolved:** ~9°C offset, no proven fix yet
- **Ground truth incomplete:** 60/137 labels (44%); blocks parameter tuning
- **No batch script:** Only per-frame tools exist; production pipeline not built
- **Fusion not implemented:** No spatial join code yet

**Ready for Argentina?** **NO** — research-only; timeline to production is unknown

---

### 3. Data Fusion - **NOT IMPLEMENTED** ❌

**What It Would Do:**
- Combine LiDAR and thermal detections
- Classify each detection as:
  - **Both** - Confirmed by both sensors (highest confidence)
  - **LiDAR-Only** - Shape detected, no heat signature
  - **Thermal-Only** - Heat detected, no 3D shape

**Current Status:**
- No spatial join code exists
- No fusion script written
- Timeline uncertain given thermal research status

---

## Test Results Summary

| Component | Test Coverage | Status | Last Validated |
|-----------|--------------|--------|----------------|
| LiDAR Pipeline | 12 tests | ✅ All Passing | Nov 5, 2025 |
| Thermal Extraction | 5 tests | ✅ All Passing | Oct 14, 2025 |
| Data Reproducibility | Golden baseline | ✅ Verified | Nov 5, 2025 |
| Performance | ~5 GB/min on M-series laptop | ✅ Measured | Nov 5, 2025 |

---

## Argentina Deployment Readiness

### What We Can Do Today

✅ **Process LiDAR data now**
- Expected output: Colony-wide candidate count (879 baseline on test tile)
- Processing estimate: ~10–15 minutes for 35 GB on similar hardware; actual time depends on TrueView density/I/O
- Confidence: High on tested data; will verify on your sample tile
- **Note:** TrueView 515 LiDAR untested; parameters may need adjustment

✅ **Generate preliminary thermal maps (research)**
- Show temperature distribution for manual review
- Not suitable for automated counting

✅ **Provide quality control visualizations**
- Detection overlays and summary plots for LiDAR runs

### What We Need From You

1. **Sensor Specifications**
   - LiDAR model and point density (points/m²)
   - Flight altitude and coverage pattern
   - Thermal camera model (H30T confirmed? H20T also used?)

2. **Sample Data**
   - 1-2 representative LiDAR tiles from Argentina
   - 10-20 thermal frames with varied lighting conditions
   - Any available ground truth counts for validation

3. **Deliverable Preferences**
   - Preferred coordinate system (UTM Zone 20S?)
   - Output formats (GeoJSON, Shapefile, KML?)
   - Visualization requirements (resolution, overlays)

---

## Proposed Next Steps

### Immediate Actions (This Week)
1. **Run LiDAR quicklook** on one Argentina tile (≤30 minutes including QC)
2. **Assess thermal contrast** on a handful of Argentina frames (1-2 hours)
3. **Generate sample outputs** for review (1-2 hours)

### Required Development (Timeline Uncertain)
1. Complete remaining ground truth labels (4 frames, 77 penguins)
2. Solve thermal calibration (approach unknown)
3. Build batch processing scripts (not started)
4. Implement fusion pipeline (not started)
5. Validate on full dataset

### Realistic Delivery Timeline
- **48 hours after sample tile:** Initial LiDAR counts and QC on Argentina data
- **0.5–2 days after first tile:** LiDAR parameter tuning for TrueView 515 (depending on data differences)
- **Unknown:** Thermal production readiness (pending calibration, ground truth, batch script)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|---------|------------|
| TrueView 515 LiDAR untested | **High** | Medium | Retune on sample tile (hours) |
| Different point density | **High** | Medium | Current tests at 8,700–9,000 pts/m²; adjust thresholds as needed |
| Poor thermal contrast in field | Medium | Medium | Use LiDAR-only approach |
| Thermal remains research-only | **High** | High | Complete ground truth, solve calibration, build batch script |
| Larger dataset than expected | Low | Low | Process in batches if needed |
| Different penguin species/size | Low | Medium | Adjust height thresholds |

---

## Technical Specifications

**Supported Inputs:**
- LiDAR: LAS/LAZ files (tested at 8,700-9,000 pts/m²; other densities may need tuning)
- Thermal: DJI H20T radiometric imagery (H30T untested)
- Coordinates: Tested with UTM Zone 20S; other projected systems should work if consistent across inputs

**System Requirements:**
- Python 3.11+ (specific version required)
- 16 GB RAM recommended
- 100 GB storage for full dataset
- GDAL/rasterio for thermal processing (complex installation)

**Processing Performance:**
- LiDAR: ~5 GB/minute on test Mac M-series laptop (4.4 GB tile in 51 seconds); varies with hardware/I/O
- Thermal: Research-only (batch script not built)
- Fusion: Not implemented

---

## Project Team Recommendations

1. **Start with LiDAR-only deployment** for immediate results
2. **Collect thermal validation data** during this trip for calibration
3. **Plan a short refinement sprint (up to 2 weeks)** post-field work to fold in LiDAR tuning and any thermal progress
4. **Consider a second validation flight** after parameter tuning

---

## Questions for Discussion

1. What is your target accuracy threshold? (±10%? ±5%?)
2. Do you need individual penguin locations or just total counts?
3. Are there specific areas of interest within the colony?
4. What is your timeline for final results?
5. Would you like real-time field processing capability?

---

## Contact & Support

**Repository:** `/penguins-4.0/`
**Documentation:** See `README.md` for quick start
**Test Data:** H20T thermal in `data/legacy_ro/penguin-thermal-og/`
**LiDAR Test:** `data/legacy_ro/penguin-2.0/data/raw/LiDAR/`

*This pipeline represents 4 iterations of development, incorporating lessons from previous field deployments and validated against 879 candidate detections on the golden test tile.*

---

*Report generated: November 20, 2025*
*Next update: Post-meeting with refined requirements*
