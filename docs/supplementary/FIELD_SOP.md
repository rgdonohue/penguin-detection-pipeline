# Field Standard Operating Procedure

**Penguin Detection Pipeline - Data Collection Guide**

Version 1.0 | Last Updated: 2025-10-14 | Status: PRE-DEPLOYMENT REVIEW REQUIRED

---

## ⚠️ CRITICAL: Read Before Deployment

**This SOP assumes LiDAR-only deployment.** If thermal imaging is included, additional sections must be completed based on zoo test results. See "Thermal Imaging Protocol (CONDITIONAL)" section below.

**Pre-Flight Checklist Mandatory:** Do not depart without completing all items in Section 8.

---

## 1. Equipment Specifications

### 1.1 DJI M350 RTK Drone

**Role:** Primary platform for DJI H30T thermal sensor

**Key Specifications:**
- Max flight time: 55 min (no payload), ~40 min (with H30T)
- Wind resistance: 12 m/s (max safe operating)
- Positioning: RTK/PPK capable (±2-5cm horizontal accuracy with RTK)
- Operating temperature: -20°C to 50°C
- IP rating: IP55 (weather resistant)

**Pre-Flight:**
- RTK/PPK: **MUST BE ENABLED** for all survey flights
- Battery: Charge to 100%, warm batteries if <5°C ambient
- Firmware: Verify latest stable version before departure
- Controller sync: Ensure time synchronization with drone

### 1.2 GeoCue 515 LiDAR Sensor

**Role:** Primary penguin detection data source (production-ready pipeline)

**Key Specifications:**
- Pulse rate: 100-500 kHz (adjustable)
- Range: 50-400m (varies with surface reflectance)
- Point density: **Target 150-300 pts/m² at flight altitude**
- Accuracy: ±2-5cm vertical (with RTK/PPK)
- Field of view: 70° (perpendicular to flight direction)
- Data output: LAS/LAZ format

**Critical Settings (GeoCue Software):**
- **RTK/PPK: ENABLED** (required for <5cm accuracy)
- **Point density target: 150-300 pts/m²**
- Cross-line pattern: Required (see Section 3.2)
- Altitude: 50-80m AGL (see Section 3.3)
- Overlap: 30% minimum (50% recommended)

**Pre-Flight:**
- Warm-up: **10 minutes minimum** before first scan
- Calibration: Verify boresight alignment (factory calibration valid 6 months)
- Storage: Verify 500GB+ free space on recording device
- Power: Verify full charge, check voltage during warm-up

### 1.3 DJI H30T Thermal Sensor (CONDITIONAL)

**Role:** Experimental validation only (see Section 2 for deployment decision)

**Key Specifications:**
- Thermal resolution: 640×512 pixels
- DFOV: 40.6° (diagonal field of view)
- Temperature range: -40°C to +150°C
- Accuracy: ±2°C or ±2% (whichever greater)
- Data format: R-JPEG (16-bit radiometric + 8-bit preview)
- Frame rate: 30 Hz (adjustable to 8.33 Hz for slower flights)

**Critical Settings (IF DEPLOYED - See Section 2):**
- **Radiometric mode: ON** (16-bit temperature data)
- **Emissivity: 0.98** (biological targets, NOT default 1.00)
- **Gain: Fixed** (disable auto-gain)
- **Overlap: 70% forward, 60% side** (higher than LiDAR)
- **Gimbal: Nadir ± 20° max** (avoid oblique angles)

**Pre-Flight (IF DEPLOYED):**
- Warm-up: **5-10 minutes** before first capture
- Flat-field cal: Point at uniform sky for 30 seconds
- Settings verification: Export one test frame, check EXIF metadata
- Time sync: Verify camera clock matches controller

### 1.4 Skyfront Perimeter 8 Drone

**Role:** [CLARIFICATION NEEDED - Not specified in current PRD]

**Action Required:** Document role and specifications before deployment.

Possible roles:
- Extended endurance missions (8+ hour flight time)
- Backup platform if M350 unavailable
- Large-area surveys requiring long-duration flights

**Status:** ⚠️ INCOMPLETE - Must be specified before field use

---

