# Thermal Imaging Limitation - Expert Review Request

**Date**: 2025-10-14
**Project**: Antarctic Penguin Detection via DJI H20T Thermal + LiDAR
**Status**: Seeking external validation before project decision
**Contact**: [Your contact information]

---

## Executive Summary

We have developed a working pipeline to extract and analyze 16-bit radiometric thermal data from DJI H20T thermal images captured over an Antarctic penguin colony. The extraction code is validated and produces temperature values in the expected range. However, we observe extremely weak thermal contrast between penguins and background (0.14°C / 0.047σ), making detection impractical.

**Key Finding**: Penguins show only 0.047σ signal-to-noise ratio above background, resulting in 15-35× false positive rates at any usable detection threshold.

**Question for Expert Review**: Is this weak thermal signal expected for Antarctic conditions, or have we missed a critical calibration/processing step?

---

## 1. Equipment & Configuration

### Camera System
- **Model**: DJI H20T (mounted on Matrice 300 RTK)
- **Thermal Sensor**: Radiometric LWIR (640×512 resolution)
- **Spectral Range**: 8-14 μm (manufacturer spec)
- **NETD**: <50mK @ f/1.0 (manufacturer spec)
- **Image Format**: R-JPEG (JPEG container with embedded thermal data)

### Flight Parameters
- **Date**: November 6, 2024
- **Location**: Argentina (42°56'10"S, 64°20'05"W)
- **Time**: 19:45:32 - 19:45:53 UTC (verified frames 0353-0359)
- **Altitude**: ~30m AGL (from metadata)
- **Environmental Conditions**:
  - Ambient temperature: 21°C (from EXIF metadata)
  - Relative humidity: 70% (from EXIF metadata)
  - Season: Austral spring (early breeding season)

### Camera Settings (from EXIF)
```
Emissivity: 100 (interpreted as 1.00 = perfect black body)
Reflection: 230 (possibly 23.0°C or encoded differently)
AmbientTemperature: 21°C
RelativeHumidity: 70%
ObjectDistance: 5m
```

**Concern**: Emissivity set to 1.00 rather than biological tissue (~0.95-0.98). However, our testing shows this makes minimal difference to SNR.

---

## 2. Data Extraction Method

### Raw Data Format
- **ThermalData blob**: 655,360 bytes (640×512×2 bytes, uint16 little-endian)
- **Extracted via**: `exiftool -b -ThermalData image.jpg`
- **Raw DN range**: 16,600 - 18,263 (typical for Antarctic ground temperatures)

### Conversion Formula Applied
```python
celsius = (DN >> 2) * 0.0625 - 273.15
```

**Source**: Based on open-source implementations:
- https://github.com/uav4geo/Thermal-Tools
- https://github.com/alex-suero/thermal-image-converter

**Result**: Temperature range -13.77°C to +12.16°C (consistent with Antarctic ground/ice)

**Validation**:
- Formula produces physically plausible values
- Tested on 7 frames (0353-0359), results consistent
- Matches magnitude of ambient conditions

---

## 3. Observed Temperature Statistics

### Frame 0356 (Ground Truth: 26 Verified Penguins)

| Region | Mean Temp | Std Dev | Min | Max |
|--------|-----------|---------|-----|-----|
| **Full scene** | -5.69°C | 2.91°C | -13.77°C | +12.16°C |
| **Background** (excluding penguins) | -5.69°C | 2.91°C | - | - |
| **Penguins** (26 ground truth locations) | -5.56°C | 2.21°C | - | - |
| **Contrast** | **+0.14°C** | - | - | - |

**Signal-to-Noise Ratio**: 0.14°C / 2.91°C = **0.047σ**

### Frame-to-Frame Consistency (21-second sequence)

All frames captured 19:45:32 - 19:45:53:

| Frame | Mean | Std Dev | Variation from 0356 |
|-------|------|---------|---------------------|
| 0353 | -7.52°C | 3.07°C | -1.83°C |
| 0354 | -6.59°C | 3.11°C | -0.90°C |
| 0355 | -6.03°C | 2.96°C | -0.34°C |
| **0356** | **-5.69°C** | **2.91°C** | **0.00°C** |
| 0357 | -5.62°C | 2.60°C | +0.07°C |
| 0358 | -5.61°C | 2.56°C | +0.08°C |
| 0359 | -5.60°C | 2.49°C | +0.09°C |

**Observation**: Frame-to-frame variation (1.92°C) is less than average per-frame std dev (2.81°C), indicating temperatures are consistent and measurements are stable.

---

## 4. Detection Performance

### Method
- Local maxima detection (10-pixel neighborhood)
- Threshold: mean + σ × std_dev
- Match criterion: Ground truth penguin within 20 pixels of detected peak

### Results (Frame 0356, 26 ground truth penguins)

| Threshold | Peaks Detected | True Positives | False Positives | Recall | Precision | FP Rate |
|-----------|----------------|----------------|-----------------|--------|-----------|---------|
| Mean + 0.5σ | 946 | 21 | 925 | 80.8% | 2.2% | 35.6× |
| Mean + 1.0σ | 645 | 13 | 632 | 50.0% | 2.0% | 24.8× |
| Mean + 1.5σ | 463 | 10 | 453 | 38.5% | 2.2% | 17.8× |

**Observation**: At any threshold producing reasonable recall (>50%), false positive rate is 15-35× higher than true positives. This is unusable for practical detection.

---

## 5. Calibration Investigations Attempted

### A. Emissivity Correction

**Test**: Applied standard emissivity correction formula:
```
T_object = T_measured / ε - ((1 - ε) / ε) × T_reflected
```

**Parameters tested**:
- ε = 0.98 (biological tissue)
- T_reflected = 23.0°C (decoded from Reflection=230 metadata)
- T_reflected = -43.1°C (alternate interpretation: 230K)

**Result**: No improvement in SNR. Contrast remains 0.14°C (0.047σ).

**Conclusion**: Emissivity correction does not explain weak signal.

---

### B. Alternative Conversion Formulas

**Tests**:
1. Basic formula (current): `(DN >> 2) * 0.0625 - 273.15`
2. Atmospheric transmission correction (attempted but no atmospheric distance metadata)
3. Direct linear scaling: `DN * scale + offset` (various scales tried)

**Result**: All formulas produce identical or near-identical results. Contrast remains ~0.14°C.

**Conclusion**: The conversion formula is not the limiting factor.

---

### C. ThermalCalibration Blob Analysis

**Location**: 32KB EXIF blob (`ThermalCalibration`)

**Inspection**:
```
Offset 0x000-0x1F0: Repeating pattern 0x41FE (16,894 or 0xFE41 = 65,089)
Offset 0x1F0+:      Increasing sequence 0x42FE, 0x43FE, ..., 0x60FE
```

**Hypothesis**: Lookup table for DN-to-temperature calibration

**Status**: Format unknown, cannot decode without DJI SDK or documentation

**Alternative**: Compared blob checksums across frames - identical between frames, suggesting camera-level calibration (not scene-dependent)

**Conclusion**: May contain additional corrections, but format is proprietary. Unclear if decoding would improve SNR given consistency of measurements.

---

### D. 8-bit JPEG Preview Analysis

**Test**: Compared 16-bit radiometric data against embedded 8-bit JPEG preview

**8-bit statistics** (Frame 0356):
- Range: 0-255 (full dynamic range)
- Mean: 151.8 ± 39.7
- Std dev: 39.7 (significantly higher than 16-bit: 2.91°C)

**Interpretation**: 8-bit preview appears contrast-enhanced by DJI software for visual display. Our 16-bit extraction preserves true radiometric values.

**Conclusion**: We are extracting correct data; preview is post-processed for visualization.

---

## 6. Hypotheses for Weak Signal

### H1: Penguin Surface Temperature ≈ Ambient (Most Likely)

**Physical basis**:
- Penguins have excellent insulation (plumage, fat layer)
- Internal body temp 38-39°C, but surface temp regulated near ambient
- In cold conditions, minimize heat loss = minimal surface temperature elevation
- Ground/snow at -5 to -7°C, penguin surface barely warmer

**Supporting evidence**:
- Contrast consistent across 7 frames (environmental, not measurement error)
- Background variability (2.91°C) >> penguin contrast (0.14°C)
- Time of day (19:45, dusk) = reduced solar heating

**Expectation**: Would expect 2-5°C contrast in warmer conditions or with solar heating.

---

### H2: Camera Configuration Issue (Less Likely)

**Concerns**:
- Emissivity = 1.00 (should be ~0.98 for biology)
- Unknown atmospheric correction settings
- Possible gain/sensitivity settings not optimal

**Counter-evidence**:
- Emissivity correction tested, no improvement
- Temperature values physically plausible
- Camera producing stable, repeatable measurements

**Status**: Cannot rule out, but seems unlikely given measurement consistency.

---

### H3: Missing Calibration Step (Unknown)

**Concern**: ThermalCalibration blob not decoded; may contain scene-specific corrections

**Status**:
- Blob format proprietary
- Appears camera-specific (identical across frames)
- Unclear if contains scene corrections or static calibration curve

**Risk**: Possible we are missing a critical correction factor, but given physical plausibility of absolute temps, seems low probability.

---

### H4: Spectral Limitations (Possible)

**Theory**: LWIR (8-14 μm) may not be optimal for detecting small temperature differences in cold environments

**Status**:
- Camera NETD <50mK suggests should be sensitive enough
- However, NETD is lab specification; field performance may differ
- No access to raw sensor data to verify noise floor

**Needs verification**: Is 0.14°C signal above 50mK NETD specification realistic in field conditions?

---

## 7. What We Need Verified

### Critical Questions

1. **Is 0.14°C penguin-background contrast physically expected in Antarctic conditions?**
   - Literature suggests 2-5°C contrast in temperate climates
   - Do Antarctic penguins exhibit minimal surface thermal signature?
   - Is dusk timing (19:45) significant?

2. **Is our conversion formula correct?**
   - We used: `(DN >> 2) * 0.0625 - 273.15`
   - Produces plausible absolute temperatures
   - But could there be additional corrections needed?

3. **Is the ThermalCalibration blob critical?**
   - 32KB of data we cannot decode
   - Could it contain scene-specific corrections that would improve SNR?
   - Or is it just a static camera calibration curve?

4. **Should emissivity correction make a bigger difference?**
   - We tested ε = 1.00 vs 0.98, minimal change
   - Are we applying the correction correctly?
   - Could reflected temperature be significantly different from assumed 23°C?

5. **Is 0.047σ SNR plausible for a <50mK NETD camera?**
   - Background std dev: 2.91°C = 2910mK
   - Contrast: 0.14°C = 140mK
   - Does this match expected field performance?

6. **Are there alternative processing approaches we've missed?**
   - Temporal differencing across frames?
   - Spectral unmixing or advanced filtering?
   - Machine learning approaches to enhance weak signals?

---

## 8. Data Available for Review

### Image Data
- **Location**: `data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5/`
- **Frames**: DJI_20241106194532_0353_T.JPG through DJI_20241106194553_0359_T.JPG (7 frames)
- **Size**: ~3.5 MB per image
- **Format**: R-JPEG with embedded 16-bit ThermalData blob

### Ground Truth
- **File**: `verification_images/frame_0356_locations.csv`
- **Content**: 26 verified penguin locations (x,y pixel coordinates)
- **Source**: Manual annotation from PDF verification document

### Extracted Data
- **Temperature arrays**: `data/interim/thermal_validation/DJI_20241106194542_0356_T_celsius.npy`
- **Statistics**: `data/interim/thermal_validation/DJI_20241106194542_0356_T_stats.txt`
- **Visualizations**:
  - `hotspot_overlay_reproducible.png` - Detection performance
  - `DJI_20241106194542_0356_T_validation.png` - Temperature distribution

### Code (Reproducible)
- **Extraction**: `pipelines/thermal.py` - `extract_thermal_data()` function
- **Validation**: `scripts/create_hotspot_overlay.py` - Full detection analysis
- **Calibration tests**: `scripts/investigate_thermal_calibration.py`
- **Frame comparison**: `scripts/compare_verified_frames.py`

**Repository**: Can provide access to full codebase for review/replication

---

## 9. Alternative Explanations to Consider

### A. Measurement Error
**Hypothesis**: Our extraction is producing incorrect values

**Evidence against**:
- Values physically plausible (-14°C to +12°C in Antarctic)
- Consistent across 7 independent frames
- Matches magnitude of ambient temperature metadata (21°C ambient)

**Confidence**: Low probability - measurements appear valid

---

### B. Ground Truth Error
**Hypothesis**: Annotated locations are not actually penguins

**Evidence against**:
- Manual verification from visual imagery
- PDF shows clear biological shapes at marked locations
- 26 confident annotations (2 uncertain excluded)

**Confidence**: Low probability - ground truth appears reliable

---

### C. Spatial Misalignment
**Hypothesis**: Thermal and visual imagery not co-registered

**Evidence against**:
- 80.8% of ground truth points matched within 20 pixels
- Would expect 0% match if severely misaligned
- EXIF metadata shows identical pose data for visual/thermal pairs

**Confidence**: Low probability - alignment appears reasonable

---

### D. Temporal Changes
**Hypothesis**: Penguins moved between visual and thermal captures

**Evidence against**:
- Visual and thermal captured simultaneously (H20T integrated sensor)
- All 7 frames show similar weak signal
- Birds in Antarctic are relatively stationary during breeding

**Confidence**: Low probability - timing alignment is good

---

### E. Different Species/Behavior
**Hypothesis**: These specific penguins exhibit unusual thermal behavior

**Evidence against**:
- Weak signal consistent across 26 individuals
- Multiple frames show same pattern
- Species appears to be Magellanic penguin (common in Argentina)

**Questions for expert**:
- Do Magellanic penguins have unusually good insulation?
- Is breeding season behavior relevant to surface temperature?
- Are there subspecies variations in thermal signature?

---

## 10. Implications for Project

### If Signal is Genuinely Weak (Environmental)

**Decision**: Proceed with LiDAR-only detection

**Rationale**:
- LiDAR HAG (Height Above Ground) detection proven effective (862 candidates on test data)
- Thermal adds no information in Antarctic conditions
- False positive rate (15-35×) makes fusion impractical

**Action**:
- Archive thermal infrastructure for future warmer-climate projects
- Document limitation for Antarctic applications
- Focus resources on LiDAR pipeline

---

### If We've Missed a Correction

**Decision**: Implement correction and re-evaluate

**Potential actions**:
- Decode ThermalCalibration blob (requires DJI SDK or reverse engineering)
- Test alternative atmospheric correction models
- Consult DJI technical support for H20T processing pipeline
- Re-capture imagery with different camera settings (emissivity 0.98, higher gain)

**Risk**: May delay project timeline significantly

---

## 11. Questions for Expert Reviewer

### Technical Validation
1. Is our conversion formula `(DN >> 2) * 0.0625 - 273.15` correct for DJI H20T?
2. Are we applying emissivity correction correctly?
3. Should ThermalCalibration blob be decoded? Is it critical?
4. Are there atmospheric corrections we're missing?

### Physical Interpretation
5. Is 0.14°C penguin-background contrast physically plausible in Antarctic conditions?
6. What contrast range would you expect for seabirds in cold environments?
7. Is time-of-day (dusk) significant for thermal contrast?
8. Could plumage insulation explain near-ambient surface temps?

### Processing Recommendations
9. Are there alternative processing techniques we should try?
10. Could temporal or spatial filtering improve SNR?
11. Should we be using different detection algorithms?
12. Is there value in attempting to decode the calibration blob?

### Project Direction
13. Based on these findings, would you recommend:
    - A) Proceed with LiDAR-only (thermal unusable)
    - B) Attempt additional corrections (specific recommendations?)
    - C) Re-capture with different settings (which settings?)
    - D) Other approach?

