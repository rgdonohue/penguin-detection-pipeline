# Pre-Deployment Checklist

**Penguin Detection Pipeline - Argentina Field Campaign**

**Target Departure Date:** [TO BE COMPLETED]  
**Team Lead:** [TO BE COMPLETED]  
**Last Updated:** 2025-10-14

---

## 🚨 CRITICAL: Must Complete Before Departure

### 1. Thermal Decision (BLOCKING ALL OTHER TASKS)

**Deadline:** 48 hours before departure

- [ ] **DECISION MADE:** Which option? (Check ONE):
  - [ ] **Option A: LiDAR-Only** (Recommended for 1-week timeline)
  - [ ] **Option B: Thermal with Zoo Test** (Requires 3-5 day delay)
  - [ ] **Option C: Dual-Mode Collection** (Research data only)

- [ ] Decision documented in: `docs/FIELD_SOP.md` Section 2
- [ ] Decision maker: _________________ Date: _________
- [ ] Flight crew notified of decision
- [ ] Equipment list updated based on decision

**If Option B selected, ADDITIONAL checklist:**
- [ ] Zoo test scheduled (2-day window)
- [ ] Zoo test completed with settings: emissivity 0.98, fixed gain
- [ ] Zoo data processed (4-hour turnaround)
- [ ] Thermal contrast measured: _____ σ (need >1.0σ to proceed)
- [ ] **GO/NO-GO decision made:** [ ] GO [ ] NO-GO (switch to Option A)

**If Option A or C selected:**
- [ ] Thermal sections removed from field procedures (Option A only)
- [ ] Team briefed on LiDAR-only workflow

---

## 2. Pipeline Validation (2-3 Hours)

**Deadline:** 3 days before departure

### Test Environment Setup

- [ ] Field laptop identified: Make/Model _______________
- [ ] Laptop specs verified:
  - [ ] RAM: _____ GB (minimum 16GB, recommend 32GB)
  - [ ] Free disk: _____ GB (minimum 50GB, recommend 256GB)
  - [ ] CPU cores: _____ (minimum 4, recommend 6+)
  - [ ] OS: [ ] macOS [ ] Linux [ ] Windows+WSL2

### Software Installation

- [ ] Python 3.11+ installed: Version _______
- [ ] Repository cloned to field laptop
- [ ] Virtual environment created: `make env`
- [ ] Dependencies installed successfully
- [ ] **Validation passed:** `make validate`
  - [ ] Environment check: PASSED
  - [ ] LiDAR smoke test: 879 detections on cloud3.las
  - [ ] 12 golden AOI tests: ALL PASSED

### Offline Capability Test

- [ ] Disable WiFi/network on laptop
- [ ] Run test processing: `make test-lidar`
- [ ] Verify works without internet connection
- [ ] Re-enable network

### Team Training

- [ ] Primary operator trained on processing workflow
- [ ] Backup operator trained (in case primary unavailable)
- [ ] Both operators successfully processed sample tile
- [ ] QC criteria reviewed: What's "reasonable" detection count?
- [ ] Troubleshooting guide reviewed

---

## 3. Equipment Preparation (1 Day)

**Deadline:** 2 days before departure

### GeoCue 515 LiDAR

- [ ] Hardware inspection: No physical damage
- [ ] Firmware version: _________ (latest stable)
- [ ] **RTK/PPK module: ENABLED AND TESTED**
- [ ] Calibration valid: Factory calibration date _______ (<6 months old)
- [ ] Mounting hardware secure and tested
- [ ] Power cable and connectors inspected
- [ ] Test flight completed (30 min local flight)
- [ ] Test data downloaded and processed successfully

### DJI M350 RTK Drone

- [ ] Airframe inspection: No damage, props secure
- [ ] Batteries: Qty _____ (minimum 4 recommended)
- [ ] All batteries charged to 100%
- [ ] Battery health check: All >80% capacity
- [ ] Controller charged and time-synced
- [ ] **RTK positioning enabled in controller**
- [ ] Firmware version: _________ (latest stable)
- [ ] Test flight completed: 20 min hover + waypoint test
- [ ] Emergency procedures reviewed with pilot

