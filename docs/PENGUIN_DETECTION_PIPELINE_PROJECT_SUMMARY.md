# Penguin Detection Pipeline - Project Summary

**Last Updated:** 2025-10-17
**Status**: DEPLOYMENT READY
**Target**: Argentina Field Campaign, November 2025
**Test Location**: Magellanic penguin colonies, coastal Patagonia (Puerto Madryn, Argentina)

---

## Validation Status and Limitations

**What this document is based on**:
- **LiDAR**: 34 GB field data (5 tiles) producing 1,175 deduped detections matching ~1,100 manual count
- **Sensor**: DJI L2 LiDAR (test data; LAS metadata lists `software_id = "DJI TERRA 4.5.18.1 DJI L2"` in `data/legacy_ro/penguin-2.0/data/raw/LiDAR/cloud0.las` and `cloud3.las`) – deployment will use GeoCue TrueView 515
- **Altitude**: 30-40m AGL (test data) - deployment will start at 60-70m per wildlife guidelines
- **Thermal**: 26 penguin samples from 7 frames over 21 seconds (H20T)
- **Location**: Single coastal colony site (Puerto Madryn) in spring breeding season
- **Hardware**: MacBook Air M-series for processing

**What we don't have**:
- Multiple test sites or colonies
- Seasonal variation data
- Comprehensive ground truth validation (false positive/negative rates unknown)
- Statistical analysis with error bars or confidence intervals
- Systematic altitude-density measurements (guidance based on field experience, not controlled sweep)
- Testing on different terrain types or penguin species/behaviors

**Confidence levels**:
- **LiDAR processing**: Works with DJI L2 data; TrueView 515 untested
- **Wildlife-compliant altitude (60-70m)**: No test data at this height
- **Point density requirements**: Unknown - test data shows 8,700-9,000 pts/m² at 30-40m
- **Thermal 0.14°C contrast**: Measured from small sample under specific conditions
- **H30T potential**: Untested equipment may perform better than H20T baseline

**Use this document as**: Starting point and operational guidance for sites similar to test location. Be prepared to adjust parameters and validate assumptions at deployment site.

---

## Operational Decision (2025-10-16)

- ✅ **Track B – LiDAR-only detection is the operational path.** HAG-based LiDAR processing produced 1,175 detections matching ~1,100 manual counts and is ready for field deployment.
- ✅ **Thermal investigation complete.** Thermal imagery cannot provide reliable per-penguin detection (best F1 ≈ 0.30), but it is recommended for validation/QC and behavioural context.
- 🔄 **Thermal + LiDAR fusion** (confidence scoring, FP filtering) remains blocked on precise thermal-to-LiDAR registration; run experiments as soon as alignment products become available.

---

## Executive Summary

We've developed a penguin detection pipeline with two components:

1. **LiDAR detection** (primary): Processes field data, produces several hundred candidate detections per tile (802 on test tile with tuned parameters)
2. **Thermal characterization**: Demonstrated strong contrast in several frames (ΔT ≈ 8–11 °C) but poor automated detection (best F1 ≈ 0.30); thermal now serves as a validation/context layer

LiDAR detection counts match observed colony density and processing runs are reproducible.

### Key Performance Metrics

**LiDAR (DJI L2 test data):**
- **Detections**: 1,742 raw → 1,175 deduped (matches ~1,100 manual count)
- **Processing**: ~18-35 sec per tile (7-9 GB files, MacBook Air M-series)
- **Test altitude**: 30-40m AGL (produced ~8,700-9,000 pts/m²)
- **Deployment altitude**: Start at 60-70m AGL (wildlife guidelines)
- **Expected per-tile**: Unknown at higher altitudes

**Thermal:**
- ΔT ≈ 8–11 °C in most frames (≈3 σ), ΔT ≈ 0.14 °C in worst-case frame (0.05 σ)
- Enhanced methods (bilateral filtering, local ΔT) achieve at best F1 ≈ 0.30
- Recommended use: validation / false-positive filtering / behavioural context (not primary detection)

---

## 1. LiDAR Detection System - OPERATIONAL

### System Status

The pipeline uses height-above-ground (HAG) analysis to find 40-70cm tall objects. Tested with DJI L2 data from Magellanic penguin colonies.

**Performance**:
- Outputs GeoJSON/GPKG formats
- Processes 4.4GB files in ~12 seconds (MacBook Air)
- Produces hundreds of detections per tile
- Results are reproducible with fixed parameters

**Processing Architecture**:
```
LAS/LAZ acquisition → Terrain modeling → HAG computation → Object segmentation → Validation → GIS outputs
```

**Deliverable Products**:
- Georeferenced detection maps (GeoJSON/GPKG formats)
- Population density statistics
- Terrain visualization products (hillshade with detection overlay)
- Quality assurance metrics (point density, coverage statistics)