## 2. Thermal Imaging Decision (REQUIRED BEFORE DEPLOYMENT)

### ⚠️ DEPLOYMENT DECISION REQUIRED

**Background:** Recent analysis shows thermal signal too weak for Magellanic penguin detection in Patagonian coastal conditions (0.047σ contrast, where σ = scene standard deviation). Test data from warmer spring environment (Puerto Madryn, Argentina) - Antarctic conditions would present even greater thermal detection challenges. See `docs/THERMAL_INVESTIGATION_FINAL.md` for full analysis.

**Choose ONE option before deployment:**

### Option A: LiDAR-Only Deployment (RECOMMENDED) ✅

**When to choose:**
- 1-week timeline is firm (no time for zoo testing)
- Team wants guaranteed working deliverable
- Risk tolerance is low

**Actions:**
- [ ] Skip all thermal setup and sections
- [ ] Remove H30T from M350 (reduces weight, extends flight time)
- [ ] Focus pilot training on LiDAR-only operations
- [ ] Update this SOP to remove thermal sections

**Advantages:**
- Proven pipeline (862 detections, reproducible)
- Simpler field operations
- Lower data volume and processing time
- Extended flight time without thermal payload

**Disadvantages:**
- No thermal validation data collected
- Missed opportunity for dual-sensor research

### Option B: Thermal With Modified Settings (REQUIRES ZOO TEST)

**When to choose:**
- Zoo test facility available
- Can delay Argentina departure by 3-5 days
- Willing to accept 50% chance thermal data won't be usable

**Actions:**
- [ ] Schedule zoo test flight (2-day window before Argentina)
- [ ] Test settings: emissivity 0.98, fixed gain, midday timing
- [ ] Process zoo data immediately (4-hour turnaround)
- [ ] Go/no-go decision based on contrast >1.0σ
- [ ] If no-go: Remove H30T and switch to Option A

**Advantages:**
- If successful, validates dual-sensor approach
- Maximizes scientific value of field campaign

**Disadvantages:**
- Adds 3-5 days to timeline
- Risk of unusable thermal data
- Increased field complexity

### Option C: Dual-Mode Collection (HIGHEST RISK)

**When to choose:**
- Thermal data valuable even if detection fails
- Team has capacity for dual-sensor operations
- Storage and processing bandwidth available

**Actions:**
- [ ] Deploy both LiDAR and thermal
- [ ] Process LiDAR for penguin counts (primary deliverable)
- [ ] Collect thermal as research data only
- [ ] Do NOT promise thermal-based detection counts

**Advantages:**
- Preserves thermal data for future analysis
- Maintains research optionality

**Disadvantages:**
- Increased field complexity
- 2× data volume and processing time
- Thermal may be unusable (known risk)

### DECISION CHECKPOINT

**Decision made:** [ ] Option A  [ ] Option B  [ ] Option C

**Decision maker:** _________________ **Date:** _________

**If Option B or C selected, complete thermal sections below.**
**If Option A selected, skip to Section 3 (LiDAR Protocol).**

---

## 3. LiDAR Data Collection Protocol

### 3.1 Pre-Flight Setup

**Equipment Check (10 minutes):**
1. Power on GeoCue 515, wait for green status LED
2. **Verify RTK/PPK mode enabled** (check software display)
3. Warm-up timer: 10 minutes (mandatory for stability)
4. Storage check: ≥500GB free space
5. Ground control point (GCP) placement if available

**Software Configuration:**
```
Target point density: 200 pts/m²
Scan angle: 70° FOV (perpendicular to flight)
Altitude: 60m AGL (initial, adjust based on terrain)
Speed: 4 m/s (adjust if needed to maintain point density)
Overlap: 50% (minimum 30%)
File naming: [SITE]_[DATE]_[TIME]_[LINE#].laz
```

**Safety Verification:**
- [ ] RTK/PPK status: GREEN
- [ ] Warm-up complete (10 min elapsed)
- [ ] Storage >500GB available
- [ ] Weather: Wind <10 m/s, no precipitation
- [ ] Airspace: Clearances obtained

### 3.2 Flight Pattern: Cross-Line Survey

