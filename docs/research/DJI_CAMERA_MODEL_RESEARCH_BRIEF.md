# Research Brief: DJI Drone Camera Model & Angle Conventions

**Date:** 2025-12-17
**Priority:** RESOLVED ✅
**Requested by:** Penguin Detection Pipeline Team
**Deliverable:** Technical report with validated rotation matrix formula

**STATUS UPDATE (2025-12-17):**
- Research report received and analyzed (see `docs/research/DJI Drone Camera Model & Angle Conventions.pdf`)
- Fix implemented in `pipelines/thermal.py:rotation_from_ypr()`
- All unit tests passing (41 passed, 2 skipped)
- Key findings: DJI Gimbal angles are ABSOLUTE to NED frame (not relative to drone)

---

## Executive Summary

We are building a thermal orthorectification pipeline for DJI drone imagery (H20T/H30T sensors). The project previously produced an invalid rotation matrix (determinant = -1) for nadir-pointing cases; the implementation has since been corrected to return proper rotations (determinant = +1) and the unit tests now pass. We still need authoritative documentation on DJI's angle conventions to validate the model against real-world frames.

---

## The Problem

### Current Implementation

Our code in `pipelines/thermal.py` function `rotation_from_ypr()` attempts to build a world→camera rotation matrix from DJI EXIF metadata:

```python
def rotation_from_ypr(yaw_deg: float, pitch_deg: float, roll_deg: float) -> np.ndarray:
    """
    Build world→camera rotation matrix from yaw/pitch/roll.

    Conventions (ASSUMED, NOT VERIFIED):
        - Yaw: North→East (degrees)
        - Pitch: Positive up (degrees)
        - Roll: Right-hand about forward (degrees)
        - Camera axes: x=right, y=down, z=forward
        - World frame: ENU (East-North-Up)
    """
```

### The Bug (FIXED ✅)

For nadir case (camera pointing straight down, `pitch=-90°`):
- Expected: `det(R) = +1` (proper rotation matrix)
- ~~Actual: `det(R) = -1` (reflection matrix)~~ **FIXED**: Now returns +1

~~This causes our test to fail:~~
```python
R = rotation_from_ypr(yaw_deg=0, pitch_deg=-90, roll_deg=0)
assert np.allclose(np.linalg.det(R), 1.0)  # NOW PASSES ✅
```

### Root Cause (CONFIRMED ✅)

The original implementation had multiple errors:
1. **Coordinate System**: DJI uses **NED** (North-East-Down), not ENU
2. **Gimbal Angles**: Gimbal angles are **ABSOLUTE** to NED frame (already stabilized), NOT relative to drone body
3. **Flight+Gimbal Addition**: We were incorrectly adding Flight + Gimbal angles. Correct approach: use Gimbal angles directly
4. **Rotation Sequence**: Correct sequence is intrinsic ZYX (yaw→pitch→roll)

The fix uses proper Euler angle composition in NED frame, then converts to ENU for mapping.

---

## Research Questions

### Q1: DJI XMP Metadata Field Definitions

The thermal images contain these EXIF/XMP fields (extracted via exiftool):

| Field | Example Value | What does it mean? |
|-------|---------------|-------------------|
| `XMP-drone-dji:FlightYawDegree` | 45.0 | ? |
| `XMP-drone-dji:FlightPitchDegree` | 2.5 | ? |
| `XMP-drone-dji:FlightRollDegree` | -0.3 | ? |
| `XMP-drone-dji:GimbalYawDegree` | 0.0 | ? |
| `XMP-drone-dji:GimbalPitchDegree` | -90.0 | ? |
| `XMP-drone-dji:GimbalRollDegree` | 0.0 | ? |
| `XMP-drone-dji:GPSLatitude` | -42.123 | Latitude (WGS84) |
| `XMP-drone-dji:GPSLongitude` | -64.456 | Longitude (WGS84) |
| `XMP-drone-dji:AbsoluteAltitude` | 85.5 | Altitude above ? (MSL? WGS84?) |
| `XMP-drone-dji:RelativeAltitude` | 50.2 | Altitude above takeoff |

**Specific questions:**
1. What is the reference frame for FlightYaw/Pitch/Roll? (NED? Body-fixed? Local tangent plane?)
2. What is the rotation order? (ZYX Euler? ZXY? Quaternion internally?)
3. What does "positive pitch" mean? (Nose up? Nose down?)
4. What does "GimbalPitchDegree = -90" mean? (Camera pointing nadir? Or something else?)
5. Are Flight angles relative to North, or to the drone body?
6. Are Gimbal angles relative to the drone body, or to the world?

### Q2: How to Combine Flight + Gimbal Angles

Our current approach (possibly wrong):
```python
total_yaw = FlightYawDegree + GimbalYawDegree
total_pitch = FlightPitchDegree + GimbalPitchDegree
total_roll = FlightRollDegree + GimbalRollDegree
```

**Questions:**
1. Is simple addition correct, or do we need matrix/quaternion composition?
2. What is the order of rotations? (Flight first, then gimbal? Or vice versa?)
3. Does the gimbal stabilize against flight motion, or add to it?

### Q3: Camera Coordinate System

For the H20T/H30T thermal camera:

**Questions:**
1. What is the camera's native coordinate system?
   - Is +Z forward (into scene)?
   - Is +Y down (toward ground)?
   - Is +X right (toward starboard)?
2. Where is the optical center relative to the GPS antenna?
3. Is there a lever arm offset we should account for?

### Q4: Reference Frame for World Coordinates

**Questions:**
1. Does DJI use NED (North-East-Down) or ENU (East-North-Up)?
2. Is the reference frame local tangent plane at the drone location?
3. How does this interact with the UTM projection we use (EPSG:32720)?

