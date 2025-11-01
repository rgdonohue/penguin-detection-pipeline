# Field Data Specifications and Requirements

**For**: Argentina Field Team
**From**: Data Processing and Analysis Team
**Last Updated:** 2025-10-17 (original issue: October 2024)
**Purpose**: Technical specifications based on empirical test data (NOT manufacturer claims)

---

## Important: Validation Scope

These specifications are based on **field testing at one coastal Patagonian site in spring**:
- **Altitude testing**: Historical DJI L2 flights at 30-40m AGL produced 1,175 deduped detections matching ~1,100 manual count
- **Operational plan**: Begin new acquisition at 60-70m AGL and step down only if density/QA checks require it
- **Processing parameters**: Calibrated on 34 GB field data (5 tiles) for accurate colony counts
- Point density values are qualitative estimates based on field experience, not systematic altitude sweep measurements
- No comprehensive validation across multiple sites, seasons, or conditions

**Treat these as starting guidance, not absolute requirements**. Verify actual conditions at your deployment site before committing to full survey.

---

## Overview

This document presents data requirements for the penguin detection pipeline based on analysis of test datasets from Patagonian colonies. These specifications come from empirical test data on actual penguins, which differs significantly from manufacturer marketing claims.

**Important Context**: All specifications derived from **Puerto Madryn coastal colony site, spring breeding season, November 2024**. Applying to other sites assumes similar conditions:
- Flat to gently sloping coastal terrain
- Surface-nesting Magellanic penguins
- Spring breeding season activity patterns
- Coastal Patagonian environmental conditions

**Site variations to consider**:
- Different terrain types may require different flight altitudes or processing parameters
- Burrowing species/behaviors require ground-penetrating methods (not covered here)
- Different seasons may affect penguin distribution and detectability
- Inland or non-coastal sites may have different LiDAR reflectivity characteristics

---

## LiDAR Requirements for Detection

### Performance Characteristics from Test Data

Analysis of test data established clear relationships between data quality and detection success. Pipeline produces hundreds of candidate detections per tile (862 with optimized parameters on test tile), with detection counts consistent with field observations of colony density.

**Point Density Context**:

**CRITICAL**: The specific density requirements below are **inferred, not measured**. Test data (DJI L2 at 30-40m) showed ~8,700-9,000 pts/m², but no measurements exist at other altitudes.

**Theoretical considerations** for detecting 30-50cm objects:
- Higher density likely improves object definition
- Minimum density threshold unknown without testing
- TrueView 515 may perform differently than DJI L2

**What we actually know**:
- DJI L2 at 30-40m: ~8,700-9,000 pts/m² → 1,175 detections (LAS metadata for `cloud0.las` / `cloud3.las` reports `software_id = "DJI TERRA 4.5.18.1 DJI L2"`)
- Higher altitudes: No data
- Minimum viable density: Unknown
- TrueView 515 performance: Untested

**Field strategy**: Test point density at each altitude and assess detection quality empirically.

**GPS Accuracy Requirements**:
- **<0.5m horizontal**: Clean tile registration
- **0.5-1.0m**: Acceptable with minor edge discontinuities
- **>1.0m**: Registration errors, potential false detections

---

### Operational Parameters

**IMPORTANT**: Test data was acquired with DJI L2 sensor at 30-40m. Field deployment will use GeoCue TrueView 515.

| Parameter | Specification | Rationale |
|-----------|--------------|-----------|
| Altitude | **Start at 60-70m AGL** | Wildlife welfare priority (Antarctic Treaty guidelines) |
| Ground speed | 3-5 m/s | Maintains consistent coverage |
| Overlap | 50% minimum | Prevents edge artifacts |
| File format | LAS 1.2+ | Required for processing pipeline |

**Altitude Testing Protocol**:

1. **Start at 70m AGL** - Wildlife welfare baseline
2. **Test at 60m AGL** - If 70m point density insufficient
3. **Test at 50m AGL** - Only with wildlife observer and approval
4. **40m AGL** - Only with written approval and continuous monitoring

**Data Context**:
- DJI L2 at 30-40m produced ~8,700-9,000 pts/m² (far exceeding requirements)
- TrueView 515 specifications indicate 80-120m operational range
- No test data exists above 40m altitude
- Point density at higher altitudes must be verified in field

**Site Variability Considerations**:
- Actual point density varies with flight speed, overlap, terrain reflectivity, surface type
- Different sites may produce different densities at same altitude:
  - Dark/wet surfaces → lower reflectivity → fewer returns
  - Vegetation cover → complex returns, harder to model ground
  - Rocky/steep terrain → more variable point density
- **Recommendation**: Test actual density at deployment site before committing to full survey

**Note**: GeoCue marketing suggests 75m altitude for "good results" but this refers to buildings/powerlines, not 30-50cm wildlife. Altitude guidance based on field experience with successful detections, sensor specifications, and LiDAR physics (inverse square law). Specific point density values not systematically measured across altitude sweep.

