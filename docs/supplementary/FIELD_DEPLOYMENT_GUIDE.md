# Field Deployment Guide - Argentina Penguin Survey

**Version**: 1.0  
**Date**: 2025-10-14  
**Deployment**: Argentina, Spring 2025  
**Status**: PRE-DEPLOYMENT CRITICAL GUIDANCE

---

## Executive Summary

**PRIMARY MISSION**: LiDAR-based penguin detection (proven methodology with validated pipeline)  
**SECONDARY**: Thermal documentation (optional - see investigation findings below)

**Key Finding**: Thermal investigation characterized penguin thermal signatures in Patagonian coastal conditions. Magellanic penguin surface temperature (−5.56°C) approaches ground temperature (−5.69°C) due to effective insulation, resulting in signal-to-noise ratio of 0.047σ. **LiDAR recommended as primary detection method** for reliable operational results.

**This guide provides field-tested parameters for successful LiDAR-based wildlife detection, with guidance for optional thermal data collection.**

---

## 1. LiDAR Flight Parameters (Primary Mission)

### Recommended Settings

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Altitude** | 30-40m AGL | Optimal point density for penguin-sized targets |
| **Speed** | 3-5 m/s | Slower = higher density (critical for 30-50cm objects) |
| **Overlap** | 50-60% | Ensures no coverage gaps, improves terrain model |
| **Point Density Target** | >100 pts/m² | Pipeline requires 50-100 pts/m² for reliable detection |
| **Time of Day** | Anytime | LiDAR independent of lighting conditions |
| **Weather** | Avoid high winds | GPS accuracy degrades in wind |

### Equipment: GeoCue 515 LiDAR

**Verified Performance**:
- Tested at 30-40m AGL in similar conditions
- Achieves >100 pts/m² at recommended parameters
- RTK GPS provides sub-10cm horizontal accuracy

### Flight Pattern

```
1. Start with small test area (~100m × 100m)
2. Process immediately to verify point density
3. Adjust parameters if needed (see QC section)
4. Execute full colony coverage with verified settings
5. Overlap adjacent passes by 50%+ to avoid gaps
```

**Why test area first**: Catch parameter issues before committing to full survey.

---

## 2. Thermal Camera Considerations (Optional)

### Investigation Findings

**Based on thermal characterization study** (`docs/THERMAL_INVESTIGATION_FINAL.md`):

- **Penguin surface temp**: −5.56°C ± 2.21°C
- **Ground temp**: −5.69°C ± 2.91°C  
- **Contrast**: 0.14°C (0.047σ SNR)
- **Detection performance**: Precision = 2.2% (98% false positives)
- **Assessment**: Insufficient thermal contrast for reliable detection with current commercial camera technology in these environmental conditions

### If Collecting Thermal Anyway (Documentation/Investigation)

**Purpose**: Visual documentation and future research ONLY - not detection.

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Altitude** | 15-20m AGL | Better GSD (1-2 cm/px vs. 3-4 cm at 30m) |
| **Speed** | 3 m/s | Slower for higher frame rate |
| **Time** | Early morning | Penguins warmer than ground after night |
| **Avoid** | Midday | Sun heats ground, increases variance |
| **Settings** | Emissivity 0.98, Manual gain | If H30T allows adjustment |

**Expected outcome**: Thermal imagery useful for documentation and spatial context. Individual penguin detection challenging given measured contrast levels; may show aggregate colony thermal patterns.

---

## 3. Flight Strategy: Separate LiDAR and Thermal

### Recommended Daily Schedule

```
Day 1 Morning (0700-1000):
  ├─ LiDAR survey: Colony area at 30-40m AGL
  └─ Focus: Complete coverage, consistent parameters

Day 1 Afternoon (1400-1700):
  ├─ Download and backup data
  ├─ Run QC on first tiles (see Section 5)
  └─ Verify point density and initial detections

Day 2 Morning (0630-0730, optional):
  ├─ Thermal survey: Same area at 15-20m AGL
  └─ Purpose: Documentation only

Day 2+ (weather dependent):
  ├─ Additional LiDAR coverage areas
  └─ Re-fly any tiles with insufficient point density
```

