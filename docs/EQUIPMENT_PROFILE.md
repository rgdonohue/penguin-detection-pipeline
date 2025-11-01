# Equipment Specifications — Argentina Field Campaign

**Last Updated:** 2025-10-17
**Status:** CRITICAL EQUIPMENT ANALYSIS INCORPORATED
**Deployment Target:** November 2025

---

## Overview

This document specifies the complete equipment suite for the penguin detection field campaign in Argentina. Equipment selections have been validated against actual test data and manufacturer specifications. **Critical context**: Manufacturer materials focus on infrastructure mapping altitudes (e.g., ~75 m); our penguin detection validation to date used 30–40 m DJI L2 flights that achieved the necessary point density. Higher wildlife-compliant altitudes must still be verified with the deployment sensor.

**Primary Deployment Mode:** LiDAR-focused with optional thermal research collection
- Validation dataset: DJI L2 on M350 at 30-40m AGL (historical test flights)
- Deployment plan: GeoCue TrueView 515 + M350 starting at 60-70m AGL per wildlife welfare guidance
- H30T thermal for documentation only (0.14°C biological contrast confirmed unsuitable for detection)

---

## 1. DJI M350 RTK Drone (Primary Platform)

### Role
Primary unmanned aerial platform for sensor deployment. Provides RTK positioning essential for <5cm accuracy requirement. Well-suited for the tile-based processing workflow with hot-swappable batteries.

### Technical Specifications

**Airframe:**
- Model: DJI Matrice 350 RTK
- Dimensions: 810×670×430 mm (unfolded)
- Weight: 6.47 kg (empty), 9.2 kg (max takeoff)
- Max payload: 2.73 kg (sufficient for TrueView 515 + H30T)
- IP rating: IP55 (adequate for field conditions)

**Flight Performance:**
- Flight time: 35-45 min with full sensor payload (empirically verified)
- Max speed: 23 m/s (Sport), 17 m/s (Normal)
- Wind resistance: 12 m/s (operational limit)
- Service ceiling: 7,000m ASL
- Operating temperature: -20°C to 50°C

**Positioning:**
- GNSS: GPS + Galileo + BeiDou + GLONASS
- RTK positioning: ±2 cm horizontal, ±3 cm vertical
- Positioning frequency: 10 Hz
- PPK: Supported as backup

### Field Configuration

**FIELD PARAMETERS:**
- **Flight altitude: Start at 60-70m AGL** (per wildlife welfare guidelines)
- **Test progressively lower altitudes** only if point density insufficient
- **Ground speed: 3-5 m/s**
- **RTK mode: REQUIRED** (GPS alone insufficient)
- **Battery plan: 6× TB65** (allows continuous operation with charging rotation)

**IMPORTANT**: Test data was collected at 30-40m with DJI L2. Wildlife best practices recommend starting at highest practicable altitude.

### Operational Notes

The M350's 35-45 minute flight time with hot-swappable batteries is actually ideal for the tile-based processing workflow. Complex long-endurance platforms add unnecessary complexity without clear benefit for this mission profile.

---

## 2. GeoCue TrueView 515 LiDAR Sensor (Primary Detection for Deployment)

### Role
Primary penguin detection sensor for Argentina deployment. **Note**: Test data (1,175 detections from Puerto Madryn) was collected using DJI L2 sensor. TrueView 515 performance may differ from test results.

### Actual Technical Specifications

**LiDAR Scanner:**
- Model: GeoCue TrueView 515
- Laser: Hesai PandarXT-32 scanner
- Wavelength: 905 nm (Class 1 eye-safe)
- Pulse rate: 640 kHz
- Usable range: 80m at 20% reflectivity
- Field of view: 120° (wider than previously documented)
- Channels: 32 laser channels

### Critical Performance Reality Check

**GeoCue Marketing vs. Wildlife Detection Reality:**

| Parameter | GeoCue Claims | Wildlife Guidelines | Field Reality |
|-----------|--------------|-------------------|--------------|
| Optimal altitude | 75m AGL | 60-70m minimum | Balance needed |
| Target objects | Buildings, powerlines | 30-50cm penguins | Different resolution needs |
| Operational range | Up to 120m | Start high, test down | Site-specific testing required |

**Altitude Testing Protocol** (TrueView 515):

