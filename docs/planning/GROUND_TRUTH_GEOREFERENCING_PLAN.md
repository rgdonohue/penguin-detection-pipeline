# Ground Truth Georeferencing Plan
## Argentina Field Data Integration

**Date:** 2025-12-01  
**Status:** Planning Phase  
**Objective:** Georeference Lydia's GPS ground truth points to thermal imagery for thermal detection calibration

---

## Executive Summary

The team has returned from Argentina with new field data including GPS waypoints for ground truth penguin locations collected by Lydia. These GPS coordinates need to be georeferenced to thermal imagery to create pixel-level ground truth annotations, which will enable calibration and optimization of the thermal detection pipeline.

**Key Deliverable:** Georeferenced ground truth dataset linking GPS coordinates to thermal image pixel coordinates for parameter optimization.

---

## Current Project Status

### LiDAR Pipeline
- ✅ **Status:** Production-ready on tested data
- ✅ **Performance:** 802 detections on golden test tile (reproducible)
- ⚠️ **Argentina Data:** TrueView 515 untested; will need parameter retuning

### Thermal Pipeline
- ⚠️ **Status:** Research phase
- ⚠️ **Calibration:** ~9°C offset issue unresolved
- ⚠️ **Ground Truth:** Previously 60/137 labels (44%) from legacy data
- ⚠️ **Detection Performance:** F1 ≈ 0.30 on best frames, 0.09 on worst
- ⚠️ **Batch Processing:** Not yet implemented

### New Argentina Data Available
- ✅ **GPS Ground Truth:** Waypoints collected by Lydia at multiple sites
- ✅ **Thermal Imagery:** H30T data from multiple missions
- ✅ **LiDAR Data:** GeoCue TrueView 515 and DJI L2 data
- ✅ **Counted Areas:** Multiple sites with known penguin counts

---

## Ground Truth Data Summary

### Caleta Sites
1. **Tiny Island**
   - Count: 321 penguins
   - Area: 0.7 ha
   - Sensors: L2 (ortho), H30T

2. **Small Island**
   - Count: 1,557 penguins
   - Area: 4 ha
   - Sensors: L2 (ortho), H30T

3. **Box Count 1**
   - Count: 8 penguins (one walked outside collection zone)
   - Sensors: H30T

4. **Box Count 2**
   - Count: 12 penguins (counted inside rope bounds)
   - Sensors: H30T

### San Lorenzo Sites
1. **Full Area**
   - Area: 66 ha (not fully counted)

2. **Road Total Count**
   - Count: 359 penguins
   - GPS waypoints: Available in PDF

3. **Plains Total Count**
   - Count: 453 penguins
   - GPS waypoints: Extensive edge waypoints documented

4. **Caves Total Count**
   - Count: 908 penguins
   - GPS waypoints: Start/end points and edge waypoints documented

5. **Box Count High Density Caves**
   - Count: 32 penguins (2 walked out between thermal and LiDAR)

6. **Box Count High Density Bushes**
   - Count: 55 penguins

**Total Known Counts:** ~3,705 penguins across all counted areas

---

## Technical Challenge: GPS to Pixel Coordinate Conversion

### Current State
- **Existing Ground Truth:** Pixel coordinates (x, y) in CSV files
- **New Ground Truth:** GPS coordinates (lat, lon) from field collection
- **Gap:** No automated process to convert GPS → pixel coordinates in thermal images

### Required Workflow
1. **Match GPS waypoints to thermal images** (spatial/temporal matching)
2. **Project GPS coordinates to pixel coordinates** using:
   - Camera pose (GPS, altitude, gimbal angles) from EXIF
   - Camera model (FOV, sensor size)
   - DSM/DTM for terrain correction
   - Boresight calibration (if available)
3. **Validate projection accuracy** (manual QC on sample points)
4. **Generate pixel-level ground truth CSVs** for thermal detection optimization

---

## Proposed Implementation Plan

### Phase 1: Data Extraction and Organization [2-4 hours]

**Tasks:**
1. **Extract GPS waypoints from PDF**
   - Parse structured waypoint data
   - Organize by site and mission
   - Export to structured format (CSV/GeoJSON)

2. **Inventory thermal imagery**
   - List all H30T thermal images from Argentina missions
   - Extract EXIF metadata (GPS, timestamp, altitude, gimbal angles)
   - Create index mapping images to missions/sites