### Why Separate Flights?

1. **Different optimal altitudes** (LiDAR 30-40m, thermal 15-20m)
2. **Different optimal timing** (LiDAR anytime, thermal early morning)
3. **Reduced payload** = longer flight time per battery
4. **Risk isolation** - If one sensor fails, other dataset preserved

**Research literature** (`thermal-lidar-fusion/research/`) documents this as best practice for multi-sensor wildlife surveys when sensors require different optimal acquisition parameters.

---

## 4. Data Management Protocol (CRITICAL)

### Immediate Post-Flight (On Landing)

```bash
# 1. Copy data from drone to laptop (DO NOT delete from drone yet)
cp -r /drone/DATA/Flight_XX /laptop/raw_data/Flight_XX

# 2. Calculate checksums
cd /laptop/raw_data/Flight_XX
find . -type f -exec shasum -a 256 {} \; > checksums.txt

# 3. Log to field notebook (see Section 8 for template)
```

### Daily End-of-Day Protocol

```bash
# 1. Copy to backup drive
rsync -av /laptop/raw_data/ /backup_drive/argentina_2025/

# 2. Run quick sanity check
# For LiDAR:
pdal info flight_XX_tile_01.las | grep "count:"
# Expected: >1M points for 100m x 100m tile at 100 pts/m²

# For Thermal:
ls -lh *.JPG | wc -l
# Expected: ~200-400 frames per 10-minute flight

# 3. Update manifest CSV with checksums and flight metadata

# 4. Keep 3 copies until processing verified:
#    - Laptop (working copy)
#    - Backup drive (safety)
#    - Drone storage (until confirmed good)
```

### Manifest Template

Create `field_manifest.csv`:

```csv
Flight_ID,Date,Time_UTC,Sensor,Altitude_m,Speed_ms,Area_ID,Weather,File_Count,Total_MB,SHA256_File,Notes
FL001,2025-10-20,12:30,LiDAR,35,4,Colony_North,Clear_Calm,45,2340,FL001_checksums.txt,Good_coverage
FL002,2025-10-20,13:15,LiDAR,35,4,Colony_South,Clear_Lt_Wind,38,1980,FL002_checksums.txt,Completed
FL003,2025-10-21,10:45,Thermal,18,3,Colony_North,Overcast_Calm,234,152,FL003_checksums.txt,Doc_only
```

**Why This Matters**: Your thermal investigation revealed the value of provenance tracking. If processing fails later, you'll know which field conditions to investigate.

---

## 5. In-Field Quality Control Gates

### LiDAR QC (Run Daily - CRITICAL)

After first flight of the day:

```bash
# Quick validation on first tile
python scripts/run_lidar_hag.py \
  --tiles data/intake/field_day1_tile1.las \
  --out-dir data/qc/day1 \
  --plots --rollup

# Review outputs:
# 1. Point density from logs
# 2. Detection count from rollup_counts.json
# 3. QC plots: hillshade + detections overlay
```

**Stop-Gates** (adjust parameters if triggered):

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Point density | <30 pts/m² | ⚠️ Fly lower (25-30m) or slower (2-3 m/s) |
| Point density | 30-50 pts/m² | ⚠️ Consider lowering altitude to 25-30m |
| Point density | >50 pts/m² | ✅ Continue with current parameters |
| Zero detections | In known colony | ⚠️ Check HAG thresholds, verify terrain |
| GPS errors | >1m horizontal | 🛑 **STOP** - Wait for RTK fix |

### Thermal QC (If Collected)