### DJI H30T Thermal (IF Option B or C Selected)

- [ ] Sensor inspection: Lens clean, no damage
- [ ] Mounted to M350, tested
- [ ] **Settings verified:** (capture test frame, check EXIF)
  - [ ] Radiometric mode: ON
  - [ ] Emissivity: 0.98 (NOT 1.00)
  - [ ] Gain: Fixed (NOT auto)
- [ ] ThermalData blob present: 655360 bytes confirmed
- [ ] Poses export tested: `exiftool` working
- [ ] Test orthorectification completed
- [ ] Flat-field calibration procedure practiced

### Skyfront Perimeter 8 (IF DEPLOYING)

**⚠️ ROLE UNDEFINED - Must specify before deployment**

- [ ] Role documented: _______________________
- [ ] Equipment list updated
- [ ] Operating procedures added to SOP
- [ ] Test flight completed (if deploying)

**OR:**

- [ ] Confirmed NOT deploying - removed from equipment list

---

## 4. Data Management Setup (2 Hours)

**Deadline:** 2 days before departure

### Storage Hardware

- [ ] **Primary SSD:** Brand/Model _________ Capacity: _____TB
  - [ ] Formatted (exFAT for cross-platform compatibility)
  - [ ] Labeled: "PRIMARY" with tape/marker
  - [ ] Read/write test: Successful
  - [ ] Free space: _____ GB (should be 100% before departure)

- [ ] **Backup SSD #1:** Brand/Model _________ Capacity: _____TB
  - [ ] Formatted (exFAT)
  - [ ] Labeled: "BACKUP 1"
  - [ ] Read/write test: Successful
  - [ ] Free space: _____ GB

- [ ] **Backup SSD #2:** Brand/Model _________ Capacity: _____TB
  - [ ] Formatted (exFAT)
  - [ ] Labeled: "BACKUP 2 - BASE CAMP"
  - [ ] Read/write test: Successful
  - [ ] Free space: _____ GB

- [ ] **Total capacity:** _____ TB (minimum 3TB total, 1TB per drive)
- [ ] All drives in protective cases
- [ ] USB cables: 3× tested and packed

### Backup Procedures

- [ ] Checksum script tested:
  ```bash
  shasum -a 256 test_file.laz
  ```
- [ ] Backup script created (or manual procedure documented)
- [ ] Backup schedule agreed: End of each flight day
- [ ] Backup verification procedure tested
- [ ] Team trained on backup workflow

### File Naming Convention

- [ ] Convention documented: [SITE]_[YYYYMMDD]_[HHMMSS]_[LINE].laz
- [ ] Example created: `PunTombo_20251020_143022_L001_lidar.laz`
- [ ] All team members briefed on convention
- [ ] Naming template cards created (laminated)

---

## 5. Documentation Package (1 Hour)

**Deadline:** 1 day before departure

### Digital Documentation

- [ ] README.md: Downloaded/printed
- [ ] RUNBOOK.md: Downloaded/printed
- [ ] FIELD_SOP.md: Downloaded/printed
- [ ] STATUS.md: Downloaded/printed (for reference)
- [ ] All docs available offline on field laptop

### Printed Materials

- [ ] Field SOP: Printed and bound (recommend laminated pages)
- [ ] Quick-reference cards: Printed and laminated
  - [ ] LiDAR flight parameters card
  - [ ] Thermal settings card (if deploying)
  - [ ] File naming convention card
  - [ ] Emergency contact card
- [ ] Flight log sheets: Qty _____ (recommend 20+)
- [ ] Checklist cards for per-flight use: Qty _____ (recommend 10+)

### Emergency Information

- [ ] Tech support contacts documented:
  - [ ] Pipeline developer: _______________ / _______________
  - [ ] GeoCue support: _______________ / _______________
  - [ ] DJI support: _______________ / _______________
- [ ] Lab/home base contact: _______________ / _______________
- [ ] Data recovery service: _______________ / _______________
- [ ] Emergency procedures reviewed with team

---

## 6. Final System Tests (2-3 Hours)