**Pattern Type:** Perpendicular grid (primary + cross-lines)

**Rationale:** Cross-lines improve accuracy by:
- Reducing systematic errors from single-direction bias
- Providing redundant coverage for QC
- Improving ground point classification

**Execution:**
1. Primary lines: Fly N-S or E-W (choose based on wind)
2. Overlap: 50% between adjacent lines
3. Cross-lines: Fly perpendicular (E-W or N-S)
4. Cross-line spacing: Every 3-5 primary lines
5. Altitude: Maintain constant 60m AGL (adjust for terrain)

**Visual Diagram:**
```
Primary Lines (N-S):       Cross-Lines (E-W):
|||||||||||                ═══════
|||||||||||                ═══════
|||||||||||                ═══════
|||||||||||
|||||||||||
```

**Flight Parameters:**
- Speed: 4 m/s (adjust to maintain 150-300 pts/m²)
- Altitude: 50-80m AGL (start at 60m, adjust based on point density check)
- Gimbal: LiDAR perpendicular to flight direction
- Turn radius: Wide arcs (minimize acceleration)

### 3.3 Altitude vs. Point Density Trade-Off

| Altitude (AGL) | Point Density | Coverage Rate | When to Use |
|----------------|---------------|---------------|-------------|
| 50m | 250-350 pts/m² | Slower | High-detail areas, rough terrain |
| 60m | 180-250 pts/m² | ✅ RECOMMENDED | Standard surveys |
| 80m | 120-180 pts/m² | Faster | Preliminary surveys, large areas |

**Point density check workflow:**
1. Fly one test line at 60m AGL
2. Download and check density: `pdal info --stats test_line.laz`
3. If density <150 pts/m²: Decrease altitude or slow speed
4. If density >300 pts/m²: Can increase altitude to speed up survey

### 3.4 In-Flight Monitoring

**Pilot monitors:**
- Altitude hold accuracy (±2m)
- Speed consistency (±0.5 m/s)
- Wind compensation (cross-track error <3m)
- Battery level (land with ≥20% remaining)

**Sensor operator monitors:**
- RTK/PPK status: Must stay GREEN
- Point density estimate (if real-time display available)
- Storage space remaining
- File creation per line (verify new file each transect)

**Abort conditions:**
- RTK/PPK drops to FLOAT or FIXED (only RTK acceptable)
- Wind exceeds 10 m/s
- Battery <25% and >10 min from landing
- Storage <100GB remaining

### 3.5 Post-Flight QC (Per Battery)

**Immediate checks (5 minutes between batteries):**
1. File count: One .laz per line flown?
2. File sizes: Reasonable (~100MB-1GB per line)?
3. Quick-look processing (if time permits):
   ```bash
   # Optional: Process one tile for quick QC
   python scripts/run_lidar_hag.py \
       --data-root field_data/raw/today/ \
       --out quicklook/results.json \
       --plots
   ```

**End-of-day QC (30-60 minutes):**
1. **Backup immediately**: Copy all .laz files to TWO separate drives
2. Verify checksums: `shasum -a 256 *.laz > checksums.txt`
3. Process one representative tile (10-15 min):
   ```bash
   python scripts/run_lidar_hag.py \
       --data-root field_data/site_A/day_1/ \
       --out qc/day_1_counts.json \
       --plots --emit-geojson
   ```
4. Visual inspection: Open QC plots, verify reasonable detection counts
5. Coverage map: Check for gaps in survey area
6. Decide: Re-fly gaps tomorrow, or continue to next site?

---

## 4. Thermal Imaging Protocol (CONDITIONAL)

**⚠️ ONLY FOLLOW IF OPTION B OR C SELECTED IN SECTION 2**

### 4.1 When to Deploy Thermal

**Deploy thermal only if:**
- [ ] Zoo test showed >1.0σ contrast improvement (Option B), OR
- [ ] Collecting as research data with no detection promise (Option C)
- [ ] Team trained on dual-sensor operations
- [ ] Processing capacity available for 2× data volume

**Skip thermal if:**
- Option A selected (LiDAR-only)
- Zoo test failed (<1.0σ contrast)
- Timeline or capacity insufficient

