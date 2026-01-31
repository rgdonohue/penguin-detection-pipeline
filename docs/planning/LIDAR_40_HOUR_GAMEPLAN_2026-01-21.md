# LiDAR 40-Hour Gameplan (2026-01-21)

## Context
- Project scope narrowed to LiDAR focus; thermal analysis assigned to another contractor.
- Remaining budget: ~40 hours.
- Key validation issue: LiDAR detection rates inside AOIs are far below ground truth counts.
- Co-managed by Claude Code and Codex with Richard coordinating.

---

## Confirmed Inputs

### Box Count Coordinates (CONFIRMED: Bushes Box, 55 penguins)
The 4-point coordinates from PDF page 4 are **confirmed as the Bushes box count area** based on the attached image showing "Box Count High Density Bushes: 55 Counted Penguins" directly below the coordinate block.

| Corner | Latitude | Longitude | Position |
|--------|----------|-----------|----------|
| 1 | -42.085258 | -63.867123 | Top-Left (NW) |
| 2 | -42.085381 | -63.867161 | Bottom-Left (SW) |
| 3 | -42.085392 | -63.866972 | Bottom-Right (SE) |
| 4 | -42.085273 | -63.866958 | Top-Right (NE) |

Area: ~37,984 m² (0.38 ha) per Google Earth measurement in PDF.

### LiDAR Tile Mapping
| File | Points | CRS | Box Count Area |
|------|--------|-----|----------------|
| `San Lorenzo Box Count 11.10 LAS.las` | 36M | POSGAR 2007 / Argentina 3 | **Bushes** (55 penguins) |
| `San Lorenzo Box Count 11.9.25 LAS.las` | 10M | POSGAR 2007 / Argentina 3 | **Caves** (32 penguins) |
| `San Lorenzo Full LiDAR LAS.las` | 675M | POSGAR 2007 / Argentina 3 | Full site (66 ha) |

### Existing AOI Evaluation Results (Total Count Areas)
| AOI | Ground Truth | LiDAR Detections | Rate | Notes |
|-----|--------------|------------------|------|-------|
| Caves Total | 908 | 263 | 29% | Large area with many burrows |
| Plains Total | 453 | 86 | 19% | Open terrain |

**Important**: These rates are from the **Total Count Areas**, not the smaller Box Count Areas (55 + 32 penguins). Box counts are better validation targets due to smaller area and synchronized counting.

### Thermal Label Distribution (Bushes Box)
From `data/2025/labels_penguins_2025-12-03-04-07-18.csv`:

| Label Type | Count | LiDAR Visibility |
|------------|-------|------------------|
| Penguin in Burrow | 48 | Partial (surface visible) |
| Penguin Deep in Burrow | 36 | **Likely invisible** |
| Empty Burrow | 27 | N/A |
| Box Corner | 16 | N/A (georeferencing) |

**Key insight**: 43% of labeled penguins (36/84) are "Deep in Burrow" and likely invisible to LiDAR. This partially explains the low detection rates.

### Thermal Image Metadata
4 JPGs captured at cardinal yaw angles with LRF targets:

| Image | Yaw | LRF Target | Nearest Corner |
|-------|-----|------------|----------------|
| 0076_T | -88° (W) | -42.08526, -63.86692 | Top-Right |
| 0116_T | +1° (N) | -42.08544, -63.86698 | Bottom-Right |
| 0158_T | +90° (E) | -42.08537, -63.86713 | Bottom-Left |
| 0197_T | -179° (S) | -42.08522, -63.86713 | Top-Left |

All images: Gimbal pitch -45° (oblique), RTK GPS, 1280x1024 resolution.

---

## Key Risks / Unknowns

| Risk | Severity | Mitigation |
|------|----------|------------|
| Caves box count (32) has no GPS corners | Medium | Request from client or derive from map |
| Burrow occlusion limits LiDAR detection ceiling | High | Document as known limitation; thermal fills gap |
| CRS mismatch between datasets | Medium | Verify all outputs in EPSG:5345 for San Lorenzo |
| Homography accuracy depends on corner ordering | Low | Visual verification of corner-to-pixel mapping |

---

## Plan Overview (~40 hours)

### Phase 1: Ground Truth Infrastructure (8-10h)

| Task | Owner | Deliverable |
|------|-------|-------------|
| 1.1 Create Bushes box AOI GeoJSON | Claude | `aoi_san_lorenzo_boxes_epsg5345.geojson` |
| 1.2 Request/derive Caves box coordinates | Richard | Coordinates for 32-penguin area |
| 1.3 Build homography georeferencing script | Codex | `scripts/georeference_thermal_labels.py` |
| 1.4 Output georeferenced labels | Codex | `labels_penguins_georef.geojson` + CSV |

### Phase 2: LiDAR Validation Sprint (14-16h)

| Task | Owner | Deliverable |
|------|-------|-------------|
| 2.1 Run LiDAR detection on Bushes tile | Claude/Codex | Detection JSON + summary |
| 2.2 Run LiDAR detection on Caves tile | Claude/Codex | Detection JSON + summary |
| 2.3 Evaluate detections in box AOIs | Claude/Codex | `box_count_aoi_eval.json` |
| 2.4 Overlay thermal labels on LiDAR detections | Both | Validation comparison |
| 2.5 Classify TP/FP/FN for box areas | Both | Error classification CSV |

### Phase 3: Parameter Tuning & Gap Analysis (8-10h)

| Task | Owner | Deliverable |
|------|-------|-------------|
| 3.1 HAG threshold sensitivity sweep (0.10-0.60m) | Codex | Parameter sweep results |
| 3.2 Area/compactness threshold testing | Codex | Threshold comparison |
| 3.3 Precision/recall analysis | Both | Tradeoff summary |
| 3.4 Document detection ceiling (burrow limitation) | Both | Technical note |