**Deadline:** 1 day before departure

### End-to-End Workflow Test

- [ ] **Simulate full workflow:**
  1. [ ] Capture test data (or use sample data)
  2. [ ] Download to PRIMARY drive
  3. [ ] Backup to BACKUP 1 (verify checksum match)
  4. [ ] Process one tile: `python scripts/run_lidar_hag.py ...`
  5. [ ] Review QC plots
  6. [ ] Load GeoJSON in QGIS
  7. [ ] Verify detection counts reasonable
  8. [ ] Document time elapsed: _____ minutes

- [ ] **Workflow timing acceptable:** <60 min total
- [ ] All team members can execute workflow independently

### Failure Mode Testing

- [ ] Test: Primary drive "fails" (unplug during workflow)
  - [ ] Backup 1 accessible? [ ] YES [ ] NO
  - [ ] Team knows how to continue? [ ] YES [ ] NO

- [ ] Test: Processing fails (introduce error)
  - [ ] Team knows how to check logs? [ ] YES [ ] NO
  - [ ] Team knows when to abort vs. troubleshoot? [ ] YES [ ] NO

- [ ] Test: Rollback procedure
  - [ ] Team knows how to restore last working version? [ ] YES [ ] NO

### QC Criteria Calibration

- [ ] Process 3 sample tiles with varying densities
- [ ] Note detection counts:
  - Tile 1: _____ detections (_____ pts/m²)
  - Tile 2: _____ detections (_____ pts/m²)
  - Tile 3: _____ detections (_____ pts/m²)
- [ ] Establish "reasonable range" for field QC: _____ to _____ detections per tile
- [ ] Team understands what triggers re-flight decision

---

## 7. Logistics and Packing (1 Day)

**Deadline:** Day before departure

### Equipment Packing

**Drone Systems:**
- [ ] DJI M350 RTK (in hard case)
- [ ] M350 batteries: Qty _____ (all charged)
- [ ] DJI controller (charged)
- [ ] GeoCue 515 LiDAR (in protective case)
- [ ] H30T thermal sensor (in protective case, IF DEPLOYING)
- [ ] Charging station + power cables
- [ ] Portable battery bank (charged)
- [ ] International power adapters
- [ ] Skyfront Perimeter 8 (IF DEPLOYING)

**Data & Computing:**
- [ ] Field laptop (charged)
- [ ] Laptop charger + international adapters
- [ ] PRIMARY SSD (in protective case)
- [ ] BACKUP 1 SSD (in protective case)
- [ ] BACKUP 2 SSD (separate bag - for base camp)
- [ ] USB-C cables: Qty _____
- [ ] USB hub (for multiple connections)
- [ ] Mouse (for QC review)
- [ ] Portable display (optional but recommended)
- [ ] Card readers (if using SD cards)

**Documentation:**
- [ ] Printed SOP (bound/laminated)
- [ ] Quick-reference cards (laminated)
- [ ] Flight log sheets
- [ ] Per-flight checklist cards
- [ ] Emergency contact card

**Field Supplies:**
- [ ] Weatherproof bags (for equipment)
- [ ] Lens cleaning kit
- [ ] Spare propellers: Qty _____
- [ ] Zip ties, duct tape (field repairs)
- [ ] Portable shade/tent (for setup area)
- [ ] Sharpies/labels (for marking drives/data)

### Travel Logistics

- [ ] Equipment customs documentation prepared
- [ ] Battery transport approved (lithium battery regulations)
- [ ] Insurance coverage verified (equipment + drone)
- [ ] Travel to Argentina booked:
  - [ ] Flights: _______________ to _______________
  - [ ] Accommodation: _______________________
  - [ ] Ground transport: ____________________
- [ ] Permits obtained:
  - [ ] Drone flight permits: [ ] YES [ ] IN PROGRESS
  - [ ] Research permits: [ ] YES [ ] IN PROGRESS
  - [ ] Site access permissions: [ ] YES [ ] IN PROGRESS

---

## 8. Day-Before Departure Final Checks

**Complete these checks the night before departure:**

### Equipment Status

