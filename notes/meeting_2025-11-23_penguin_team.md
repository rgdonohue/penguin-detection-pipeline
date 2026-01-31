# Meeting Notes: Penguin Team Discussion
**Date:** ~November 23, 2025
**Participants:** Penguin detection team
**Note Taker:** Richard (rough notes, interpreted)

---

## Raw Notes (as captured)

The following were transcribed from handwritten/verbal notes during the meeting. Interpretations and implications follow.

---

## 1. External Platforms Mentioned

### EarthRanger (Paul Allen Institute / Ai2)

**What it is:** [EarthRanger](https://www.earthranger.com/) is an open-source ecosystem monitoring platform developed by the Allen Institute for AI (Ai2), originally funded by Paul Allen for the Great Elephant Census. It's deployed at 750+ conservation sites tracking 23,000+ animals globally.

**Capabilities:**
- Real-time data aggregation from GPS collars, camera traps, patrol reports, remote sensors
- **API integration** with 100+ tools via robust APIs
- Cloud-hosted (Google Cloud Platform), free for conservation use
- Interactive map visualization of wildlife data

**Relevance to our project:**
- **Potential integration point** for our penguin detection outputs
- Could serve as a deployment platform for field teams to visualize LiDAR/thermal detections in real-time
- API could allow our pipeline to push detection results directly to EarthRanger maps
- Worth investigating: Can we export GeoJSON detections to EarthRanger?

**Action:** Evaluate EarthRanger API for potential output integration

### Skylight (Ai2 - Maritime Monitoring)

**What it is:** [Skylight](https://skylight.global/) is also from Ai2 (Paul Allen's institute), focused on detecting illegal fishing using satellite imagery, vessel tracking, and AI/computer vision.

**Relevance to our project:** Likely **not directly relevant** - this appears to have been mentioned as context about other Allen Institute projects, or potentially for monitoring penguin colony proximity to fishing activity. Unless we're tracking vessel interactions with penguin colonies, this is probably tangential.

**Note:** If the mention was about "fishing monitoring" as threat assessment to penguin populations, this could be relevant for colony health analysis down the line.

---

## 2. Ground Truth & Data Collection Timing

### "Inside the squiggly on the image is the total count"

**Interpretation:** This likely refers to hand-drawn boundary annotations on field images/maps where total penguin counts were recorded. The "squiggly" = polygon boundary, and the count inside represents ground truth for that area.

**Implication:** We may have annotated imagery with polygon counts that could be digitized for validation. Check with field team for original annotated materials.

### "Ground truth was obtained during the day"

**Implication:** Ground truth counts were made during daylight hours. This is standard practice for visual counting but has implications:
- Penguins may be more/less active at different times
- Matches well with LiDAR collection (also daytime)
- **Thermal imaging at different times** introduces temporal mismatch

### "Flights for thermal and lidar were different days, EXCEPT box counts"

**CRITICAL FINDING:** This is significant for data fusion:

| Data Type | Collection Timing | Implication |
|-----------|------------------|-------------|
| LiDAR | Day X | Primary detection source |
| Thermal | Day Y (different) | **Cannot directly fuse with LiDAR** - penguins moved |
| Box Counts | Same day | **CAN do meaningful thermal+LiDAR comparison** |

**Action Items:**
1. Identify which datasets have same-day thermal+LiDAR (box counts only?)
2. Focus fusion validation on box count areas where temporal alignment exists
3. Document temporal offsets for other areas - fusion will have inherent uncertainty

### "Time series may be off (implications for thermal)"

**Interpretation:** Timestamp synchronization between sensors may be unreliable, OR thermal collection occurred at times when penguin thermal signatures differ (e.g., cooler morning vs. warmer midday).

**Implications:**
- The ~9C calibration offset we're seeing may partly be time-of-day related
- Thermal detection F1 scores varying (0.02-0.30) may correlate with collection time
- Need to log collection timestamps and correlate with detection performance

**Action:** Add timestamp analysis to thermal QC pipeline

---

## 3. LiDAR Processing Tools & Workflow

### "Access to high point cloud - see GeoQ"

**Interpretation:** Almost certainly referring to **GeoCue**, the company that makes:
- LP360 (point cloud processing software)
- TrueView 515 (LiDAR sensor used in Argentina deployment)

GeoCue provides access to high-density point clouds through their processing pipeline.

### "LiDAR uses LP360"

**Confirmed:** [LP360](https://www.lp360.com/) is GeoCue's professional LiDAR processing software:
- Desktop software for point cloud exploitation
- Classification tools (ground filtering, vegetation, etc.)
- Works with LAS/LAZ formats
- Has automated classification via ML plugins
- Supports HESAI sensors (which power TrueView 515)

**Relevance:**
- Our pipeline uses PDAL/laspy, which is compatible but different from LP360
- LP360 outputs may have different classification conventions
- If field team processes with LP360, we need to understand their classification workflow

### "Do these look different than the Terra (L2)"

**Interpretation:** Comparing LP360-processed TrueView 515 data vs. DJI Terra-processed L2 data.

**Background from our EQUIPMENT_PROFILE.md:**
- Test data: DJI L2 sensor, processed with DJI Terra 4.5.18
- Deployment data: TrueView 515, processed with LP360

**Key Differences:**

| Aspect | DJI L2 + Terra | TrueView 515 + LP360 |
|--------|---------------|---------------------|
| Point rate | 240,000 pts/sec | 640,000 pts/sec |
| Channels | ? | 32 |
| Classification | DJI Terra auto | LP360 manual/ML |
| Intensity encoding | DJI format | HESAI format |

**Action:** Create comparison analysis between L2 and TrueView 515 outputs when Argentina data arrives

### "Intensities of LP360 in greyscale - is this an issue?"

**Important observation:** LP360 visualizes intensity as greyscale. The concern is whether intensity values differ between sensors.

### "Penguins should have lower intensities"

**Key insight for detection:** Penguin feathers absorb 905nm LiDAR wavelength (relatively low reflectance) compared to:
- Rock/stone: Higher intensity
- Guano: Variable
- Vegetation: Higher intensity

**Detection implication:**
- We could potentially use intensity as an additional filter
- Penguins = low intensity returns in HAG 0.2-0.6m band
- This is not currently used in our pipeline (purely geometric)

**Action:** Add intensity analysis to detection pipeline as supplementary filter

### "See CloudCompare Open Source"

[CloudCompare](https://www.danielgm.net/cc/) is a free, open-source point cloud viewer/processor:
- Supports LAS, E57, PTX formats
- Can visualize intensity as scalar field with custom color ramps
- Has ML classification plugin (3DMASC)
- Good for QC visualization and manual inspection

**Relevance:**
- Free alternative to LP360 for visualization
- Can verify intensity distributions
- Useful for QC panels and manual validation
- Cross-platform (unlike some LP360 versions)

**Action:** Use CloudCompare for intensity QC visualization

---

## 4. Summary: Implications for Project

### Immediate Actions

1. **Temporal alignment audit** - Identify which flights have same-day thermal+LiDAR (critical for fusion)
2. **Intensity analysis** - Add intensity filtering to detection pipeline
3. **CloudCompare QC** - Set up intensity visualization workflow
4. **EarthRanger evaluation** - Can we push detections to EarthRanger API?

### Questions to Clarify with Field Team

1. Which specific flights have same-day thermal and LiDAR?
2. Where are the annotated images with "squiggly" boundary counts?
3. What classification settings were used in LP360?
4. What are the exact timestamps for each data collection?

### Pipeline Changes to Consider

| Enhancement | Priority | Complexity |
|-------------|----------|------------|
| Intensity-based filtering | Medium | Low |
| Timestamp QC checks | High | Low |
| CloudCompare export for QC | Medium | Low |
| EarthRanger API integration | Low | Medium |
| LP360/Terra output comparison | High | Medium |

### Key Risk Identified

**Fusion validation is limited to box count areas** where same-day collection occurred. All other areas have temporal mismatch between thermal and LiDAR, making direct fusion comparison unreliable.

---

## References

- [EarthRanger](https://www.earthranger.com/) - Ai2 wildlife monitoring platform
- [EarthRanger API](https://www.earthranger.com/technology) - Integration documentation
- [Skylight](https://skylight.global/) - Ai2 maritime monitoring (tangential)
- [LP360](https://www.lp360.com/) - GeoCue point cloud software
- [GeoCue](https://geocue.com/) - TrueView 515 manufacturer
- [CloudCompare](https://www.danielgm.net/cc/) - Open source point cloud viewer

---

**Document created:** 2025-01-14
**Status:** Draft - pending field team clarification