### Flight Parameters

**For deployment (prioritizing wildlife welfare):**

| Parameter | Value | Why |
|-----------|-------|-----|
| Altitude | Start at 60-70m AGL | Wildlife welfare guidelines (Antarctic Treaty) |
| Test protocol | 70m → 60m → 50m → 40m | Only descend if necessary with approvals |
| Ground speed | 3-5 m/s | Consistent coverage |
| Point density | To be verified | Test data: 8,700-9,000 pts/m² at 30-40m with DJI L2 |
| Wind | <20 km/h | Keeps GPS accuracy acceptable |
| Wildlife observer | Required | Monitor behavioral responses |

Back up field data to three locations with SHA256 checksums for verification.

### How It Works

LiDAR measures 3D structure directly, making it possible to identify 40-70cm tall objects on relatively flat ground. The height-above-ground metric works regardless of lighting or temperature.

Pipeline tested on field data. Detection counts match observed colony density. Parameters were tuned iteratively.

### Assumptions and Limitations

**Site-Specific Context**:
All test data comes from **one coastal Patagonian colony site (Puerto Madryn) in spring breeding season**. Applying these results to other sites assumes:
- Similar terrain (flat to gently sloping coastal habitat)
- Similar penguin behavior (surface-nesting, not burrowing)
- Similar colony density and distribution patterns
- Similar environmental conditions (coastal Patagonia climate)

**What may differ at other sites**:
- Different terrain (rocky slopes, dense vegetation, complex topography) → HAG method may fail
- Burrowing species or behaviors → penguins underground won't be detected
- Different seasons → penguin distribution, molt stage, behavior may change
- Inland or different climate zones → different point cloud reflectivity, thermal contrast
- Different colony densities → detection count patterns may differ

**Key Assumptions**:
1. Penguins are 40-70cm tall (adults standing/sitting)
2. Terrain is relatively flat (HAG method requires ground baseline)
3. Penguins are on ground surface (not in burrows or under vegetation)
4. Point density remains high enough to resolve 30-50cm objects (minimum threshold under evaluation)
5. GPS accuracy <1m sufficient for tile registration

**Generalization uncertainty**: These parameters were tuned on one test site. No validation on different colonies, seasons, or locations.

**Detection Count Uncertainty**:
- Test tile: 802 detections (reproducible with fixed parameters)
- **Unknown**: Actual false positive and false negative rates
- **Not validated** against comprehensive ground truth counts
- Detection counts are "candidate detections" - require interpretation
- Parameter sensitivity: Different HAG/size thresholds produce different counts

**What Could Go Wrong**:
- **If terrain isn't flat**: HAG method may fail on steep slopes or complex topography
- **If penguins in burrows**: Underground penguins won't be detected (height = 0)
- **If point density low**: May miss smaller penguins or get fragmented detections
- **If GPS accuracy poor**: Tile registration errors could create false detections at boundaries
- **If penguins clustered tightly**: May merge into single larger detection

**Processing Uncertainty**:
- Ground model quality depends on point density and terrain complexity
- HAG threshold selection affects detection count (tuned on one test file)
- Size filtering (2-30 cells) based on expected penguin size - may exclude juveniles or include rocks

---

## 2. Thermal Characterization Study - COMPLETE

### What We Measured

Thermal signatures of Magellanic penguins using DJI H20T infrared camera. Extracted 16-bit radiometric temperature data.

**Methodology**:
- Single colony site (Puerto Madryn), single day, spring breeding season
- 7 thermal frames over 21 seconds at ~30m altitude
- 26 visually confirmed penguin locations from concurrent visible imagery
- 16-bit radiometric temperature extraction from DJI H20T
- Quantified thermal contrast relative to background terrain

**Sample limitations**: Initial measurements from one location, one day, one set of environmental conditions. Not comprehensive species characterization.

### Key Scientific Findings

**Thermal Measurements** (Puerto Madryn colony, spring breeding season):
- Frames 0353/0355: Penguins ~8–11 °C warmer than background (≈3 σ)
- Frame 0356: Penguin contrast 0.14 °C (0.05 σ) – worst case
- Scene standard deviation (0356): 2.91 °C

### Interpretation

Penguins often present clear, positive thermal signatures, but contrast can collapse under certain conditions (e.g., frame 0356). Radiometric extraction is reliable, yet automated detection remains non-operational (best F1 ≈ 0.30 after bilateral filtering or local ΔT annulus).

**Detection Performance**:
- Best baseline run (bilateral filter, 1.5σ): precision 14–36%, recall 24–48%, F1 ≤ 0.29
- Local ΔT (4 σ) improves precision (≈43% on frame 0353) but recall drops to ≈23% (F1 ≈ 0.30)
- No tested configuration achieves both high precision (>50%) and high recall (>80%)

