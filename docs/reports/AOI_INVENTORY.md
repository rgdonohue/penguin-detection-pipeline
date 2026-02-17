# AOI Inventory — Argentina 2025

**Last verified:** 2026-02-04
**Source data:** `data/processed/san_lorenzo_analysis.json`, GPS Ground Truthing Notes 2025 - RD.pdf
**QGIS files:** `data/processed/aoi_qgis/` (all WGS84 / EPSG:4326)

---

## Canonical File Set

| Purpose | File | CRS | Contents |
|---------|------|-----|----------|
| San Lorenzo analysis | `data/processed/aoi_san_lorenzo_epsg5345.geojson` | EPSG:5345 | Caves, Plains, Box Bushes, Road |
| Caleta Tiny analysis | `data/processed/aoi_caleta_tiny_island_epsg32720.geojson` | EPSG:32720 | Tiny Island |
| Caleta Small analysis | `data/processed/aoi_caleta_small_island_epsg32720.geojson` | EPSG:32720 | Small Island |
| Caleta combined | `data/processed/aoi_caleta_islands_epsg32720.geojson` | EPSG:32720 | Tiny + Small |
| Full catalogue (viz) | `data/processed/aoi_catalogue_wgs84.geojson` | WGS84 | All AOIs |
| Per-site QGIS files | `data/processed/aoi_qgis/*.geojson` | WGS84 | Individual files |

---

## Summary

9 survey areas across 2 sites (Caleta Valdés, San Lorenzo). 3,705 penguins total from field counts. 6 of 9 AOIs have polygon geometry; 3 are missing boundaries.

| # | AOI | Field Count | AOI Polygon | Detections | Detection Rate | Actionable? |
|---|-----|-------------|-------------|------------|----------------|-------------|
| 1 | Caleta Tiny Island | 321 | Yes (LiDAR-derived) | 329 | 1.02 | Yes |
| 2 | Caleta Small Island | 1,557 | Yes (LiDAR-derived) | ~1,260 | ~0.81 | Yes |
| 3 | Caleta Box 1 | 8 | **No** | — | — | No |
| 4 | Caleta Box 2 | 12 | **No** | — | — | No |
| 5 | San Lorenzo Caves | 908 | Yes (GPS, 8 waypoints) | 263 | 0.29 | Qualified |
| 6 | San Lorenzo Plains | 453 | Yes (GPS, 38 waypoints) | 86 | 0.19 | Qualified |
| 7 | San Lorenzo Road | 359 | Yes (GPS, 34 waypoints) | 281 | 0.78 | Yes |
| 8 | SL Box Caves | 32 | Yes (GPS, 4 corners) | — | — | Qualified* |
| 9 | SL Box Bushes | 55 | **No coordinates** | — | — | No |

\* Caves box polygon is ~200 m² from GPS corners but PDF measurement shows ~10,000 m²; coords may be interior stakes.

**Actionable** = polygon exists and detection rate is interpretable.
**Qualified** = polygon exists but low detection rates (0.19–0.29) may reflect burrow occlusion, boundary error, or both.

---

## Caleta Valdés (DJI L2 sensor, EPSG:32720)

### 1. Caleta Tiny Island

| Field | Value |
|-------|-------|
| Field count | 321 penguins |
| AOI source | LiDAR footprint (Otsu land core + 7m dilation constrained to data cells) |
| Polygon area | 0.86 ha |
| Reported area | 0.7 ha |
| LiDAR detections | 329 inside AOI (340 total) |
| Detection rate | 1.02 |
| Sensor | DJI L2 |
| GeoJSON (projected) | `data/processed/aoi_caleta_tiny_island_epsg32720.geojson` |
| GeoJSON (WGS84) | `data/processed/aoi_qgis/caleta_tiny_island.geojson` |
| Status | **Production-ready.** Best-performing site. |

**Notes:** Island boundary derived from LiDAR: Otsu threshold identifies the dense land core, then dilation expands to the shoreline constrained to cells with actual LiDAR returns (>=2 pts/cell). Previous polygon (0.53 ha) used aggressive morphological opening that clipped the shoreline. Updated polygon (0.86 ha) extends to the full sandy beach per client request. The 1.02 detection rate (329 vs 321) suggests a small number of false positives on the beach fringe — consistent with the 85-95% precision estimate from spectral analysis.