**Coverage Estimates** (from test acquisitions):
- 40m altitude, 5 m/s speed: ~2.5 hectares per battery
- Data volume: ~10GB per hectare (compressed LAS)
- Processing time: ~1.2 hours per hectare

---

## Thermal Data Specifications

### Sensor Capabilities and Limitations

**Equipment Note**: Field deployment will use DJI H30T (1280×1024 resolution) vs. H20T (640×512) used in testing.

**Collection guidance**: Capture thermal imagery concurrently with LiDAR flights whenever platform configuration allows. Thermal data supports validation, QA, and behavioural analysis but does not replace LiDAR for counting.

**H20T Test Results** (single colony, spring breeding season, 26 samples):
- Measured thermal contrast: 0.14°C above background
- Scene noise: ±2.91°C
- Detection precision: 2.2% at optimal threshold
- Signal-to-noise ratio: 0.047σ

**Important limitations**: Measurements from one location, one day, resting penguins during spring breeding. Thermal contrast may vary with season, weather, activity level, or molt stage.

**H30T Considerations** (untested):
- 4× pixel count (1280×1024 vs 640×512) = 2× linear resolution improvement
- Better spatial discrimination may improve signal averaging
- Same 0.14°C thermal contrast measured under spring breeding conditions
- **Unknown**: Whether improved resolution enables better detection than H20T
- **Unknown**: Whether thermal contrast differs under other conditions (different seasons, active penguins, post-immersion)
- **Recommendation**: Test flights needed to assess H30T performance under field conditions

**If Collecting Thermal Data**:
- Altitude: Match the selected LiDAR altitude for registration
- Timing: Vary collection times to test contrast differences (early morning, midday, late afternoon)
- Conditions: Sample different activity states if possible (resting, recently active, post-water immersion)
- Purpose: Build validation/confidence layers (ΔT scoring), behavioural activity maps, and archival datasets; individual detection capability unknown without H30T testing across varied conditions

### Multi-Sensor Data Products

- **Primary detection**: LiDAR HAG detections → candidate geospatial layers (GeoJSON/GPKG)
- **Thermal validation**: ΔT-based confidence scores for each LiDAR detection (requires thermal↔LiDAR registration)
- **Thermal activity maps**: Colony-level heatmaps summarising behavioural hotspots
- **QA deliverables**: Percentage of LiDAR detections with positive thermal confirmation, notes on LiDAR-only detections flagged for review
- **Archival assets**: Raw 16-bit thermal frames, ΔT rasters, and ground-truth CSVs to support future fusion research

---

## Data Quality Verification

Optional field verification can be performed using:

```bash
# Check point cloud density
pdal info [filename].las | grep "count:"
# Log actual point count and compute pts/m² for each altitude tested

# Test detection (if processing scripts available)
python scripts/run_lidar_hag.py --tiles [filename].las --out-dir test --plots
# Review: Point density log, detection count, QC visualization
```

This verification takes <1 minute per tile and can identify acquisition issues before leaving a site.

---

## Environmental Considerations

Analysis of test data under varying conditions revealed:

**Wind Impact on Data Quality**:
- <10 km/h: No measurable effect
- 10-20 km/h: Minor GPS drift, correctable in processing
- >20 km/h: Degraded GPS accuracy affecting registration

**Optimal Conditions**:
- LiDAR: Functions well in overcast conditions
- Thermal: Clear sky enhances radiative cooling contrast
- Both: Calm conditions (<10 km/h wind) preferred

---

## Processing Requirements Summary

### Essential Data Characteristics
1. **Point density sufficient for detection** (record actual density at each altitude; minimum threshold under evaluation)
2. **GPS accuracy <1m horizontal** (RTK positioning required for tile registration)
3. **Complete coverage** (gaps = no detections in those areas)
4. **Wildlife welfare compliance** (start at 60-70m AGL per guidelines)

### Recoverable Issues
- Minor GPS drift (<1m)
- Variable point density between tiles
- Incomplete metadata
- Mixed acquisition parameters

### Non-Recoverable Issues
- Large areas below density threshold
- GPS errors exceeding 1m
- Corrupted files
- Major coverage gaps

---

## Timeline and Deliverables

**Processing Timeline**:
- Week 1: Data validation and initial processing
- Week 2: Detection refinement and quality control
- Week 3: Final products and documentation

**Expected Deliverables**:
- Detection maps (GeoJSON/GeoPackage formats)
- Statistical summaries (counts, density distributions)
- Quality control visualizations
- Processing documentation for reproducibility

---

## Contact and Support

For technical questions during acquisition:
- Verify data meets density thresholds
- Check GPS fix quality if registration issues occur
- Send sample tiles for validation if uncertain

Data transfer arrangements flexible based on team preferences (physical drives, cloud transfer, etc.). Raw LAS/LAZ files plus any navigation metadata required for processing.

---

*For complete system documentation, see PENGUIN_DETECTION_PIPELINE_PROJECT_SUMMARY.md*
*For thermal investigation details, see THERMAL_FINDINGS_SUMMARY.md*