- [ ] All batteries charged to 100%:
  - [ ] Drone batteries: _____ / _____ charged
  - [ ] Laptop battery: 100%
  - [ ] Portable battery bank: 100%
  - [ ] Controller battery: 100%

- [ ] All storage drives empty and formatted:
  - [ ] PRIMARY: _____ GB free
  - [ ] BACKUP 1: _____ GB free
  - [ ] BACKUP 2: _____ GB free

- [ ] Software environment validated:
  - [ ] `make validate` run time: _______ (last 24 hours)
  - [ ] Result: [ ] PASSED [ ] FAILED (if failed, DO NOT DEPART)

### Team Readiness

- [ ] All team members briefed on:
  - [ ] Thermal decision (Option A/B/C)
  - [ ] Flight procedures
  - [ ] Data backup workflow
  - [ ] QC criteria and gates
  - [ ] Emergency procedures

- [ ] Roles assigned:
  - [ ] Pilot: _____________________
  - [ ] Sensor operator: _____________________
  - [ ] Data manager: _____________________
  - [ ] Backup for each role: _____________________

- [ ] Communication plan established:
  - [ ] Daily check-ins with home base: [ ] YES [ ] NO
  - [ ] Time zone: _______________
  - [ ] Check-in time: _______________
  - [ ] Method: [ ] Satellite phone [ ] Cell [ ] Email

### Final Contingency Review

- [ ] Backup plan if GeoCue 515 fails: _______________________
- [ ] Backup plan if M350 fails: _______________________
- [ ] Backup plan if field laptop fails: _______________________
- [ ] Backup plan if all drives fail: _______________________
- [ ] Medical emergency procedures: [ ] Reviewed
- [ ] Weather delay procedures: [ ] Reviewed

---

## 9. Departure Day Checklist

**Morning of departure:**

- [ ] **FINAL GO/NO-GO DECISION**
  - [ ] All critical items above completed? [ ] YES [ ] NO
  - [ ] Team healthy and ready? [ ] YES [ ] NO
  - [ ] Weather forecast acceptable? [ ] YES [ ] NO
  - [ ] **DECISION:** [ ] GO [ ] NO-GO

**If GO:**

- [ ] All equipment packed and inventoried
- [ ] Battery levels confirmed: All 100%
- [ ] Documentation package complete
- [ ] Emergency contacts distributed to team
- [ ] Home base notified of departure
- [ ] Vehicle loaded and secured
- [ ] **DEPARTURE AUTHORIZED:** __________ (Team Lead Signature)

**If NO-GO:**

- [ ] Reason documented: _______________________
- [ ] Stakeholders notified
- [ ] New departure date: _______________________
- [ ] Items to complete before new date: _______________________

---

## 10. Post-Deployment Review Checklist

**Complete within 1 week of return:**

- [ ] All data backed up to lab storage (4th copy)
- [ ] Checksums verified on lab storage
- [ ] Preliminary count report generated
- [ ] Equipment inventory: All items returned? [ ] YES [ ] NO
- [ ] Equipment condition: Any damage? [ ] YES [ ] NO
- [ ] Team debrief completed:
  - [ ] What worked well?
  - [ ] What didn't work?
  - [ ] Recommendations for next time?
- [ ] STATUS.md updated with field results
- [ ] Lessons learned documented in `manifests/incidents.md`
- [ ] SOP updated based on field experience
- [ ] This checklist reviewed and improved for next deployment

---

## Checklist Status

**Overall Completion:** _____ / _____ items (______%)

**Blocking Issues (Prevent Departure):**
1. _____________________________________
2. _____________________________________
3. _____________________________________

**Non-Blocking Issues (Note for field):**
1. _____________________________________
2. _____________________________________
3. _____________________________________

**Sign-Off:**

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Team Lead | | | |
| Pilot | | | |
| Data Manager | | | |
| Technical Support | | | |

**DEPLOYMENT AUTHORIZED:** [ ] YES [ ] NO

**Authorized By:** _____________________ **Date:** __________

---

**Version:** 1.0  
**Last Updated:** 2025-10-14  
**Next Review:** After first deployment