---

### 2. Caleta Small Island

| Field | Value |
|-------|-------|
| Field count | 1,557 penguins |
| AOI source | LiDAR footprint (grid occupancy + morphology + contour) |
| Polygon area | 6.95 ha |
| Reported area | 4.0 ha |
| LiDAR detections | ~1,260 inside AOI |
| Detection rate | ~0.81 |
| Sensor | DJI L2 |
| GeoJSON (projected) | `data/processed/aoi_caleta_small_island_epsg32720.geojson` |
| GeoJSON (WGS84) | `data/processed/aoi_qgis/caleta_small_island.geojson` |
| Status | **Production-ready.** |

**Notes:** The LiDAR-derived island footprint (6.95 ha) is substantially larger than the reported survey area (4.0 ha). This likely means the field survey covered a portion of the island, not the whole thing. Detection rate is reliable within the surveyed portion. Two additional variants exist: `aoi_caleta_small_island_regenerated.geojson` and `aoi_caleta_small_island_ground_truth_epsg32720.geojson`.

---

### 3. Caleta Box Count 1

| Field | Value |
|-------|-------|
| Field count | 8 penguins |
| AOI source | **None** — screenshot only (Google Maps, PDF pp. 6–7) |
| Polygon area | Unknown |
| Reported area | Unknown (~209 m perimeter) |
| Status | **No geometry. Needs digitizing or client coordinates.** |

**Notes:** Located on the Caleta mainland (not on the islands). Appears to be a small square region. Suspected to be **nested inside Box Count 2** — if confirmed, these 8 penguins are a subset of the 12 in Box 2, not additional. See Issue #1 below.

---

### 4. Caleta Box Count 2

| Field | Value |
|-------|-------|
| Field count | 12 penguins |
| AOI source | **None** — screenshot only (Google Maps, PDF pp. 6–7) |
| Polygon area | Unknown |
| Reported area | Unknown (~439 m perimeter) |
| Status | **No geometry. Needs digitizing or client coordinates.** |

**Notes:** Larger rectangle on Caleta mainland that appears to contain Box 1. Field notes state "only inside rope bounds." If nested, unique count for this area = 12 (not 8 + 12 = 20).

---

## San Lorenzo (TrueView 515 sensor, native EPSG:5345 / POSGAR)

### 5. San Lorenzo Caves (High Density)

| Field | Value |
|-------|-------|
| Field count | 908 penguins |
| AOI source | GPS waypoints (8: start, end, edge) — convex hull |
| Polygon area | 0.60 ha |
| Reported area | 0.60 ha |
| LiDAR detections | 263 inside AOI |
| Detection rate | 0.29 |
| Sensor | TrueView 515 |
| GeoJSON (projected) | `data/processed/aoi_san_lorenzo_epsg5345.geojson` (feature: san_lorenzo_caves) |
| GeoJSON (WGS84) | `data/processed/aoi_qgis/san_lorenzo_caves.geojson` |
| Status | **AOI exists but low detection rate.** |

**Notes:** The 0.29 detection rate is expected at a burrow-dominated cave site. 43% of labeled penguins across Argentina sites were "deep in burrow" — invisible to LiDAR. With only 8 waypoints, the convex hull may also not capture the full survey boundary. The low rate reflects physics (burrow occlusion), not pipeline failure.

---

### 6. San Lorenzo Plains

| Field | Value |
|-------|-------|
| Field count | 453 penguins |
| AOI source | GPS waypoints (38: start, end, top_edge, bottom_edge) — perimeter winding |
| Polygon area | 0.74 ha (computed from polygon) |
| Reported area | 0.98 ha |
| LiDAR detections | 86 inside AOI |
| Detection rate | 0.19 |
| Sensor | TrueView 515 |
| GeoJSON (projected) | `data/processed/aoi_san_lorenzo_epsg5345.geojson` (feature: san_lorenzo_plains) |
| GeoJSON (WGS84) | `data/processed/aoi_qgis/san_lorenzo_plains.geojson` |
| Status | **AOI exists but boundary uncertain.** |

**Notes:** The polygon area (0.74 ha) is 26% smaller than the reported area (0.98 ha). The waypoints appear to be internal transect endpoints rather than the actual survey boundary edges. One longitude may contain a typo (−63.860 should likely be −63.870). These boundary issues compound the already-low detection rate caused by burrow occlusion. Client clarification needed on true survey extent.