### 4.2 Thermal Camera Settings (DJI H30T)

**CRITICAL: Verify these settings before every flight**

```
Mode: Radiometric (16-bit)
Emissivity: 0.98 (NOT default 1.00)
Gain: Fixed (disable auto-gain)
Shutter: Auto (for varying light conditions)
Frame rate: 8.33 Hz (for 4 m/s flight speed)
Color palette: Ironbow (for human QC; data is 16-bit regardless)
```

**How to verify:**
1. Capture one test frame before survey
2. Export EXIF metadata:
   ```bash
   exiftool -G1 -a -s test_frame.JPG | grep -i "emissivity\|gain"
   ```
3. Confirm: `Emissivity: 0.98` and `Gain: Fixed`

### 4.3 Thermal Flight Parameters

**Overlap requirements (HIGHER than LiDAR):**
- Forward overlap: 70%
- Side overlap: 60%

**Why higher?** Thermal has no range data; needs photogrammetry-style overlap for orthorectification.

**Flight pattern:**
```
Altitude: Same as LiDAR (50-80m AGL)
Speed: 4 m/s (matches LiDAR)
Gimbal: Nadir ± 20° max (avoid oblique)
Flight lines: Follow LiDAR pattern (simplifies co-registration)
```

**Timing considerations:**
- Avoid early morning (thermal equilibrium after sunrise)
- Midday preferred (maximum solar contrast)
- Avoid late evening (penguins may be warmer after day activity)

### 4.4 Thermal-Specific Pre-Flight

**Warm-up (5-10 minutes):**
1. Power on H30T
2. Point at uniform sky for 30 seconds (flat-field calibration)
3. Wait 5 minutes for thermal stabilization
4. Capture test frame, verify settings (emissivity, gain)

**Do NOT:**
- Point at sun during warm-up (sensor damage risk)
- Fly immediately after power-on (thermal drift)
- Change emissivity mid-survey (consistency critical)

### 4.5 Thermal Post-Flight QC

**Immediate checks:**
1. Frame count: `exiftool -CreateDate -csv *.JPG | wc -l`
2. Verify radiometric data present:
   ```bash
   # Should show ThermalData blob size = 655360 bytes
   exiftool -b -ThermalData test_frame.JPG | wc -c
   ```
3. Export poses for processing:
   ```bash
   exiftool -n -csv -G1 -a -s -ee \
     -XMP:CreateDate -XMP-drone-dji:GPSLatitude \
     -XMP-drone-dji:GPSLongitude -XMP-drone-dji:AbsoluteAltitude \
     *.JPG > poses.csv
   ```

**End-of-day QC:**
1. Process one test frame:
   ```bash
   python scripts/run_thermal_ortho.py ortho-one \
       --image test_frame.JPG \
       --poses poses.csv \
       --dsm ../lidar/dsm.tif \
       --out qc/test_ortho.tif \
       --radiometric --snap-grid
   ```
2. Visual check: Open in QGIS, verify alignment with DSM
3. Temperature range check: Should be reasonable for environment

---

## 5. Data Management

### 5.1 File Naming Convention

**LiDAR:**
```
[SITE]_[YYYYMMDD]_[HHMMSS]_[LINE]_lidar.laz
Example: PunTombo_20251020_143022_L001_lidar.laz
```

**Thermal (if deployed):**
```
[SITE]_[YYYYMMDD]_[HHMMSS]_[FRAME]_T.JPG
Example: PunTombo_20251020_143022_0001_T.JPG
```

**Processed outputs:**
```
[SITE]_[YYYYMMDD]_detections.json
[SITE]_[YYYYMMDD]_detections.geojson
[SITE]_[YYYYMMDD]_qc_plots.png
```

### 5.2 Storage and Backup Strategy

**Field storage requirements:**
- Primary: 1TB+ ruggedized SSD (Samsung T7, SanDisk Extreme Pro)
- Backup 1: 1TB+ second SSD (different brand/model)
- Backup 2: 1TB+ third drive (left at base camp)

**Backup schedule:**
```
End of each flight day:
1. Copy all raw data → Backup 1 (immediate)
2. Verify checksums match
3. Copy all raw data → Backup 2 (end of day)
4. Keep Backup 2 at separate location (base camp)
```