```bash
# Check thermal frame integrity
ls -lh data/thermal/*.JPG | head -n 5

# Verify:
# - File sizes ~650KB (R-JPEG with embedded thermal data)
# - Sequential naming (no gaps)
# - GPS coordinates present:
exiftool data/thermal/DJI_*_0001_T.JPG | grep -E "GPS|Altitude"
```

**No thermal processing needed in field** - just verify data integrity for later investigation.

---

## 6. Deployment Contingency Plans

### Weather Contingencies

#### High Winds (>20 km/h sustained)
**Risk**: GPS accuracy degrades, point cloud alignment issues  
**Action**: Delay flight until winds <15 km/h

#### Rain/Heavy Fog
**Risk**: Reduced LiDAR returns, wet electronics  
**Action**: Wait for clearing. LiDAR can fly in light overcast.

#### Limited Weather Windows
**Priority**:
1. Small test area LiDAR (verify parameters)
2. Primary colony coverage LiDAR
3. Additional areas if time permits
4. Thermal documentation (lowest priority)

### Equipment Failures

| Failure | Severity | Response |
|---------|----------|----------|
| **LiDAR failure** | 🔴 CRITICAL | Stop. Troubleshoot or abort mission. |
| **GPS/RTK failure** | 🔴 CRITICAL | Do not fly - accuracy will be unusable. |
| **Thermal camera failure** | 🟡 MINOR | Continue with LiDAR only. |
| **Drone battery issues** | 🟠 MODERATE | Reduce coverage area, focus on priority zones. |

### Processing Failures (Detected in Daily QC)

#### Point Density Too Low (<30 pts/m²)
**Cause**: Altitude too high, speed too fast, or sensor settings  
**Fix**: Re-fly area at lower altitude (25-30m) or slower speed (2-3 m/s)

#### Zero Detections Despite Good Density
**Cause**: HAG thresholds wrong for terrain, or penguins not in area  
**Fix**: 
1. Check QC hillshade - does terrain look reasonable?
2. Adjust `--hag-min` / `--hag-max` parameters
3. Verify flying over actual colony (GPS check)

#### Large GPS Offsets Between Passes
**Cause**: RTK not fixed, multipath interference  
**Fix**: Wait for RTK fix before continuing, avoid flying near cliffs/buildings

---

## 7. What NOT to Do (Lessons from Investigation)

### ❌ Don't Over-Promise Thermal Detection Capabilities

**Investigation findings**: 0.047σ SNR presents significant detection challenges  
**Recommended messaging**: "LiDAR provides reliable penguin detections. Thermal data collected for documentation and future research applications."

### ❌ Don't Fly Too High to "Cover More Area Faster"

**Why**: Point density drops with altitude²  
**Example**: 50m altitude = 50% point density vs. 35m = missed penguins

### ❌ Don't Skip the Test Area

**Why**: Parameter problems discovered after full survey = wasted time/batteries  
**Always**: Process first tile before committing to full coverage

### ❌ Don't Delete Data in Field

**Why**: "Looks good" ≠ "processes correctly"  
**Keep**: Original data on drone + laptop + backup until processing verified at home

### ❌ Don't Mix LiDAR and Thermal in Same Flight

**Why**: Compromise parameters for both, heavier payload, single point of failure  
**Do**: Separate flights with optimized parameters for each

### ❌ Don't Ignore Stop-Gates

**If point density <30 pts/m²**: Stop, adjust, re-fly  
**If GPS errors >1m**: Wait for fix, don't continue  
**Why**: Bad data is worse than no data - can't be fixed in post-processing

---

## 8. Field Notes Template

### Daily Flight Log (CSV Format)

```csv
Flight_ID,Date,Time_UTC,Sensor,Altitude_m,Speed_ms,Area_ID,Weather,Temp_C,Wind_kmh,File_Count,Coverage_Ha,Batteries_Used,Notes,Issues
FL001,2025-10-20,12:30,LiDAR,35,4,Colony_North,Clear,8,5,45,2.5,3,Good_coverage,None
FL002,2025-10-20,13:15,LiDAR,35,4,Colony_South,Clear,9,8,38,2.1,3,Complete,Light_wind
FL003,2025-10-21,10:45,Thermal,18,3,Colony_North,Overcast,6,3,234,1.2,2,Doc_only,None
```