3. **Match waypoints to images**
   - Spatial matching: Find images containing waypoint locations
   - Temporal matching: Use timestamps if available
   - Create mapping table: waypoint → candidate images

**Deliverables:**
- `data/2025/ground_truth/gps_waypoints.csv` (or GeoJSON)
- `data/2025/ground_truth/thermal_image_index.csv`
- `data/2025/ground_truth/waypoint_image_mapping.csv`

**Tools Needed:**
- PDF parsing script or manual extraction
- EXIF extraction script (can use existing `pipelines/thermal.py` functions)
- Spatial matching script (point-in-polygon or distance-based)

---

### Phase 2: Georeferencing Implementation [4-6 hours]

**Tasks:**
1. **Create GPS-to-pixel projection function**
   - Leverage existing `pipelines/thermal.py` camera model
   - Use `ortho_one()` back-projection logic in reverse
   - Implement forward projection: GPS (lat, lon, alt) → pixel (u, v)

2. **Handle coordinate system transformations**
   - Convert GPS (WGS84) to UTM Zone 20S (project coordinate system)
   - Account for terrain elevation (use DSM if available, or assume flat)
   - Apply boresight corrections if calibrated

3. **Batch process waypoints**
   - For each waypoint-image pair:
     - Extract camera pose from image EXIF
     - Project GPS coordinate to pixel coordinate
     - Validate projection (check if within image bounds)
     - Store result with confidence metrics

**Deliverables:**
- `scripts/georeference_ground_truth.py` (new script)
- `data/2025/ground_truth/pixel_coordinates.csv` (GPS + pixel coords)
- Validation report showing projection accuracy

**Technical Approach:**
```python
# Pseudo-code for GPS → pixel projection
def gps_to_pixel(gps_lat, gps_lon, gps_alt, image_path, dsm_path=None):
    # 1. Load camera pose from image EXIF
    pose = extract_pose_from_exif(image_path)
    
    # 2. Convert GPS to UTM
    utm_x, utm_y = wgs84_to_utm(gps_lat, gps_lon, zone=20, south=True)
    
    # 3. Get terrain elevation (from DSM or pose altitude)
    terrain_z = get_elevation(utm_x, utm_y, dsm_path) or pose.altitude
    
    # 4. Compute camera-to-point vector
    # 5. Transform to camera coordinates
    # 6. Project to pixel coordinates
    u, v = project_to_image(utm_x, utm_y, terrain_z, pose, camera_model)
    
    return u, v
```

---

### Phase 3: Validation and Quality Control [2-3 hours]

**Tasks:**
1. **Manual validation sample**
   - Select 10-20 waypoints across different sites
   - Visually verify pixel coordinates align with penguin locations in thermal images
   - Document any systematic offsets or errors

2. **Accuracy assessment**
   - Measure projection error (distance between projected pixel and actual penguin center)
   - Identify sources of error:
     - GPS accuracy (RTK vs standard GPS)
     - Terrain model accuracy
     - Camera pose accuracy
     - Boresight calibration errors

3. **Error correction**
   - If systematic offsets found, apply corrections
   - Document correction parameters
   - Re-project with corrections

**Deliverables:**
- Validation report with accuracy metrics
- Corrected pixel coordinates if needed
- Documentation of error sources and corrections

---

### Phase 4: Ground Truth Dataset Creation [1-2 hours]

**Tasks:**
1. **Generate pixel coordinate CSVs**
   - Format matching existing ground truth CSVs (`verification_images/frame_*.csv`)
   - Include metadata: site, mission, GPS coordinates, confidence scores

2. **Organize by thermal image**
   - Group waypoints by image
   - Create per-image ground truth files
   - Cross-reference with existing legacy ground truth format

3. **Create summary statistics**
   - Total ground truth points per site
   - Coverage statistics (how many images have ground truth)
   - Distribution across sites and missions

**Deliverables:**
- `data/2025/ground_truth/pixel_coords/` directory with per-image CSVs
- `data/2025/ground_truth/summary.json` (metadata and statistics)
- Documentation of dataset structure

---

### Phase 5: Integration with Thermal Detection Optimization [Future]

**Tasks:**
1. **Update optimization scripts**
   - Modify `scripts/optimize_thermal_detection.py` to use new ground truth
   - Support both legacy pixel CSVs and new georeferenced data

2. **Run parameter optimization**
   - Use new ground truth dataset for parameter tuning
   - Compare results across different sites/conditions
   - Identify optimal thresholds for H30T data