---

### 7. San Lorenzo Road

| Field | Value |
|-------|-------|
| Field count | 359 penguins |
| AOI source | GPS waypoints (34) — convex hull (11 vertices) |
| Polygon area | 1.08 ha |
| Reported area | — (not previously documented) |
| LiDAR detections | 281 inside AOI |
| Detection rate | 0.78 |
| Sensor | TrueView 515 |
| GeoJSON (WGS84) | `data/processed/aoi_qgis/san_lorenzo_road.geojson` |
| Also at | `gps_aoi/data/layers/aoi_san_lorenzo_road.geojson` |
| Status | **Production-ready.** Resolved 2026-02-03 after client provided waypoints. |

**Notes:** Originally had zero boundary data. Client provided 34 GPS waypoints (Nov 08, 2025). Convex hull polygon created and validated. Detection rate of 0.78 is strong for a San Lorenzo site — likely open terrain (road corridor) with fewer burrows.

---

### 8. SL Box Count — Caves

| Field | Value |
|-------|-------|
| Field count | 32 penguins (30 effective — 2 walked out between thermal and LiDAR passes) |
| AOI source | 4 GPS corners from PDF p.4 (listed under "Box Count High Density Caves" heading) |
| Polygon area | ~200 m² (computed from GPS corners) |
| Reported area | ~1.0 ha (from PDF measurement: 9,997 m²) |
| GeoJSON (WGS84) | `gps_aoi/data/layers/aoi_san_lorenzo_box_caves.geojson` |
| Status | **Valid but area mismatch.** GPS corners produce ~200 m² vs ~10,000 m² from PDF measurement. Coords may be interior stakes, not full boundary. |

**Notes:** The 4 GPS coordinates were previously misattributed to the Bushes box count (55 penguins). Re-examination of the PDF confirms they appear under the Caves heading. They fall within LiDAR tile 11.9 (Caves area), consistent with this attribution. The thermal penguin labels (`data/2025/thermal-penguin-labels/`) are from 4 H30T images orbiting this location.

---

### 9. SL Box Count — Bushes

| Field | Value |
|-------|-------|
| Field count | 55 penguins |
| AOI source | **None** — no GPS coordinates listed in PDF |
| Polygon area | Unknown |
| Reported area | ~3.8 ha (from PDF satellite measurement: 37,984 m²) |
| Status | **No coordinates.** PDF shows only a satellite image with Google Maps measurement overlay. Awaiting client GPS corners. |

**Notes:** The PDF's Bushes section shows 55 counted penguins with an area of ~3.8 ha but provides no GPS corner coordinates. The 4 coordinates previously assigned here actually belong to the Caves box (see #8 above). The Bushes area is in LiDAR tile 11.10.

---

## Open Issues

### Issue 1: Caleta nested box counts (affects grand total)

Box 1 (8 penguins) appears to be spatially contained within Box 2 (12 penguins). If confirmed, the grand total should be **3,697**, not 3,705.

**Status:** Pending client confirmation.
**Impact:** 8 penguins (~0.2% of total).

### ~~Issue 2: Bushes box GPS in wrong tile~~ RESOLVED

The 4 GPS corners were listed under the Caves heading in the PDF, not Bushes. They correctly fall in tile 11.9 (Caves). The Bushes box has no coordinates at all. Corrected in code and AOI files (2026-02-06).

**Status:** Resolved.

### ~~Issue 3: Caves box count has no corners~~ RESOLVED

The Caves box does have 4 GPS corners from PDF p.4. They were previously misattributed to Bushes. Now correctly assigned. However, the polygon they produce (~200 m²) is much smaller than the PDF measurement (~10,000 m²).

**Status:** Resolved (attribution corrected). Area mismatch remains — client clarification needed on what the 4 coords represent.
**Impact:** 32 penguins (<1% of total) unvalidatable.

### Issue 4: Plains area mismatch

Computed polygon area (0.74 ha) is 26% smaller than reported (0.98 ha). Waypoints may be internal transect points, not survey boundary.

**Status:** Pending client clarification on true boundary.
**Impact:** Detection rate (0.19) may be artificially low if AOI is too small.