**Directory structure:**
```
field_data/
├── raw/
│   ├── site_A/
│   │   ├── day_1/
│   │   │   ├── lidar/  (*.laz files)
│   │   │   └── thermal/ (*.JPG files, poses.csv)
│   │   └── day_2/
│   └── site_B/
├── processed/
│   └── site_A/
│       └── day_1/
│           ├── detections.json
│           └── qc_plots/
└── metadata/
    ├── flight_logs/
    └── checksums/
```

### 5.3 Data Volume Estimates

**Per 100 hectares:**
- LiDAR: 20-40 GB raw (.laz)
- Thermal (if deployed): 5-10 GB (R-JPEG)
- Processed outputs: 500 MB-1 GB
- **Total per site: 25-50 GB**

**Typical expedition (5 sites, 500 ha total):**
- Total raw data: 100-250 GB
- With backups: 300-750 GB (3× copies)
- Processing outputs: 2-5 GB

**Recommendation:** Bring 2TB+ total capacity (3× 1TB drives minimum)

---

## 6. Field Processing Workflow

### 6.1 Daily Processing (Optional but Recommended)

**Goal:** Verify data quality before leaving survey area

**Time required:** 30-60 minutes per site

**Workflow:**
```bash
# 1. Activate environment
source .venv/bin/activate

# 2. Process LiDAR for detection counts
python scripts/run_lidar_hag.py \
    --data-root field_data/raw/site_A/day_1/lidar/ \
    --out processed/site_A_day1_detections.json \
    --plots --emit-geojson

# 3. Quick QC check
jq '.total_count' processed/site_A_day1_detections.json
open processed/lidar_hag_plots/*.png

# 4. Coverage assessment
# Load GeoJSON in QGIS, check for gaps
```

**QC Criteria:**
- Detection counts reasonable for site (order of magnitude check)
- QC plots show clear detections (not noise)
- No obvious gaps in coverage
- Processing completes without errors

**If QC fails:**
- Identify problem areas (gaps, poor quality)
- Plan re-flight for next day
- Adjust parameters if systematic issue (altitude, overlap)

### 6.2 Field Computing Requirements

**Minimum:**
- Laptop: 16GB RAM, 50GB free disk, multi-core CPU
- OS: macOS, Linux, or Windows with WSL2
- Software: Python 3.11+, dependencies pre-installed
- Peripherals: Mouse, external display (for QC review)

**Recommended:**
- Laptop: 32GB RAM, 256GB free disk, 6+ core CPU
- External SSD: For processing (faster than internal HDD)
- Portable battery: For field processing

**Pre-departure setup:**
```bash
# Test processing on sample data
cd penguins-4.0
source .venv/bin/activate
make validate
make test-lidar

# Verify all dependencies installed
pytest tests/test_golden_aoi.py -v
```

---

## 7. Quality Control Gates

### 7.1 Level 1 QC: In-Flight (Real-Time)

**Pilot/operator checks:**
- [ ] RTK/PPK status GREEN (LiDAR)
- [ ] Altitude hold ±2m
- [ ] Speed consistency ±0.5 m/s
- [ ] File creation per transect

**Action if fail:** Abort mission, troubleshoot on ground

### 7.2 Level 2 QC: Post-Flight (5 Minutes)

**Immediate checks:**
- [ ] File count matches number of lines flown
- [ ] File sizes reasonable (not 0 bytes or unexpectedly small)
- [ ] No error messages in sensor logs

**Action if fail:** Note issues, plan re-flight before leaving site

### 7.3 Level 3 QC: Daily Processing (60 Minutes)

**Processing checks:**
- [ ] Detection counts within expected range (e.g., 100-2000 per site)
- [ ] QC plots show clear detections (not all noise or all hits)
- [ ] Coverage map shows no gaps
- [ ] Processing logs show no warnings/errors

**Action if fail:**
- Minor: Note for post-processing investigation
- Major (data unusable): Re-flight required before leaving site

### 7.4 Level 4 QC: Post-Expedition (Full Analysis)