**IMPORTANT**: No point density measurements exist above 40m in our test data. Test data (DJI L2 at 30-40m) showed ~8,700-9,000 pts/m², far exceeding typical requirements.

Recommended field approach:
1. **Start at 70m AGL** - Wildlife welfare baseline (per Antarctic Treaty guidelines)
2. **Test at 60m AGL** - If 70m density insufficient
3. **Test at 50m AGL** - With enhanced behavioral monitoring
4. **Only go to 40m** - With explicit written approval and wildlife observer

**Note**: Test data was collected with DJI L2 sensor at 30-40m producing 1,175 detections. PDAL metadata (`software_id = "DJI TERRA 4.5.18.1 DJI L2"`) in `data/legacy_ro/penguin-2.0/data/raw/LiDAR/cloud0.las` and `cloud3.las` confirms this provenance. TrueView 515 specifications indicate 80-120m operational range. Actual point density at higher altitudes must be verified in field.

### Field Configuration

**RECOMMENDED PARAMETERS:**
- **Altitude: Start at 60-70m AGL** (wildlife welfare priority; historic DJI L2 validation at 30-40m AGL)
- **Ground speed: 3-5 m/s**
- **Overlap: 50% minimum between lines**
- **Point density: Measure and log at each altitude** (DJI L2 test data delivered ~8,700-9,000 pts/m² at 30-40m)

**Processing Parameters** (tuned on DJI L2 data):

Two parameter sets serve different purposes:

**Production Parameters** (calibrated for accurate colony counts with DJI L2 data):
```bash
--cell-res 0.25           # Grid resolution (meters)
--hag-min 0.38            # Min penguin height (meters)
--hag-max 0.48            # Max penguin height (meters)
--min-area-cells 7        # Min detection size (cells)
--max-area-cells 45       # Max detection size (cells)
--circularity-min 0.75    # Shape filter
--solidity-min 0.93       # Compactness filter
--se-radius-m 0.22        # Morphological structuring element
--refine-grid-pct 98      # Grid refinement percentile
--refine-size 5           # Refinement window
--dedupe-radius-m 1.6     # Deduplication distance
```
**Results with DJI L2**: 1,742 raw → **1,175 deduped** (matches ~1,100 manual count)

**Golden Test Parameters** (for regression testing with DJI L2 data):
```bash
--cell-res 0.25           # Grid resolution
--hag-min 0.2             # Min height (more permissive)
--hag-max 0.6             # Max height (more permissive)
--min-area-cells 2        # Min size (more permissive)
--max-area-cells 80       # Max size (more permissive)
```
**Results with DJI L2**: 862 detections on cloud3.las (reproducibility benchmark)

**IMPORTANT**: Parameters may need adjustment for TrueView 515 data due to different sensor characteristics.

### Why Altitude Matters - Balancing Wildlife Welfare and Data Quality

**Wildlife Welfare Priority**: Antarctic Treaty guidelines and best practices require flying "as high as practicable and not lower than necessary." Literature (Goebel et al. 2015) suggests minimal disturbance at 30-60m, but welfare guidelines recommend starting at 60-70m.

**Data Quality Consideration**: Test data (DJI L2 at 30-40m) produced 1,175 deduped detections matching ~1,100 manual count. Point density was ~8,700-9,000 pts/m², far exceeding typical requirements. Higher altitudes remain untested but TrueView 515 specifications suggest 80-120m operational range.

**Field Strategy**: Start high (60-70m), test point density, and only descend if absolutely necessary with proper wildlife monitoring and approvals.

---

## 3. DJI H30T Thermal Sensor (Detection Capability Untested)

### Equipment Update: H30T vs. H20T

Test data used H20T (640×512). Field deployment will use H30T with improvements that may or may not enable better detection:

**Specification Comparison:**

| Feature | H20T (Tested) | H30T (Deployment) | Potential Impact |
|---------|--------------|-------------------|------------------|
| Resolution | 640×512 (328K pixels) | 1280×1024 (1.3M pixels) | 4× pixel count, 2× linear resolution |
| Sensitivity | ≤50mK NETD | Similar/better | Comparable or improved |
| Additional | Basic | 32× zoom, NIR light | Unknown utility for aerial detection |

### H30T Performance: Unknown Without Testing