### Penguin Behavior Observations

```
Date: 2025-10-20
Time: 0800-1000 local
Weather: Clear, 8°C, light breeze

Observations:
- Most penguins at nests (incubation period)
- ~30% walking between nests and shore
- Colony density appears high in north section
- Minimal disturbance from drone at 35m altitude

Notes for processing:
- Expect higher detection in north section
- May have some motion blur in thermal (walking birds)
- LiDAR should capture stationary birds well
```

**Why**: Contextual observations help explain detection patterns during processing.

---

## 9. Success Criteria

### Minimum Viable Deployment (MVD)

**Must Achieve**:
- ✅ LiDAR coverage of penguin colony at 30-40m AGL
- ✅ Point density >50 pts/m² across survey area
- ✅ GPS coordinates logged for all flights
- ✅ Three copies of data (laptop + backup + drone)
- ✅ Checksums and manifest for all files
- ✅ Field notes documenting conditions and observations
- ✅ At least one test area processed in-field (QC verified)

**Nice to Have**:
- 📸 Thermal imagery (documentation purposes)
- 📸 RGB photos (visual context)
- 📸 Ground control points (if GPS accuracy uncertain)
- 📸 Multiple altitude tests (20m, 30m, 40m comparison)

### What Success Looks Like

**In Field**:
- All flights logged with metadata
- Daily QC shows good point density
- Test area shows reasonable detection counts
- No major equipment failures
- Data safely backed up with checksums

**After Return** (Processing Deliverables):
```
deliverables/
├── lidar_detections.gpkg          # Penguin locations (GeoJSON/GPKG)
├── rollup_counts.json             # Summary statistics
├── qc_panels/                     # Hillshade + detections overlays
│   ├── colony_north_overview.png
│   ├── colony_south_overview.png
│   └── detection_density_map.png
├── thermal_investigation.pdf      # Why fusion not viable
└── processing_documentation.md    # Reproducibility guide
```

**This constitutes successful deployment** - proven LiDAR methodology with thermal investigation documented as important negative finding.

---

## 10. Quick Reference Field Card

**Print this section, laminate, attach to equipment case:**