---

## Specific Documentation to Find

### Primary Sources (Most Authoritative)

1. **DJI Mobile SDK Documentation**
   - FlightController state definitions
   - Gimbal state definitions
   - Coordinate system documentation
   - URL: https://developer.dji.com/mobile-sdk/documentation/

2. **DJI Onboard SDK (OSDK) Documentation**
   - Telemetry data definitions
   - Attitude representation
   - URL: https://developer.dji.com/onboard-sdk/documentation/

3. **DJI Payload SDK (PSDK) Documentation**
   - Camera pointing calculations
   - Gimbal control interface
   - URL: https://developer.dji.com/payload-sdk/documentation/

4. **DJI Thermal Analysis Tool (TA3) Documentation**
   - How DJI's own software interprets these angles
   - Any export formats that include rotation matrices

### Secondary Sources

5. **DJI Developer Forum**
   - Search: "gimbal pitch angle convention"
   - Search: "FlightYawDegree reference frame"
   - Search: "thermal camera orthorectification"
   - URL: https://forum.dji.com/

6. **exiftool Documentation**
   - XMP-drone-dji namespace definitions
   - URL: https://exiftool.org/TagNames/DJI.html

7. **Academic Papers**
   - Search: "DJI drone photogrammetry rotation"
   - Search: "DJI Matrice thermal mapping"
   - Search: "UAV thermal imagery georeferencing"

8. **Open Source Implementations**
   - OpenDroneMap: https://github.com/OpenDroneMap/ODM
   - Pix4D technical documentation
   - Any GitHub repo doing DJI thermal orthorectification

---

## Validation Test Cases

If you find documentation, please validate against these scenarios:

### Test Case 1: Nadir (Straight Down)
- **Input:** `FlightYaw=0, FlightPitch=0, FlightRoll=0, GimbalYaw=0, GimbalPitch=-90, GimbalRoll=0`
- **Expected camera pointing:** Straight down (negative Z in ENU, or positive Z in NED)
- **Expected rotation matrix:** Should have det(R) = +1

### Test Case 2: North-Facing Horizontal
- **Input:** `FlightYaw=0, FlightPitch=0, FlightRoll=0, GimbalYaw=0, GimbalPitch=0, GimbalRoll=0`
- **Expected camera pointing:** North, horizontal
- **Expected rotation matrix:** Should have det(R) = +1

### Test Case 3: East-Facing, 45° Down
- **Input:** `FlightYaw=90, FlightPitch=0, FlightRoll=0, GimbalYaw=0, GimbalPitch=-45, GimbalRoll=0`
- **Expected camera pointing:** East, 45° below horizon
- **Expected rotation matrix:** Should have det(R) = +1

### Test Case 4: Flight at Angle + Gimbal Compensation
- **Input:** `FlightYaw=0, FlightPitch=10, FlightRoll=5, GimbalYaw=0, GimbalPitch=-90, GimbalRoll=0`
- **Expected camera pointing:** Still nadir (gimbal stabilizes)? Or tilted?
- **Question:** Does gimbal compensate for flight attitude?

---

## Deliverables Requested

### Minimum Viable Deliverable
1. **Authoritative source** for DJI angle conventions (link + quote)
2. **Confirmed reference frame** (NED or ENU)
3. **Confirmed rotation order** (ZYX, ZXY, etc.)
4. **Confirmed sign conventions** (positive pitch = ?)
5. **Correct formula** for combining Flight + Gimbal angles

### Ideal Deliverable
All of the above, plus:
6. **Working rotation matrix formula** (pseudocode or Python)
7. **Validation** against at least one test case
8. **Reference implementation** (link to validated open-source code)

### Report Format
Please provide findings as a markdown document with:
- Sources cited with URLs
- Direct quotes from documentation
- Any code snippets found
- Confidence level for each finding (High/Medium/Low)
- Remaining uncertainties

---

## Context: How We'll Use This

Once we have the correct conventions, we will:

1. Fix `rotation_from_ypr()` in `pipelines/thermal.py:478-523`
2. Update the docstring with verified conventions
3. Add unit tests for all test cases above
4. Re-enable the thermal orthorectification pipeline

The thermal pipeline is currently blocked because we can't trust the geometric accuracy of our orthorectified outputs.

---

## Equipment in Use

- **Drone:** DJI Matrice 350 RTK (Argentina) / DJI Matrice 300 RTK (legacy)
- **Thermal Camera:** DJI Zenmuse H20T (legacy) / DJI Zenmuse H30T (Argentina)
- **Data Format:** RJPEG with XMP metadata
- **Extraction Tool:** exiftool

---

## Sample Metadata

Here's actual metadata from one of our thermal frames:

```
[XMP-drone-dji]
GPSLatitude                     : -42.0847222222222
GPSLongitude                    : -63.8569444444444
AbsoluteAltitude                : 85.5
RelativeAltitude                : 50.2
FlightYawDegree                 : 156.3
FlightPitchDegree               : 2.1
FlightRollDegree                : -0.4
GimbalYawDegree                 : 0.0
GimbalPitchDegree               : -89.9
GimbalRollDegree                : 0.0
```

This appears to be a nadir shot (GimbalPitch ≈ -90°) with the drone heading roughly SSE (FlightYaw ≈ 156°).

---

## Timeline

- **Urgency:** High (blocking pipeline development)
- **Ideal turnaround:** 1-2 days
- **Acceptable turnaround:** 1 week

---

## Contact

Questions about this brief can be directed to the project team.

---

*Research brief prepared: 2025-12-17*