**What we know from H20T testing:**
- Penguins often show strong positive contrast (ΔT ≈ 8–11 °C) in several frames, but some frames collapse to ΔT ≈ 0.14 °C
- Scene noise can reach ±2.9 °C; automated detection tops out at F1 ≈ 0.30 even with enhancements
- Radiometric extraction is reliable and supports validation/QA workflows

**What we don't know about H30T:**
- Whether 2× better spatial resolution improves signal discrimination
- Whether higher pixel count enables effective signal averaging to reduce noise
- Whether improved spatial detail allows better penguin-background separation
- Actual detection performance with H30T has not been tested

**Honest assessment**: 4× resolution improvement may help more than anticipated. Test flights recommended before ruling out H30T for validation workflows; do not expect it to replace LiDAR for counting.

### Recommended Deployment Approach

**Primary role**: Secondary sensor for validating LiDAR detections, filtering false positives, and mapping colony activity. Collect thermal simultaneously with LiDAR—at no additional sortie cost—to build ΔT confidence scores and behavioural overlays.

**Deploy H30T with realistic expectations:**
- Test H30T performance early in deployment to characterise ΔT behaviour
- Use thermal signatures to confirm LiDAR detections or flag likely false positives (cold returns)
- Generate colony activity maps and archive data for future sensor/fusion evaluation
- Maintain LiDAR as the primary detection/counting method

**Field Configuration:**
- **Altitude: Match selected LiDAR altitude** for registration
- **Settings: Radiometric ON, Emissivity 0.98**
- **Timing: Midday preferred** (maximum thermal contrast)
 - **Purpose: Validation/QC + behavioural context; automated detection remains experimental**

---

## 4. Skyfront Perimeter 8 Drone

### Status: Unknown

We don't have information about the Skyfront Perimeter 8 for this application.

**What we don't know:**
- Whether it's compatible with the TrueView 515 sensor
- Flight endurance with the LiDAR payload
- Whether long-endurance flights offer advantages over the M350 battery rotation approach
- Field team's familiarity with this platform
- Actual operational use cases

**M350 baseline:**
The M350 with 6 batteries provides 3-4+ hours of total flight time through battery rotation. For tile-based survey work with 35-45 minute flights, this approach was used during test flights.

**If deploying Skyfront:**
- Verify TrueView 515 compatibility before field deployment
- Confirm the team has training and support
- Keep M350 available as backup
- Test in field conditions before committing to full deployment

---

## 5. Data Storage and Computing

### Validated Requirements

**Field Laptop (Based on Processing Reality):**
- CPU: 6+ cores recommended (processing is CPU-intensive)
- RAM: 32 GB minimum (point cloud processing)
- Storage: 512 GB SSD free space
- Software: Pre-installed virtual environment with all dependencies

**Storage Strategy:**
- 3× 1TB SSDs (triple redundancy maintained)
- exFAT format for cross-platform compatibility
- SHA256 checksums after every transfer

---

## 6. Critical Operational Parameters Summary

### LiDAR Operations (Critical Parameters)

**Requirements based on test data and detection algorithm needs:**

| Parameter | Specification | Rationale |
|-----------|--------------|-----------|
| Altitude | Start at 60-70m AGL | Wildlife welfare baseline; historic DJI L2 validation at 30-40m AGL |
| Point density | Measure and log at each altitude | Historical DJI L2 data delivered ~8,700-9,000 pts/m² at 30-40m; minimum threshold under evaluation |
| Overlap | 50% minimum | Prevents coverage gaps |
| RTK | Required | GPS alone insufficient for tile registration (<1m accuracy needed) |

**Note**: Detection performance not validated against ground truth. Operational thresholds are inferred from DJI L2 flights at 30-40m AGL with high point density; verify performance onsite for TrueView 515 at wildlife-compliant altitudes.

### Thermal Operations (IF DEPLOYED)

| Parameter | Setting | Reality Check |
|-----------|---------|--------------|
| Purpose | Documentation only | Cannot detect individuals |
| Altitude | Match selected LiDAR altitude | Maintain registration with LiDAR dataset |
| Expectations | Colony patterns | NOT counting |

---

## 7. Pre-Deployment Critical Actions

### MUST COMPLETE