### Issue 5: Plains longitude typo

One waypoint has longitude −63.860 instead of likely −63.870 (~1 km offset).

**Status:** Identified. Fix applied in polygon construction.
**Impact:** Minimal if corrected.

---

## File Index

### Per-site GeoJSON files (WGS84, for QGIS)

All files in `data/processed/aoi_qgis/`:

| File | AOI | Has Geometry |
|------|-----|--------------|
| `caleta_tiny_island.geojson` | Caleta Tiny Island | Yes |
| `caleta_small_island.geojson` | Caleta Small Island | Yes |
| `san_lorenzo_caves.geojson` | San Lorenzo Caves | Yes |
| `san_lorenzo_plains.geojson` | San Lorenzo Plains | Yes |
| `san_lorenzo_road.geojson` | San Lorenzo Road | Yes |
| `san_lorenzo_box_bushes.geojson` | SL Box Bushes | Yes (broken — see Issue 2) |
| `all_aois.geojson` | Combined (all 6 above) | Yes |

### Projected CRS files (for pipeline processing)

| File | CRS | Contents |
|------|-----|----------|
| `data/processed/aoi_caleta_tiny_island_epsg32720.geojson` | EPSG:32720 | Caleta Tiny |
| `data/processed/aoi_caleta_small_island_epsg32720.geojson` | EPSG:32720 | Caleta Small |
| `data/processed/aoi_caleta_islands_epsg32720.geojson` | EPSG:32720 | Both Caleta islands |
| `data/processed/aoi_san_lorenzo_epsg5345.geojson` | EPSG:5345 | Caves + Plains + Box Bushes + Road |

### Source and provenance

| File | Purpose |
|------|---------|
| `data/processed/san_lorenzo_analysis.json` | Field counts and density by site |
| `data/processed/san_lorenzo_waypoints.csv` | 48 GPS waypoints (raw) |
| `gps_aoi/data/waypoints/san_lorenzo_road_waypoints.geojson` | Road waypoint source points |
| `docs/reports/CLIENT_STATUS_REPORT_2026-02-02.md` | AOI clarification questions inline |

---

## Deprecated Files

The following files have been superseded and should not be used:

| File | Superseded By | Notes |
|------|---------------|-------|
| `data/processed/aoi_san_lorenzo_boxes_epsg5345.geojson` | `aoi_san_lorenzo_epsg5345.geojson` | Bushes box now included in combined file |
| `data/processed/aoi_san_lorenzo_boxes_wgs84.geojson` | `aoi_catalogue_wgs84.geojson` | Was loaded as duplicate source in catalogue |

---

## Detection Summary by Validation Tier

### Tier 1 — High confidence (well-defined AOI, >0.75 detection rate)

| AOI | Field | Detected | Rate | Notes |
|-----|-------|----------|------|-------|
| Caleta Tiny Island | 321 | 329 | 1.02 | Full shoreline AOI, open terrain |
| Caleta Small Island | 1,557 | ~1,260 | ~0.81 | Island boundary, mixed terrain |
| San Lorenzo Road | 359 | 281 | 0.78 | GPS hull, road corridor |
| **Subtotal** | **2,237** | **~1,870** | **~0.84** | |

### Tier 2 — Low confidence (boundary issues or heavy burrow occlusion)

| AOI | Field | Detected | Rate | Notes |
|-----|-------|----------|------|-------|
| San Lorenzo Caves | 908 | 263 | 0.29 | Cave site, 43% deep in burrow |
| San Lorenzo Plains | 453 | 86 | 0.19 | Area mismatch, transect strip |
| **Subtotal** | **1,361** | **349** | **0.26** | |

### Tier 3 — Not validatable (missing or broken AOI)

| AOI | Field | Notes |
|-----|-------|-------|
| Caleta Box 1 | 8 | No coordinates; possibly nested in Box 2 |
| Caleta Box 2 | 12 | No coordinates |
| SL Box Caves | 32 | No corner coordinates |
| SL Box Bushes | 55 | GPS corners produce wrong polygon |
| **Subtotal** | **107** | 2.9% of grand total |

---

**Grand total field count:** 3,705 (possibly 3,697 if Caleta boxes nested)
**Validatable:** 3,598 (97.1%)
**High-confidence validated:** 2,237 (60.4%)