3. **Calibration validation**
   - Use ground truth to validate thermal calibration
   - Check if 9°C offset issue affects detection accuracy
   - Test calibration correction methods

**Deliverables:**
- Optimized thermal detection parameters
- Validation results comparing old vs new ground truth
- Updated thermal detection pipeline with calibrated parameters

---

## Technical Dependencies

### Existing Infrastructure (Available)
- ✅ `pipelines/thermal.py` - Camera model, pose extraction, orthorectification
- ✅ `scripts/run_thermal_ortho.py` - CLI for thermal processing
- ✅ EXIF extraction functions (`load_poses()`, `pose_for_image()`)
- ✅ Coordinate transformation utilities (pyproj)

### New Components Needed
- ⚠️ GPS-to-pixel projection function (reverse of orthorectification)
- ⚠️ Waypoint-to-image matching logic
- ⚠️ Batch georeferencing script
- ⚠️ Validation/QC tools

### Data Requirements
- ✅ GPS waypoints (from PDF)
- ✅ Thermal images with EXIF metadata
- ⚠️ DSM/DTM for terrain correction (may need to generate from LiDAR)
- ⚠️ Boresight calibration (if available from field)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GPS waypoint accuracy insufficient | Medium | High | Use RTK GPS data if available; validate with manual checks |
| Waypoint-to-image matching fails | Medium | High | Use spatial + temporal matching; manual verification |
| Terrain model unavailable | High | Medium | Use flat terrain assumption initially; generate DSM from LiDAR later |
| Projection accuracy poor | Medium | High | Validate on sample points; apply systematic corrections |
| H30T camera model differs from H20T | Medium | Medium | Test projection on known points; adjust FOV if needed |

---

## Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Data Extraction | 2-4 hours | PDF access, thermal image inventory |
| Phase 2: Georeferencing | 4-6 hours | Phase 1, camera model understanding |
| Phase 3: Validation | 2-3 hours | Phase 2, manual QC time |
| Phase 4: Dataset Creation | 1-2 hours | Phase 3 |
| **Total** | **9-15 hours** | |

**Note:** Timeline assumes working knowledge of existing thermal pipeline. May extend if camera model debugging needed.

---

## Success Criteria

1. ✅ GPS waypoints extracted and organized
2. ✅ Automated GPS-to-pixel projection implemented
3. ✅ Projection accuracy validated (<5 pixel error for RTK GPS)
4. ✅ Pixel coordinate ground truth CSVs generated for all sites
5. ✅ Dataset ready for thermal detection parameter optimization

---

## Questions for Discussion

1. **GPS Accuracy:** What GPS system was used? (RTK, standard GPS, phone GPS?)
   - Affects expected projection accuracy
   - RTK: <10cm → <1 pixel error
   - Standard GPS: 3-5m → 5-10 pixel error
   - Phone GPS: 5-10m → 10-20 pixel error

2. **Terrain Model:** Is DSM/DTM available from LiDAR data?
   - Needed for accurate projection if terrain is not flat
   - Can generate from LiDAR if available

3. **Boresight Calibration:** Was boresight calibration performed in field?
   - Needed for accurate camera pointing
   - Can estimate from LRF data if available

4. **Image Coverage:** Do thermal images cover all waypoint locations?
   - Some waypoints may be outside thermal image footprints
   - Need to identify which waypoints can be georeferenced

5. **Priority Sites:** Which sites should be prioritized for initial work?
   - Box counts (smaller areas) may be easier to validate
   - Large count areas (Small Island: 1,557) provide more data points

---

## Next Steps (Immediate Actions)

1. **Extract GPS waypoints from PDF** → CSV/GeoJSON format
2. **Inventory thermal imagery** → Create image index with EXIF metadata
3. **Review existing camera model code** → Understand projection math
4. **Create proof-of-concept** → Test GPS-to-pixel on 1-2 waypoints manually
5. **Design georeferencing script** → Implement batch processing

---

## Related Documentation

- `CLIENT_STATUS_REPORT_2025-11-20.md` - Current project status
- `docs/FIELD_DATA_SPECIFICATIONS.md` - Data requirements and specifications
- `pipelines/thermal.py` - Thermal processing pipeline (camera model)
- `docs/planning/NEXT_STEPS.md` - Previous planning document
- `verification_images/README.md` - Legacy ground truth format

---

*Plan created: 2025-12-01*  
*Status: Planning - Awaiting approval to proceed*