**Back at lab:**
- Full tile processing with optimized parameters
- Cross-validation with known colony counts (if available)
- Accuracy assessment with manual verification
- Report generation and delivery

---

## 8. Pre-Deployment Checklist

### 8.1 Critical (Must Complete Before Departure)

**Pipeline Validation:**
- [ ] `make validate` passes without errors
- [ ] Test processing on sample data completed
- [ ] Team trained on scripts and commands
- [ ] Field laptop has environment pre-installed

**Thermal Decision:**
- [ ] Thermal deployment decision made (Option A/B/C selected)
- [ ] If Option B: Zoo test completed, results documented
- [ ] If Option C or thermal excluded: H30T removed from equipment list
- [ ] SOP updated to match decision

**Equipment:**
- [ ] All hardware inventoried and functional
- [ ] Batteries charged (drone + laptop + portable power)
- [ ] Storage drives formatted and tested (3× 1TB+ drives)
- [ ] RTK/PPK enabled and tested (GeoCue 515)
- [ ] Firmware updated to latest stable versions

**Documentation:**
- [ ] This SOP printed and reviewed by all team members
- [ ] RUNBOOK.md available offline (printed or PDF)
- [ ] Emergency contact list (tech support, data recovery)
- [ ] Backup plan documented (what if primary equipment fails?)

**Logistics:**
- [ ] Storage capacity confirmed (300-750 GB total)
- [ ] Backup drives labeled and assigned
- [ ] File naming convention agreed upon
- [ ] Data transfer process tested

### 8.2 Recommended (Should Complete)