### Phase 4: QC, Visualization & Reporting (6-8h)

| Task | Owner | Deliverable |
|------|-------|-------------|
| 4.1 Generate QC panels | Both | `qc/panels/*.png` |
| 4.2 Create interactive maps | Claude | `qc/panels/*.html` |
| 4.3 Update RUNBOOK.md | Codex | Commands documentation |
| 4.4 Final status report | Both | Client-ready summary |

---

## Visualization & Mapping Artifacts

### Expected Deliverables

#### 1. Box Count Validation Maps (Priority: High)
- **Format**: Interactive HTML (Folium) + static PNG
- **Content**:
  - LiDAR detections as points/polygons
  - Georeferenced thermal labels (color-coded by type)
  - Box AOI boundary overlay
  - Satellite/ortho basemap
- **Purpose**: Visual verification of detection accuracy
- **Location**: `qc/panels/box_count_bushes_validation.html`

#### 2. Detection Classification Map (Priority: High)
- **Format**: Static PNG + GeoJSON
- **Content**:
  - Green markers: True Positives (LiDAR + thermal match)
  - Red markers: False Positives (LiDAR only, no thermal)
  - Yellow markers: False Negatives (thermal only, no LiDAR)
  - Label annotations for "Deep in Burrow" misses
- **Purpose**: Error analysis and detection ceiling documentation
- **Location**: `qc/panels/detection_classification_bushes.png`

#### 3. Parameter Sensitivity Plots (Priority: Medium)
- **Format**: PNG charts
- **Content**:
  - Detection count vs HAG min/max threshold
  - Precision vs recall curves
  - Area threshold impact
- **Purpose**: Document parameter tradeoffs for future tuning
- **Location**: `qc/panels/parameter_sensitivity.png`

#### 4. Site Overview Map (Priority: Medium)
- **Format**: Interactive HTML (Folium)
- **Content**:
  - All San Lorenzo AOIs (Caves, Plains, Boxes)
  - Detection density heatmap
  - Ground truth counts as labels
  - Links to detailed box count maps
- **Purpose**: Client-facing summary of coverage
- **Location**: `qc/panels/san_lorenzo_overview.html`

#### 5. Thermal-LiDAR Overlay Panels (Priority: Medium)
- **Format**: Multi-panel PNG (2x2 grid)
- **Content**:
  - Each thermal image with:
    - Original thermal view
    - Projected LiDAR detections
    - Labeled penguin locations
    - Detection match indicators
- **Purpose**: Per-image validation for methodology documentation
- **Location**: `qc/panels/thermal_lidar_overlay_*.png`

#### 6. Detection Rate Summary Table (Priority: High)
- **Format**: Markdown table + JSON
- **Content**:
  - Per-AOI: ground truth, detections, rate, confidence interval
  - Breakdown by penguin visibility class (surface vs burrow)
  - Comparison: Total Count Areas vs Box Count Areas
- **Purpose**: Quantitative accuracy reporting
- **Location**: `docs/reports/DETECTION_RATE_SUMMARY.md`

### Visualization Tools Available
- `scripts/create_detection_map.py` - Folium web maps from GeoJSON
- `matplotlib` - Static plots and multi-panel figures
- `folium` - Interactive HTML maps with layer controls
- Existing QC infrastructure in `qc/panels/`

---

## Immediate Next Steps

| # | Action | Owner | Blocked By |
|---|--------|-------|------------|
| 1 | Create Bushes box AOI GeoJSON | Claude | None - ready to proceed |
| 2 | Request Caves box coordinates from client | Richard | Client response |
| 3 | Build homography georeferencing script | Codex | None - ready to proceed |
| 4 | Run LiDAR detection on Bushes tile | Claude/Codex | Step 1 |
| 5 | Re-verify 29%/19% detection rates are reproducible | Both | None |

---

## Open Questions / Dependencies

1. **Caves box coordinates**: Do we have GPS corners for the 32-penguin box count area? If not, can client provide or should we derive from the PDF map?

2. **AOI file organization**: Confirmed approach - create separate `aoi_san_lorenzo_boxes_epsg5345.geojson` for box count areas.

3. **Thermal contractor coordination**: If they produce georeferenced thermal detections, we can integrate into fusion validation.

4. **Detection ceiling documentation**: How should we present the "burrow invisibility" limitation to the client? Recommend explicit note that LiDAR cannot detect penguins deep in burrows.

---

## Success Criteria

| Metric | Target | Notes |
|--------|--------|-------|
| Box count AOIs created | 2 (Bushes + Caves) | Caves pending coordinates |
| Thermal labels georeferenced | 127 labels → WGS84 | Via homography |
| Detection rate for Bushes box | Documented with CI | Compare to 55 ground truth |
| TP/FP/FN classification | Complete for Bushes | Per-detection |
| Visualization artifacts | 6 deliverables | Listed above |
| Parameter sensitivity documented | HAG + area thresholds | With tradeoff curves |

---

## Notes

- Box-count areas are the best validation targets because penguins were counted during the flight window, minimizing movement uncertainty.
- The 43% "Deep in Burrow" rate suggests a **detection ceiling of ~57%** even with perfect LiDAR parameters, unless penguins surface.
- Homography georeferencing is viable with 4 corner correspondences per image; accuracy depends on correct corner-to-pixel mapping.
- All San Lorenzo outputs should be in EPSG:5345 (POSGAR 2007 / Argentina 3) for consistency.

---

*Last updated: 2026-01-21*
*Authors: Claude Code, Codex, Richard*