```
╔══════════════════════════════════════════════════════════════╗
║          ARGENTINA PENGUIN DEPLOYMENT QUICK REF             ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  PRIMARY MISSION: LiDAR Coverage                            ║
║  ✓ Altitude: 30-40m AGL                                     ║
║  ✓ Speed: 3-5 m/s                                           ║
║  ✓ Overlap: 50%+ between passes                             ║
║  ✓ Target density: >50 pts/m²                               ║
║  ✓ Time: Anytime, avoid high winds                          ║
║                                                              ║
║  OPTIONAL: Thermal Data Collection                          ║
║  • Altitude: 15-20m AGL (LOWER than LiDAR)                  ║
║  • Time: Early morning (first light)                        ║
║  • Purpose: Documentation and research applications         ║
║                                                              ║
║  AFTER EACH FLIGHT:                                         ║
║  1. Copy data: drone → laptop → backup                      ║
║  2. Calculate SHA256 checksums                              ║
║  3. Log to manifest CSV                                     ║
║  4. Keep 3 copies until verified                            ║
║                                                              ║
║  DAILY QC (CRITICAL):                                       ║
║  • Process first tile with run_lidar_hag.py                 ║
║  • Check point density in logs                              ║
║  • Verify detections look reasonable                        ║
║  • Adjust parameters if needed before full survey           ║
║                                                              ║
║  STOP-GATES:                                                ║
║  🛑 Point density <30 pts/m²: Fly lower/slower              ║
║  🛑 GPS errors >1m: Wait for RTK fix                        ║
║  🛑 High winds >20 km/h: Delay flight                       ║
║                                                              ║
║  SUCCESS = LiDAR coverage + good metadata + backups         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 11. Pre-Departure Checklist

### Equipment Verification

```
□ GeoCue 515 LiDAR tested and calibrated
□ DJI M350 RTK drone fully charged
□ H30T thermal camera (optional) tested
□ RTK base station (if using) tested
□ Spare batteries charged (minimum 6-8)
□ Memory cards formatted (minimum 256GB)
□ Backup hard drive ready (1TB+)
□ Laptop with processing scripts tested
□ Laminated field reference card
```

### Software Verification

```
□ Python environment activated
□ Test run of scripts/run_lidar_hag.py successful
□ pdal, laspy, opencv libraries confirmed working
□ exiftool installed for thermal metadata
□ rsync or backup software tested
□ Field manifest CSV template ready
```

### Documentation

```
□ This field deployment guide (printed + digital)
□ Equipment manuals (digital backup)
□ Processing scripts backed up
□ Emergency contact information
□ Drone registration/permits for Argentina
```

---

## 12. Emergency Contacts & Resources

### Technical Support (From Home)

**Data Processing Issues**:
- Test first with: `python scripts/run_lidar_hag.py --tiles <file> --out-dir test --plots`
- Check logs in `test/provenance_lidar.json` for errors
- Review QC plots in `test/lidar_hag_plots/` for visual verification

**GPS/RTK Issues**:
- Verify RTK fix status before each flight
- If no fix: Wait, relocate base station, check for obstructions
- Acceptable: RTK Fixed mode (horizontal <10cm)
- Unacceptable: RTK Float or GPS-only (>50cm error)

### In-Field Troubleshooting

**LiDAR shows zero points**:
1. Check sensor power connection
2. Verify data logging enabled in drone settings
3. Test flight over area with known terrain variation
4. Review .las file with `pdal info <file>` - should show point count

**Thermal images corrupt**:
1. Verify memory card not full
2. Check file sizes (~650KB expected)
3. Test opening with DJI Thermal Analysis Tool (if available)
4. If persistent: Skip thermal, focus on LiDAR

---

## 13. Data Processing Timeline (Post-Deployment)

### Week 1: Data Ingest and QC

```bash
# 1. Harvest data from field drives to data/intake/
python scripts/harvest_golden_data.py --source /field_drive/argentina_2025/

# 2. Validate checksums against field manifest
shasum -c field_checksums.txt

# 3. Run full LiDAR processing
make lidar
# Processes all tiles, generates detections + QC panels

# 4. Generate delivery metrics
python scripts/generate_delivery_metrics.py
```

### Week 2: Analysis and Deliverables

```bash
# 1. Create penguin detection maps
# Output: GeoJSON, GPKG, shapefiles

# 2. Generate QC report with:
#    - Detection counts by area
#    - Point density heatmaps
#    - Hillshade overlays
#    - Confidence metrics

# 3. Thermal investigation summary
#    - Document why fusion not viable
#    - Include representative frames
#    - Reference thermal investigation report