- [ ] README.md quick-start practiced by field team
- [ ] Sample processing workflow demonstrated
- [ ] QC criteria reviewed (what's "reasonable" detection count?)
- [ ] Rollback procedure tested (last known-good data)
- [ ] Weather monitoring plan established

### 8.3 Nice-to-Have (Optional)

- [ ] Docker image built (alternative to venv)
- [ ] Automated backup scripts created
- [ ] Real-time cloud sync configured (if connectivity available)
- [ ] Client communication template prepared

---

## 9. Emergency Procedures

### 9.1 Equipment Failure

**Primary LiDAR sensor fails:**
1. Switch to backup drone/sensor if available
2. If no backup: Continue with thermal only (if deployed)
3. Contact vendor support (GeoCue: [CONTACT INFO NEEDED])

**M350 drone failure:**
1. Switch to Skyfront Perimeter 8 if compatible
2. If no alternative: Mission abort, return to base

**Data storage failure:**
1. Immediately copy to remaining backup drives
2. Do NOT continue flying until backup restored
3. Verify checksums before resuming

### 9.2 Data Loss or Corruption

**Discovered during QC:**
1. Check all 3 backup drives for uncorrupted copy
2. If all corrupted: Re-flight required
3. Document incident in field notes

**Discovered after leaving site:**
1. Assess severity: Can post-processing salvage data?
2. Major loss: Plan return trip if feasible
3. Document lessons learned for future expeditions

### 9.3 Software/Processing Issues

**Processing fails on field laptop:**
1. Check error messages in logs
2. Verify environment: `pytest tests/test_golden_aoi.py -v`
3. If systematic: Process data after return to lab
4. **Do NOT modify pipeline in field** (risk of breaking working code)

**Rollback procedure:**
```bash
# Restore last known-good commit
git log --oneline  # Find last working version
git checkout [COMMIT_SHA]

# Re-run validation
make validate
```

---

## 10. Success Criteria

### 10.1 Minimum Viable Data Collection

**LiDAR (must achieve):**
- [ ] All survey areas covered with ≥30% overlap
- [ ] Point density ≥150 pts/m² throughout
- [ ] RTK/PPK positioning for all tiles
- [ ] 3× backup copies of all data
- [ ] At least one site processed and QC'd in field

**Thermal (if deployed, nice-to-have):**
- [ ] All frames have radiometric data (655360-byte ThermalData blob)
- [ ] Emissivity 0.98 and fixed gain confirmed
- [ ] Poses exported and synced with LiDAR
- [ ] At least one frame orthorectified for QC

### 10.2 Field QC Metrics

**Acceptable ranges:**
- Detection counts: 100-5000 per site (depending on colony size)
- Processing time: <15 min per tile on field laptop
- Point density: 150-300 pts/m² (lower acceptable if consistent)
- RTK accuracy: <5cm horizontal (throughout survey)

**Red flags (require investigation):**
- Zero detections on any tile
- Detection counts vary >10× between adjacent tiles
- Processing crashes or hangs
- Large gaps in coverage (>20% of site)

---

## 11. Post-Expedition Actions

### 11.1 Immediate (Within 24 Hours of Return)

- [ ] Copy all data to lab storage (4th backup)
- [ ] Verify checksums on lab storage
- [ ] Generate preliminary count report
- [ ] Debrief with team: What worked? What didn't?

### 11.2 Short-Term (Within 1 Week)

- [ ] Full processing of all sites
- [ ] Accuracy assessment (if ground truth available)
- [ ] Generate QC report with panels
- [ ] Update STATUS.md with field results
- [ ] Document lessons learned in `manifests/incidents.md`

### 11.3 Long-Term (Within 1 Month)

- [ ] Final deliverables to client/stakeholders
- [ ] Publish methodology (if applicable)
- [ ] Archive raw data with metadata
- [ ] Update SOP based on field experience
- [ ] Plan improvements for next expedition

---

## Appendix A: Troubleshooting Quick Reference

| Problem | Quick Fix | See Section |
|---------|-----------|-------------|
| RTK drops to FLOAT | Land, reboot GeoCue 515 | 3.4 |
| Low point density | Decrease altitude or slow speed | 3.3 |
| Thermal emissivity wrong | Reset in H30T menu: Emissivity → 0.98 | 4.2 |
| Processing fails | Check environment: `make validate` | 6.2 |
| Backup drive full | Offload to 3rd backup, free space | 5.2 |
| Detection count zero | Check HAG parameters in provenance | 7.3 |

---

## Appendix B: Contact Information

**Technical Support:**
- Pipeline developer: [NAME / EMAIL / PHONE]
- GeoCue LiDAR support: [VENDOR CONTACT]
- DJI support: [VENDOR CONTACT]

**Emergency Contacts:**
- Field team lead: [NAME / PHONE]
- Lab/home base: [NAME / PHONE]
- Data recovery service: [SERVICE / CONTACT]

**[TO BE COMPLETED BEFORE DEPARTURE]**

---

## Appendix C: Equipment Packing List

### Drone Systems
- [ ] DJI M350 RTK drone (2× batteries minimum)
- [ ] DJI controller (charged, time synced)
- [ ] GeoCue 515 LiDAR sensor
- [ ] H30T thermal sensor (if Option B/C selected)
- [ ] Charging station + cables
- [ ] Portable battery bank (for field charging)
- [ ] Skyfront Perimeter 8 (if deployed - TBD)

### Data Storage
- [ ] 1TB SSD #1 (primary, labeled)
- [ ] 1TB SSD #2 (backup 1, labeled)
- [ ] 1TB SSD #3 (backup 2, labeled)
- [ ] USB-C cables (3×)
- [ ] Card readers (if using SD cards)
- [ ] Hard-shell cases for drives

### Computing
- [ ] Field laptop (environment pre-installed)
- [ ] Mouse (for QC review)
- [ ] Portable display (optional but recommended)
- [ ] Laptop charger + international adapters
- [ ] USB hub (for multiple drive connections)

### Documentation
- [ ] This SOP (printed, laminated pages recommended)
- [ ] RUNBOOK.md (printed or offline PDF)
- [ ] Flight logs (paper backup)
- [ ] Checklist cards (laminated, per-flight use)

### Miscellaneous
- [ ] Weatherproof bags (for equipment in field)
- [ ] Lens cleaning kit
- [ ] Spare props (drone)
- [ ] Zip ties, duct tape (field repairs)
- [ ] Portable shade/tent (for equipment setup)

---

**SOP Version:** 1.0  
**Last Reviewed:** 2025-10-14  
**Next Review:** After first field deployment  
**Status:** ⚠️ PRE-DEPLOYMENT REVIEW REQUIRED - Thermal decision pending