**Important context**: Thermal signatures vary by frame; continued sampling across seasons, activity states, and sensor classes (e.g., DJI H30T) is recommended.

### Research & Operational Applications

Although thermal cannot replace LiDAR for counting, it provides value when treated as a secondary validation layer:
- Confidence scoring for LiDAR detections (ΔT > ~5 °C implies warm-blooded target)
- False-positive filtering (LiDAR-height objects with no thermal signature)
- Colony activity mapping and behavioral documentation
- Visual QA and stakeholder reporting
- Dataset for future fusion and sensor evaluation once registration is available

### Scientific Contribution

This investigation provides:
1. **Initial measurements**: Thermal signatures under spring breeding conditions at one colony site
2. **Methodological framework**: Reproducible protocol for radiometric data extraction
3. **H20T performance baseline**: Detection capabilities under measured conditions
4. **Foundation for expanded study**: Infrastructure for testing across seasons and conditions

These initial measurements establish a starting point for understanding thermal detection feasibility, though additional sampling across varied conditions is needed for comprehensive species characterization.

---

## 3. Deployment Strategy

### Planned Field Equipment (Argentina 2025)
- DJI M350 RTK (primary platform for TrueView 515)
- Skyfront Perimeter 8 (long-endurance backup; deploy only after compatibility checks)
- GeoCue TrueView 515 LiDAR sensor (primary detection instrument for 2025 campaign)
- DJI Zenmuse H30T thermal sensor (documentation and experimental detection trials)

### Primary Data Collection

**LiDAR Survey Protocol**:
- Begin with 70m test flight, then 60m/50m/40m only if density requirements demand it (with approvals)
- Maintain 50% flight line overlap for complete coverage
- Process initial test area in-field to verify point density at each altitude
- Adjust acquisition parameters based on test results and wildlife observer feedback
- Implement triple-backup data management with checksum verification

**Thermal Validation & Context**:
- Capture thermal simultaneously with LiDAR (H30T payload)
- Do not alter LiDAR flight parameters solely for thermal contrast
- Generate ΔT confidence scores and colony activity maps during post-processing
- Optionally collect additional low-altitude passes if time permits for research purposes

### Expected Deliverables

**Primary Products** (2-3 weeks post-acquisition):
- Georeferenced detection maps with location precision metrics
- Population statistics and density distributions
- Terrain visualization products with detection overlays
- Comprehensive processing documentation for reproducibility

**Supporting Documentation**:
- Thermal characterization report with methodological details
- Field acquisition metadata and environmental conditions
- Complete data provenance records with checksums
- Quality control validation reports

### Success Metrics

Successful deployment defined by:
- LiDAR point density documented at each altitude and sufficient for detection (based on onsite QA)
- Complete data backup with verified checksums
- Successful pipeline execution producing validated outputs
- Quality metrics within established thresholds
- Thermal documentation captured (schedule permitting)

---

## 4. Technical Validation

### What Works

**LiDAR Pipeline**:
- Works on colony data
- Outputs GeoJSON and GPKG
- Reproducible results
- 30-40m altitude (DJI L2 test data) produced ~8,700-9,000 pts/m²

**Thermal Processing**:
- Extracts 16-bit radiometric data
- Tested on 26 locations, 7 frames
- Methodology is reproducible

### Potential Issues

1. **Weather delays**: LiDAR works in overcast conditions, so schedule can flex
2. **Equipment failure**: Prioritize LiDAR as primary sensor, thermal is optional
3. **Low point density**: Test a small area first to verify density before full survey
4. **Data loss**: Back up to multiple drives with checksums

Processing scripts are documented in the runbook. Field troubleshooting guide is available.

---

## Summary

The LiDAR detection pipeline is ready for field deployment **at sites similar to the test location** (coastal Patagonia, flat terrain, surface-nesting penguins). Processing works on test data from Puerto Madryn, produces detection counts matching field observations, and runs deterministically.

**Important**: All parameters tuned on one coastal colony site in spring. For deployment at different sites, consider:
- Test actual point density before committing to full survey
- Verify HAG method works on local terrain (may fail on steep slopes/vegetation)
- Adjust parameters if colony characteristics differ significantly
- Be prepared for different detection patterns in different seasons or locations

The thermal work measured 0.14°C contrast from 26 penguins at Puerto Madryn during spring breeding - enough to show H20T detection is problematic under those conditions, but not enough to characterize the species across different sites, seasons, or activity states.

---

*Supporting documents:*
- *`FIELD_DATA_SPECIFICATIONS.md` - Technical requirements from test data analysis*
- *`THERMAL_FINDINGS_SUMMARY.md` - Complete thermal characterization study*