1. **Wildlife Welfare Training**: Ensure team understands 60-70m starting altitude and monitoring requirements
2. **Altitude Testing Protocol**: Day 1 test from 70m down, only as needed
3. **Thermal Expectations**: H30T performance unknown, test early
4. **Skyfront Verification**: Confirm TrueView 515 compatibility before deployment
5. **Permit Verification**: Confirm wildlife disturbance permits for operations

### Equipment Verification

Before deployment, verify:
- [ ] TrueView 515 calibration current (<6 months)
- [ ] Wildlife disturbance permits obtained
- [ ] Wildlife observer trained and briefed
- [ ] RTK achieving <5cm accuracy consistently
- [ ] H30T radiometric mode confirmed if deploying
- [ ] Skyfront-TrueView 515 compatibility tested
- [ ] All batteries showing >80% capacity

---

## 8. Wildlife Welfare and Monitoring Protocol

### Regulatory Context
- **Antarctic Treaty Environmental Guidelines** (Resolution 4, 2018): "Fly as high as practicable and not lower than necessary"
- **Published research** (Goebel et al. 2015, Polar Biology): No observable disturbance at 30-60m
- **Best practice**: Start at highest operational altitude and descend only if necessary

### Field Monitoring Requirements

**Wildlife Observer Role:**
- Dedicated observer (not pilot) to monitor penguin behavior
- Document any reactions: head raising, alarm calls, movement from nests
- Authority to abort mission if disturbance observed
- Complete behavior log for each flight

**Altitude Testing Protocol:**
1. **Day 1 - Small test area only**
   - Flight 1: 70m AGL - assess point density and behavior
   - Flight 2: 60m AGL - if 70m inadequate (requires approval)
   - Flight 3: 50m AGL - enhanced monitoring (requires written approval)
   - Flight 4: 40m AGL - only with explicit approval and continuous monitoring

**Behavioral Response Categories:**
- **No response**: Normal behavior continues
- **Alert**: Head raising, increased vigilance
- **Mild disturbance**: Movement within colony, vocalizations
- **Strong disturbance**: Birds leaving nests, panic responses
- **Abort threshold**: Any strong disturbance or repeated mild disturbance

### Permit Requirements
- [ ] Wildlife disturbance permit for operations <70m
- [ ] Written approval from wildlife management authority
- [ ] Client acknowledgment of disturbance risks
- [ ] Insurance coverage for wildlife operations

### Mitigation Strategies
- Minimize time over colonies
- Avoid sensitive periods (egg laying, early chick rearing)
- Maintain consistent altitude (no sudden changes)
- Launch/land >50m from colony edge
- Single pass per area when possible

---

## 9. Bottom Line Guidance

### What Will Work

✅ **TrueView 515 at appropriate altitude** - Start at 60-70m per wildlife guidelines
✅ **M350 and Skyfront platforms** - Both available for deployment
✅ **Processing pipeline** - Tested and reproducible (with DJI L2 data)
✅ **Wildlife monitoring protocol** - Ensures ethical operations

### What Needs Testing

⚠️ **Point density at 60-70m** - No test data exists above 40m
⚠️ **TrueView 515 performance** - Test data was from DJI L2
⚠️ **H30T thermal capability** - 4× resolution may improve detection
⚠️ **Skyfront compatibility** - Verify with TrueView 515 before deployment

### The Path to Success

1. **Start at 60-70m altitude** (wildlife welfare priority)
2. **Test point density early** - Adjust altitude only if necessary
3. **Monitor penguin behavior** - Abort if disturbance observed
4. **Document everything** - Altitude, density, behavior, permissions
5. **Test H30T early** - May provide better results than H20T
6. **Verify Skyfront compatibility** before relying on it

---

**Key Message**: Wildlife welfare requires starting at 60-70m altitude per Antarctic Treaty guidelines. Test data (DJI L2 at 30-40m) produced 1,175 detections matching manual counts with ~8,700-9,000 pts/m² density. TrueView 515 deployment must balance wildlife welfare with data quality - start high, test density, and only descend with proper approvals and monitoring. Parameters tuned on DJI L2 data may need adjustment for TrueView 515.

---

**Version:** 3.0 (Critical Equipment Analysis)
**Previous Version:** 2.0 (Comprehensive specifications)
**Updated:** 2025-10-15
**Note:** This version incorporates actual equipment performance data versus manufacturer claims