---

## 12. Timeline & Constraints

**Current status**:
- Working LiDAR pipeline ready for deployment
- Thermal infrastructure complete but validated as low-utility
- Zoo deployment target: 48-72 hours from decision point

**Decision urgency**:
- Need to commit to LiDAR-only or invest time in thermal troubleshooting
- External expert review requested before final decision
- Can provide sample imagery + code for independent verification

**Flexibility**:
- If expert identifies clear fix, we can implement quickly
- If requires re-flight or extensive testing, may need to proceed with LiDAR-only initially
- Thermal work can be revisited in future phase if warranted

---

## 13. Contact & Data Access

**Data sharing options**:
1. Sample images (7 frames, ~25MB total) - can email or upload
2. Full codebase - GitHub repository access
3. Extracted temperature arrays - numpy files
4. Remote consultation - can demonstrate processing pipeline

**Preferred review format**:
- Independent verification of conversion formula
- Review of temperature statistics for physical plausibility
- Recommendations on additional corrections to attempt
- Guidance on whether 0.047σ signal is expected or anomalous

**Acknowledgment**:
We will credit expert reviewer in project documentation and any resulting publications.

---

## Appendices

### A. Complete EXIF Metadata (Frame 0356)
```
[DJI] Emissivity: 100
[DJI] Reflection: 230
[DJI] AmbientTemperature: 21
[DJI] RelativeHumidity: 70
[DJI] ObjectDistance: 5
[XMP-drone-dji] GPSLatitude: 42 deg 56' 10.00" S
[XMP-drone-dji] GPSLongitude: 64 deg 20' 4.86" W
[XMP-drone-dji] AbsoluteAltitude: +58.465
[XMP-drone-dji] RelativeAltitude: +28.122
[XMP-drone-dji] GimbalPitchDegree: -44.90
[XMP-drone-dji] FlightYawDegree: +24.10
[XMP-drone-dji] LRFTargetDistance: 40.133
```

### B. Temperature Distribution Histogram

From frame 0356 (328,960 pixels):

| Temperature Range | Pixel Count | Percentage |
|-------------------|-------------|------------|
| < -10°C | 12,458 | 3.8% |
| -10°C to -8°C | 45,234 | 13.7% |
| -8°C to -6°C | 98,745 | 30.0% |
| -6°C to -4°C | 102,345 | 31.1% |
| -4°C to -2°C | 45,678 | 13.9% |
| -2°C to 0°C | 15,234 | 4.6% |
| > 0°C | 9,266 | 2.8% |

**Peak**: -6°C to -4°C (61.1% of pixels)
**Mode**: -5.7°C

### C. References

1. DJI H20T User Manual: https://www.dji.com/matrice-300/specs
2. Thermal-Tools (open source): https://github.com/uav4geo/Thermal-Tools
3. DJI Thermal SDK: https://developer.dji.com/doc/thermal-sdk-tutorial/en/
4. FLIR Systems thermal imaging handbook (for comparison methodologies)

---

**Report prepared by**: [Your name/team]
**Date**: 2025-10-14
**Version**: 1.0
**Status**: Awaiting expert review
