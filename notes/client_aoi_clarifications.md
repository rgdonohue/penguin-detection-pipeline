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

### 1. Caleta Box Counts — Nested polygons, potential double-count

**This is a newly discovered issue.** Based on the Google Maps screenshots in the field notes (pp. 6-7), **Box Count 1 appears to be completely contained inside Box Count 2**. Both are on the mainland near Caleta (not on the islands).

- Box 1: 8 penguins, ~209 m perimeter, small square
- Box 2: 12 penguins, ~439 m perimeter, larger rectangle that contains Box 1

If these are nested, the 8 penguins from Box 1 are a **subset** of the 12 in Box 2 — not additional penguins. This means:
- Current sum (8 + 12 = 20) overcounts by 8
- Correct unique count in that area = 12
- Grand total should be 3,697, not 3,705

The field notes say Box 2 counted "only inside rope bounds" — this suggests Box 1 may be a denser sub-region within Box 2's rope boundary.

**What we need:**
- Confirmation whether Box 1 and Box 2 are nested (subset) or spatially separate
- If nested, which count (8 or 12) represents unique penguins in the area?
- Does the same nested methodology apply to any San Lorenzo box counts?

### 2. Bushes Box Count — GPS corners fall in wrong LAS tile

The four GPS coordinates labeled "Box Count High Density Bushes: 55 penguins" (p.4 of the field notes PDF) produce a polygon that falls inside LAS tile **11.9** (the Caves area), not tile **11.10** (where the Bushes area should be). The resulting polygon is also ~200 m² — far smaller than the reported 3.8 ha.

**Possible explanations:**
- (a) The coordinates are mislabeled and actually belong to the Caves box count area, or
- (b) They are internal waypoints within the Caves zone, not box corners.

**What we need:** Confirmation of which area these coordinates represent, and correct box corner coordinates for the Bushes site if the above are wrong.

### 3. Road Site — ~~359 penguins, zero boundary data~~ RESOLVED

~~The field notes record 359 penguins for "The Road" site, but all coordinate fields are blank.~~

**UPDATE (2026-02-03):** Client provided 34 GPS waypoints. Convex hull polygon created:
- Area: 1.08 ha
- Density: 332 penguins/ha
- AOI file: `gps_aoi/data/layers/aoi_san_lorenzo_road.geojson`
- Waypoints: `gps_aoi/data/waypoints/san_lorenzo_road_waypoints.geojson`

This site is now ready for validation.

### 4. Caves Box Count — 32 penguins, no GPS corners

The notes reference a box count of 32 penguins in the Caves area, but no corner coordinates are provided. (Note: 2 penguins reportedly walked out between thermal and LiDAR passes.)

**What we need:** Four corner coordinates for the Caves box count polygon.

---

## High Priority (Affects Accuracy)

These items don't fully block validation but reduce our confidence in the results.

### 5. Plains AOI area mismatch — 0.73 ha vs reported 0.98 ha

The perimeter winding of the top/bottom edge waypoints documented for "The Plains" site gives an area of 0.73 ha, which is 26% smaller than the reported 0.98 ha. This likely means the GPS waypoints were recorded at internal transect endpoints rather than at the actual survey boundary edges.

**What we need:** Confirmation of the true survey boundary, ideally as digitized coordinates or annotated imagery showing the full survey extent.

### 6. Plains waypoint longitude typo — likely -63.870, not -63.860

One waypoint in the Plains dataset (line 104 in the PDF) has longitude `63.860152 W`, which places it about 1 km east of the other waypoints (clustered near -63.870°). This is a single-digit transcription error — should be `63.870152 W`.

**What we need:** Confirmation that this is a typo and the correct longitude is approximately -63.870°.

### 7. LAS tile naming — 11.9 and 11.10 appear spatially swapped

Based on our spatial analysis, the LAS tile labeled "11.9" covers the area where we'd expect "11.10" (Bushes) to be, and vice versa. This is consistent with the Bushes box GPS issue above — the coordinates may be correct but associated with the wrong tile.

**What we need:** Confirmation of which physical area each tile (11.9, 11.10) covers. A simple annotated map or screenshot from the flight planning software would resolve this.

---

## Low Priority (Metadata / Context)

These don't block current work but would improve interpretation.

### 8. Caleta box count GPS corners

~~Two box counts at Caleta (8 and 12 penguins) lack boundary coordinates.~~ **UPDATE:** Elevated to Critical item #1 due to nested polygon issue.

### 9. GPS equipment type and accuracy

Were the waypoints collected with RTK-GPS (cm accuracy), consumer-grade GPS (~3-5m), or phone GPS (~5-10m)? This helps us set appropriate tolerance when matching waypoints to LiDAR coordinates.

### 10. Count timing relative to flights

For each site, were the ground truth counts done before, during, or after the drone flights? The Caves box count notes mention 2 penguins walking out between thermal and LiDAR passes — knowing the general timing helps us interpret count differences.

---

## What We've Done So Far

- Processed all San Lorenzo and Caleta LiDAR datasets (754M points, 25.8 GB)
- Built AOI polygons for all sites where waypoints were available
- Validated detection pipeline on Caleta islands (0.81–0.98 candidate/field ratio)
- Identified the boundary issues above through spatial cross-referencing

## What This Unblocks

Resolving the critical items above lets us:
1. **Correct the grand total** — If Caleta boxes are nested, the true count is ~3,697 (not 3,705)
2. Complete the San Lorenzo validation (currently only Caves and Plains are evaluable)
3. Account for ~446 penguins (Road 359 + Caves Box 32 + Bushes Box 55) currently excluded from validation
4. Produce a full per-site accuracy table with verified ground truth counts

Resolving the high-priority items improves confidence in the San Lorenzo Caves/Plains results and helps us determine whether the low detection rates (0.19–0.29) are primarily due to boundary error or burrow occlusion.

## Summary of Ground Truth Uncertainty

| Issue | Affected Count | Impact | Status |
|-------|---------------|--------|--------|
| Nested Caleta boxes (if confirmed) | 8 penguins overcounted | Total: 3,705 → 3,697 | **Pending confirmation** |
| Road site (no boundaries) | 359 penguins | 10% of total | **RESOLVED** — AOI created |
| Caves box (no corners) | 32 penguins unvalidatable | <1% of total | Pending |
| Bushes box (wrong coordinates) | 55 penguins unvalidatable | 1.5% of total | Pending |

**Current state:** ~2.5% of ground truth unvalidatable (down from 12% after Road resolution).

---

Thanks for your help on this. Happy to jump on a call to walk through the spatial diagnostic plots if that would be useful.

Best,
[Data Analysis Team]