# 4. Package deliverables for client
```

**Expected timeline**: 2-3 weeks from field return to final deliverables.

---

## 14. Thermal Characterization Study Summary

### Key Findings (docs/THERMAL_INVESTIGATION_FINAL.md)

**Test Conditions**: Puerto Madryn, Argentina (42°56'S) - Spring, coastal environment (Magellanic penguin colony)

**Thermal Measurements**:
- Magellanic penguin surface temperature: −5.56°C ± 2.21°C
- Ground background temperature: −5.69°C ± 2.91°C
- Thermal contrast: 0.14°C
- Scene standard deviation (σ): 2.91°C
- Signal-to-noise ratio: **0.047σ**

**Detection Performance Analysis** (at 0.5σ threshold):
- True Positives: 21 / 26 ground truth (Recall = 80.8%)
- False Positives: 925 (Precision = 2.2%)
- F1 Score: 0.043

**Biological Context**:
Magellanic penguins evolved exceptional insulation for survival in harsh coastal environments. Multi-layer feather system and subcutaneous fat effectively regulate internal temperature (38°C) while minimizing surface heat loss. This thermal regulation strategy results in surface temperatures approaching ambient conditions.

**Implications**:
- Test conditions (Patagonian spring, coastal) represent relatively favorable thermal imaging scenarios
- Colder environments (Antarctic winter) would present additional detection challenges
- Current commercial thermal camera technology shows limited applicability for individual penguin detection under these biological and environmental constraints

**Proven Alternative**: LiDAR height-above-ground detection successfully identifies penguin-sized objects (879 detections in test area with reproducible pipeline results).

---

## 15. Final Recommendations

### For This Deployment

**Recommended Priorities**:
- ✅ Focus on high-quality LiDAR coverage (validated methodology)
- ✅ Fly test area first, verify parameters with daily QC
- ✅ Maintain rigorous data management (3 copies + checksums)
- ✅ Document field conditions and penguin behavior observations
- ✅ Collect thermal data if operational constraints allow (research value)

**Risk Management**:
- ⚠️ Set appropriate expectations for thermal detection capabilities with stakeholders
- ⚠️ Allocate sufficient time for test area validation before full coverage
- ⚠️ Maintain adequate point density (avoid flying too high for efficiency)
- ⚠️ Preserve all raw data until processing verification complete
- ⚠️ Optimize flight parameters for primary sensor (LiDAR) first

### For Future Deployments

**LiDAR-Based Detection** (Primary Recommendation):
- Validated methodology with production-ready pipeline
- Consistent performance across terrain conditions
- Independent of environmental thermal conditions
- Established processing workflow and quality metrics

**Thermal Research Opportunities**:
- **Pre-deployment validation**: Zoo or controlled environment testing before field commitment
- **Advanced equipment**: Cooled MWIR cameras may improve contrast detection capabilities
- **Calibration infrastructure**: In-scene reference targets (heated/cooled) for radiometric validation
- **Appropriate framing**: Position as research investigation with exploratory objectives
- **Resource allocation**: Plan 2-3× development time vs. established LiDAR approach
- **Environmental optimization**: Target conditions with maximum thermal contrast (behavioral patterns, weather, time of day)

### Success Definition

**Deployment objectives achieved when**:
- High-quality LiDAR data collected with comprehensive metadata documentation
- Point density targets (>50 pts/m²) met across survey area
- Data management protocol followed (3-copy backup with checksums)
- Processing pipeline produces validated penguin detection maps
- Thermal data collected (if operationally feasible) with field condition documentation

**Scientific Value**: This deployment contributes validated LiDAR detection methodology and empirical thermal characterization data. Both datasets advance understanding of multi-sensor wildlife monitoring approaches in challenging environmental conditions.

---

## Document Version Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-14 | Richard | Initial field deployment guide |

**Last Updated**: 2025-10-14  
**Next Review**: Post-deployment (2025-11-30)

---

## References

1. `docs/THERMAL_INVESTIGATION_FINAL.md` - Thermal signal analysis
2. `docs/equipment.md` - GeoCue 515 LiDAR and DJI H30T specifications
3. `docs/FIELD_SOP.md` - Standard operating procedures
4. `scripts/run_lidar_hag.py` - LiDAR processing pipeline
5. `tests/test_golden_aoi.py` - Validation test suite (12 tests)
6. `data/legacy_ro/thermal-lidar-fusion/research/` - Multi-sensor deployment research
7. External review: `docs/THERMAL_INVESTIGATION_REVIEW.md` - Peer review findings

---

**END OF FIELD DEPLOYMENT GUIDE**

*Print this document and laminate Section 10 (Quick Reference Field Card) for field use.*

