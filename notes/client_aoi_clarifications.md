# AOI Boundary Clarification Request

**Draft email — January 2026**
**To:** Field Team / Conservation Technology Alliance
**From:** Remote Sensing / Data Analysis Team
**Subject:** Clarification needed on survey boundaries for LiDAR validation

---

Hi team,

We've been processing the Argentina 2025 LiDAR data and validating detection counts against the ground truth from the field surveys. The pipeline is producing strong results on sites with well-defined boundaries (Caleta Tiny Island: 98% of field count, Caleta Small: 81%), but we've hit several boundary/AOI issues that are blocking validation on the San Lorenzo sites.

Below is a summary of what we need, grouped by priority.

---

## Critical (Blocks Validation)

These items prevent us from running any meaningful count comparison on affected sites.

### 1. Bushes Box Count — GPS corners fall in wrong LAS tile

The four GPS coordinates labeled "Box Count High Density Bushes: 55 penguins" (p.4 of the field notes PDF) produce a polygon that falls inside LAS tile **11.9** (the Caves area), not tile **11.10** (where the Bushes area should be). The resulting polygon is also ~200 m² — far smaller than the reported 3.8 ha.

**Possible explanations:**
- (a) The coordinates are mislabeled and actually belong to the Caves box count area, or
- (b) They are internal waypoints within the Caves zone, not box corners.

**What we need:** Confirmation of which area these coordinates represent, and correct box corner coordinates for the Bushes site if the above are wrong.

### 2. Road Site — 359 penguins, zero boundary data

The field notes record 359 penguins for "The Road" site, but no GPS waypoints or boundary coordinates were documented. Without any spatial reference, we cannot clip LiDAR detections to this site or compute a detection rate.

**What we need:** Boundary waypoints, corner coordinates, or a digitized polygon on imagery for the Road survey area.

### 3. Caves Box Count — 32 penguins, no GPS corners

The notes reference a box count of 32 penguins in the Caves area, but no corner coordinates are provided. (Note: 2 penguins reportedly walked out between thermal and LiDAR passes.)

**What we need:** Four corner coordinates for the Caves box count polygon.

---

## High Priority (Affects Accuracy)

These items don't fully block validation but reduce our confidence in the results.

### 4. Plains AOI area mismatch — 0.73 ha vs reported 0.98 ha

The perimeter winding of the top/bottom edge waypoints documented for "The Plains" site gives an area of 0.73 ha, which is 26% smaller than the reported 0.98 ha. This likely means the GPS waypoints were recorded at internal transect endpoints rather than at the actual survey boundary edges.

**What we need:** Confirmation of the true survey boundary, ideally as digitized coordinates or annotated imagery showing the full survey extent.

### 5. Plains waypoint longitude typo — likely -63.870, not -63.860

One waypoint in the Plains dataset has longitude approximately -63.860°, which places it about 1 km east of the other waypoints (which are clustered near -63.870°). This is consistent with a single-digit transcription error.

**What we need:** Confirmation that this is a typo and the correct longitude is approximately -63.870°.

### 6. LAS tile naming — 11.9 and 11.10 appear spatially swapped

Based on our spatial analysis, the LAS tile labeled "11.9" covers the area where we'd expect "11.10" (Bushes) to be, and vice versa. This is consistent with the Bushes box GPS issue above — the coordinates may be correct but associated with the wrong tile.

**What we need:** Confirmation of which physical area each tile (11.9, 11.10) covers. A simple annotated map or screenshot from the flight planning software would resolve this.

---

## Low Priority (Metadata / Context)

These don't block current work but would improve interpretation.

### 7. Caleta box count boundaries

Two box counts at Caleta (8 and 12 penguins) lack boundary coordinates. If you have corner GPS points or can identify them on imagery, we can include them in the validation.

### 8. GPS equipment type and accuracy

Were the waypoints collected with RTK-GPS (cm accuracy), consumer-grade GPS (~3-5m), or phone GPS (~5-10m)? This helps us set appropriate tolerance when matching waypoints to LiDAR coordinates.

### 9. Count timing relative to flights

For each site, were the ground truth counts done before, during, or after the drone flights? The Caves box count notes mention 2 penguins walking out between thermal and LiDAR passes — knowing the general timing helps us interpret count differences.

---

## What We've Done So Far

- Processed all San Lorenzo and Caleta LiDAR datasets (754M points, 25.8 GB)
- Built AOI polygons for all sites where waypoints were available
- Validated detection pipeline on Caleta islands (0.81–0.98 candidate/field ratio)
- Identified the boundary issues above through spatial cross-referencing

## What This Unblocks

Resolving the critical items above lets us:
1. Complete the San Lorenzo validation (currently only Caves and Plains are evaluable)
2. Account for ~446 penguins (Road 359 + Caves Box 32 + Bushes Box 55) currently excluded from validation
3. Produce a full per-site accuracy table covering all ~3,705 ground truth penguins

Resolving the high-priority items improves confidence in the San Lorenzo Caves/Plains results and helps us determine whether the low detection rates (0.19–0.29) are primarily due to boundary error or burrow occlusion.

---

Thanks for your help on this. Happy to jump on a call to walk through the spatial diagnostic plots if that would be useful.

Best,
[Data Analysis Team]
