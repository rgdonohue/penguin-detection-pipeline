# Argentina Data Integration - Executive Summary

**Date:** 2025-12-01  
**Project Manager Review**  
**Status:** Planning Phase - Ready for Implementation

---

## Situation Overview

The team has returned from Argentina with new field data, including **penguin counts collected by Lydia** for multiple penguin colony sites. This data represents a significant opportunity to improve thermal detection calibration, which is currently in research phase with known calibration issues.

**IMPORTANT CLARIFICATION (2025-12-17):** The ~3,705 figure is total penguin COUNT from field observations. We do NOT have 3,705 GPS-tagged penguin locations. The `san_lorenzo_waypoints.csv` file contains 48 boundary/route waypoints, not individual penguin positions. Georeferencing (GPS→pixel projection) is needed to convert count locations to image coordinates.

---

## Key Findings from Field Data

### Ground Truth Data Available
- **Total Known Counts:** ~3,705 penguins across counted areas (field observations)
- **Site-level counts (NOT individual GPS locations):**
  - Caleta: Tiny Island (321), Small Island (1,557), Box Counts (8, 12)
  - San Lorenzo: Road (359), Plains (453), Caves (908), Box Counts (32, 55)
- **Boundary waypoints:** 48 survey boundary/route points in `san_lorenzo_waypoints.csv`
- **Data Format:** Penguin counts by site; boundary GPS coordinates documented in PDF notes

### Sensor Data Collected
- ✅ **H30T Thermal Imagery** - Multiple missions across all sites
- ✅ **GeoCue TrueView 515 LiDAR** - San Lorenzo sites
- ✅ **DJI L2 LiDAR** - Caleta sites

---

## Current Project Status

### LiDAR Pipeline ✅
- **Status:** Production-ready on tested data
- **Performance:** 802 detections on golden test tile (reproducible)
- **Argentina Readiness:** Will need parameter retuning for TrueView 515

### Thermal Pipeline ⚠️
- **Status:** Research phase (not production-ready)
- **Critical Issues:**
  - ~9°C calibration offset unresolved
  - Ground truth incomplete (previously 60/137 labels = 44%)
  - Detection performance variable (F1: 0.09-0.30)
  - Batch processing not implemented
- **Opportunity:** New GPS ground truth can enable calibration and optimization

---

## Proposed Solution: Georeferencing Ground Truth Points

### Objective
Convert Lydia's GPS waypoints to pixel coordinates in thermal images, creating a comprehensive ground truth dataset for:
1. **Thermal detection parameter optimization**
2. **Calibration validation** (testing the 9°C offset correction)
3. **Detection accuracy assessment** across different sites/conditions

### Approach
1. **Extract GPS waypoints** from PDF → structured format
2. **Match waypoints to thermal images** (spatial/temporal)
3. **Project GPS → pixel coordinates** using camera model and pose data
4. **Validate accuracy** with manual QC
5. **Generate ground truth CSVs** for optimization pipeline

### Technical Implementation
- Leverage existing `pipelines/thermal.py` camera model
- Reverse-engineer orthorectification logic for forward projection
- Use EXIF metadata (GPS, altitude, gimbal angles) from thermal images
- Account for terrain elevation (DSM from LiDAR if available)

---

## Implementation Plan

### Phase 1: Data Extraction (2-4 hours)
- Parse GPS waypoints from PDF
- Inventory thermal imagery with EXIF metadata
- Create waypoint-to-image mapping

### Phase 2: Georeferencing (4-6 hours)
- Implement GPS-to-pixel projection function
- Batch process all waypoints
- Generate pixel coordinate outputs

### Phase 3: Validation (2-3 hours)
- Manual QC on sample points
- Accuracy assessment
- Error correction if needed

### Phase 4: Dataset Creation (1-2 hours)
- Generate ground truth CSVs
- Organize by image and site
- Create summary statistics

**Total Estimated Time:** 9-15 hours

---

## Expected Outcomes

### Immediate Benefits
1. **Comprehensive Ground Truth Dataset**
   - ~3,705 known penguin locations (vs. previous 60)
   - Multiple sites and conditions
   - GPS-accurate positioning

2. **Thermal Detection Optimization**
   - Parameter tuning on real field data
   - Site-specific threshold optimization
   - Performance validation

3. **Calibration Validation**
   - Test 9°C offset correction methods
   - Validate thermal extraction accuracy
   - Identify calibration improvements

### Long-term Benefits
- Foundation for production thermal detection
- Multi-site validation dataset
- Improved detection accuracy
- Better understanding of thermal signal variability

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| GPS accuracy insufficient | Use RTK data if available; validate manually |
| Waypoint-to-image matching fails | Spatial + temporal matching; manual verification |
| Terrain model unavailable | Use flat assumption initially; generate DSM later |
| Projection accuracy poor | Validate on samples; apply corrections |
| H30T camera model differs | Test on known points; adjust FOV if needed |

---

## Critical Questions

1. **GPS System Used:** RTK, standard GPS, or phone GPS?
   - Affects expected accuracy (RTK: <1 pixel; standard: 5-10 pixels)

2. **Terrain Model:** Is DSM available from LiDAR?
   - Needed for accurate projection on non-flat terrain

3. **Boresight Calibration:** Was this performed in field?
   - Needed for accurate camera pointing

4. **Image Coverage:** Do thermal images cover all waypoints?
   - Some waypoints may be outside image footprints

5. **Priority Sites:** Which should we start with?
   - Box counts (smaller) vs. large count areas (more data)

---

## Recommended Next Steps

### Immediate (This Week)
1. ✅ **Review and approve plan** (this document)
2. **Extract GPS waypoints** from PDF → structured format
3. **Inventory thermal imagery** → create image index
4. **Clarify critical questions** → GPS system, terrain model, boresight

### Short-term (Next 1-2 Weeks)
1. **Implement georeferencing script** → GPS-to-pixel projection
2. **Process waypoints** → generate pixel coordinates
3. **Validate accuracy** → manual QC on samples
4. **Create ground truth dataset** → ready for optimization

### Medium-term (Next Month)
1. **Run parameter optimization** → using new ground truth
2. **Validate thermal calibration** → test offset corrections
3. **Assess detection performance** → across sites/conditions
4. **Update thermal pipeline** → with optimized parameters

---

## Success Criteria

✅ GPS waypoints extracted and organized  
✅ Automated GPS-to-pixel projection implemented  
✅ Projection accuracy validated (<5 pixel error for RTK)  
✅ Pixel coordinate ground truth CSVs generated  
✅ Dataset ready for thermal detection optimization  

---

## Related Documents

- **Detailed Plan:** `docs/planning/GROUND_TRUTH_GEOREFERENCING_PLAN.md`
- **Current Status:** `CLIENT_STATUS_REPORT_2025-11-20.md`
- **Field Data Specs:** `docs/FIELD_DATA_SPECIFICATIONS.md`
- **Thermal Pipeline:** `pipelines/thermal.py`

---

## Decision Point

**Ready to proceed with implementation?** This plan provides a clear path to georeferencing the ground truth data and enabling thermal detection optimization. The work is well-scoped (9-15 hours) and leverages existing infrastructure.

**Alternative:** If immediate implementation is not desired, we can start with Phase 1 (data extraction) to better understand the data structure and refine the approach.

---

*Review completed: 2025-12-01*  
*Next update: Post-implementation or upon approval*

