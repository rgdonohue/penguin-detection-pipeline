# Thermal Characterization of Magellanic Penguins in Coastal Patagonia

**Investigation Period**: November 2024
**Location**: Puerto Madryn, Argentina (42°56'S, 64°20'W)
**Equipment**: DJI Zenmuse H20T (640×512 LWIR, ≤50mK NETD)
**Species**: Magellanic penguin (*Spheniscus magellanicus*)
**Last Updated:** 2025-10-17

---

## Executive Summary

We extracted 16-bit radiometric temperatures from seven DJI H20T frames (≈30 m AGL) over a Magellanic penguin colony. Most frames show strong positive contrast for penguins—typically 8–11 °C warmer than surrounding terrain (≈3 σ)—while one low-SNR frame (0356) exhibits only 0.14 °C contrast (0.05 σ). Automated per-penguin detection remains unreliable (best F1 ≈ 0.30), but the thermal layer is valuable for validating LiDAR detections and documenting colony activity.

**What this represents**: Initial thermal signature data from one specific scenario (resting penguins, spring breeding, coastal Patagonia, ~ -6 °C ambient). These are preliminary measurements, not comprehensive species characterization.

**Limitations**:
- Small sample (n=26) from single 21-second observation
- One location, one day, one season, one behavioral state
- 0.14°C contrast is smaller than ±2°C sensor accuracy
- No testing across varied conditions (different seasons, activity levels, weather, other colonies)

**Use these findings as**: Baseline for H20T performance under specific conditions and starting point for expanded study. Not as definitive biological characterization of the species.

---

## Methods and Data Collection

**Data Collection**:
- Location: Single colony site, Puerto Madryn, Argentina
- Timing: Spring breeding season, single day
- Sensor: DJI H20T at ~30m altitude
- Sample: 7 thermal frames over 21 seconds
- Ground truth: 26 visually confirmed penguin locations

We extracted 16-bit radiometric temperature data and compared penguin surface temperatures against surrounding terrain. This limited sample provides initial measurements from one set of environmental conditions.

---

## Primary Findings

### Thermal Measurements
- **Typical contrast (frames 0353/0355)**: Penguins ~8–11 °C warmer than background (≈3 σ)
- **Low-SNR frame (0356)**: 0.14 °C contrast (0.05 σ)
- **Penguin surface temperature (0356)**: -5.56 °C ± 2.21 °C
- **Ground temperature (0356)**: -5.69 °C ± 2.91 °C
- **Scene standard deviation (0356)**: 2.91 °C

### Biological Interpretation

Penguins maintain strong thermal signatures in the majority of sampled frames, but contrast can collapse under certain conditions (e.g., frame 0356). The variability likely reflects a mix of biological factors (activity level, insulation, recent immersion) and environmental context (ambient temperature, wind, substrate).

**Important context**: These measurements represent one location on one day during breeding season. Thermal signatures may vary with:
- Season and weather conditions
- Activity level (resting vs. active)
- Molt stage and feather condition
- Time since water immersion
- Wind exposure and sun angle

The observed 0.14°C contrast establishes detection challenges for this specific scenario but does not constitute comprehensive species-wide characterization.

---

## Detection Analysis

We evaluated baseline hotspot, bilateral-filtered, and local ΔT annulus methods across multiple thresholds. Even with enhancement, F1 scores remain below 0.30 because precision and recall cannot be improved simultaneously.

| Frame | Contrast (ΔT) | Best Method | Precision | Recall | F1 |
|-------|---------------|-------------|-----------|--------|----|
| 0353 (high SNR) | 10.5 °C | Bilateral + 1.5σ | 13.8% | 30.8% | 0.190 |
| 0353 (local ΔT) | 10.5 °C | ΔT annulus 4.0σ | 42.9% | 23.1% | 0.300 |
| 0355 (moderate SNR) | 8.5 °C | Bilateral + 1.5σ | 35.7% | 23.8% | 0.286 |
| 0355 (local ΔT) | 8.5 °C | ΔT annulus 4.0σ | 30.0% | 14.3% | 0.194 |
| 0356 (low SNR) | 0.14 °C | Baseline 0.5σ | 2.2% | 80.8% | 0.022 |
| 0356 (local ΔT) | 0.14 °C | ΔT annulus 2.0σ | 4.9% | 42.3% | 0.088 |

Enhanced preprocessing reduces false positives (especially for high-contrast frames) but at the cost of recall. No tested method achieves both high precision (>50%) and high recall (>80%).

---

## Scientific Value and Applications

### Research Contributions
1. **Initial quantitative measurements** of Magellanic penguin thermal signatures under spring breeding conditions
2. **Detection baseline** for H20T sensor performance on resting penguins at one colony site
3. **Reproducible methodology** for thermal data extraction and analysis
4. **Foundation for expanded study** across seasons, weather conditions, and activity states

### Operational Applications
While individual penguin identification remains challenging with current sensors, thermal imaging provides value for:
- Colony extent mapping and density estimation
- Behavioral pattern documentation (clustering, movement)
- Multi-sensor validation when combined with LiDAR
- Long-term archive for analysis with future sensor improvements

---

## Technical Specifications

**Sensor Performance**:
- Resolution: 640×512 pixels
- Thermal sensitivity: ≤50mK at f/1.0
- Measurement accuracy: ±2°C or ±2% (whichever is greater)

**Data Extraction**:
Temperature values extracted using: `T(°C) = (DN >> 2) × 0.0625 - 273.15`

This formula, validated against multiple thermal datasets, provides consistent relative temperature measurements essential for contrast analysis.

**Internal Consistency**:
- Frame-to-frame variation: 1.92°C (below within-frame variation of 2.91°C)
- Spatial consistency: All 26 penguin locations showed similar thermal signatures within this flight
- Temporal stability: Measurements consistent across 21-second acquisition period

**Measurement Uncertainty**:
- Sensor accuracy: ±2°C absolute (manufacturer spec)
- Measured contrast: 0.14°C (±2.21°C penguin SD, ±2.91°C ground SD)
- **Implication**: The 0.14°C contrast is smaller than measurement uncertainty
- Temperature values are relative within-scene measurements, not absolute calibrated temperatures
- Contrast measurement may include sensor noise, atmospheric effects, and biological variation

**Key Limitations**:
- Sample size: 26 penguins from single 21-second observation
- Spatial: One colony location only
- Temporal: Single day, single season, single time of day
- Behavioral: Resting penguins only (no active/post-foraging samples)
- Environmental: One weather condition (~-6°C ambient, unknown wind/humidity)

**Note**: Consistency within this single acquisition does not validate findings across different environmental conditions or penguin activity states.

---

## Practical Applications of Thermal Data

Even without operational per-penguin detection, thermal imagery complements LiDAR in several ways:

1. **Quality control / validation** – Sample the local thermal patch for each LiDAR detection; strong ΔT (> ~5 °C) increases confidence that the target is a warm-blooded penguin.
2. **False-positive filtering** – LiDAR-height targets with no thermal signature can be flagged for manual review (likely rocks or vegetation).
3. **Colony activity mapping** – Aggregate ΔT to visualise hot/cold quadrants and behavioural hotspots.
4. **Documentation and reporting** – Thermal overlays demonstrate that LiDAR detections correspond to warm-bodied organisms.
5. **Future fusion research** – Archiving 16-bit frames, ΔT maps, and ground-truth CSVs enables evaluation of higher-performance sensors (e.g., DJI H30T, cooled MWIR) and future fusion algorithms once registration is available.

## Field Collection Strategy

- **Capture thermal concurrently with LiDAR**; H30T can record thermal alongside RGB/zoom with negligible extra cost.
- **Prioritise wildlife welfare and LiDAR quality**—maintain the agreed 60–70 m start altitude and step-down protocol; do not compromise LiDAR to optimise thermal contrast.
- **Log camera settings and ambient conditions** (emissivity, reflected temperature, ambient temperature) to support calibration checks.
- **Retain raw 16-bit data and derived ΔT layers** for QA, validation, and behavioural analysis.

---

## Conclusions

Thermal signatures are often strong (ΔT ≈ 8–11 °C) but can collapse in individual frames (ΔT ≈ 0.14 °C). Radiometric extraction is reliable, yet automated per-penguin detection remains non-operational (best F1 ≈ 0.30). Thermal imagery should therefore be treated as a validation and context layer that augments LiDAR rather than a primary counting sensor.

**What we learned**:
- Penguins frequently present detectable positive contrast, but contrast can drop near zero under some conditions.
- Enhanced methods (bilateral filtering, local ΔT annulus) improve precision but still miss the majority of penguins.
- Thermal data is valuable for validating LiDAR detections, filtering false positives, and documenting colony activity.

**What remains unknown**:
- Thermal signatures across seasons, weather conditions, or behavioural states
- Impact of sensor upgrades (DJI H30T, cooled MWIR) or improved registration
- Benefits of LiDAR/thermal fusion once alignment tools are available

Additional sampling across varied conditions would strengthen conclusions about species-wide thermal characteristics.

---

## Recommendations

1. **Population monitoring**: Use LiDAR for counting; integrate thermal as a validation and context layer.
2. **Thermal workflow**: Automate ΔT-based confidence scoring for LiDAR detections when registration is available.
3. **Sensor trials**: Evaluate H30T and cooled MWIR sensors with the multi-condition protocol below.
4. **Data management**: Archive thermal frames and ΔT maps for future fusion research.

### H30T Multi-Condition Sampling Protocol

Given the 4× resolution improvement over H20T, systematically test detection capability under varied conditions:

**Time of Day Variations**:
- Early morning (maximum overnight cooling)
- Midday (maximum solar heating differential)
- Late afternoon (thermal equilibration period)
- If possible, pre-dawn (maximum thermal contrast)

**Activity State Sampling**:
- Resting birds (baseline)
- Active birds (recently moving)
- Post-foraging (wet from ocean)
- Incubating vs. non-incubating
- Adults vs. chicks

**Environmental Conditions**:
- Clear vs. overcast (radiation differences)
- Calm vs. windy (convective cooling)
- Different ambient temperatures
- Various humidity levels

**Data Collection**:
- Document all conditions for each capture
- Maintain consistent altitude with LiDAR
- Capture radiometric data (16-bit TIFF)
- Include concurrent visible imagery
- Record exact time and weather data

This expanded sampling may reveal conditions where thermal detection becomes viable, particularly with H30T's improved resolution.

---

*For complete system documentation, see PENGUIN_DETECTION_PIPELINE_PROJECT_SUMMARY.md*  
*For field requirements, see FIELD_DATA_SPECIFICATIONS.md*
