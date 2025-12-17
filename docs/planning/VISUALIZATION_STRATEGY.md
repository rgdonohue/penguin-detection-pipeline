# Visualization Strategy
## Penguin Detection Pipeline - Argentina Field Data

**Date:** 2025-12-11
**Status:** Draft - Pending Review
**Purpose:** Define visualization requirements for LiDAR-thermal fusion pipeline development

---

## Project Context

We have Argentina field data with GPS ground truth (~3,705 penguins across San Lorenzo and Caleta sites). The pipeline goal is **LiDAR-thermal fusion** for automated penguin detection and counting.

**Primary objective:** Visualizations that help us **develop, validate, and tune** the detection pipeline - not marketing materials.

---

## Existing Visualization Assets

| Asset | Type | Purpose | Status |
|-------|------|---------|--------|
| `qc/panels/caleta_box1_detections.html` | Folium map | LiDAR detections vs satellite | Working |
| `data/interim/lidar_hag_plots/*.png` | Static PNG | HAG raster + detection centroids | Working (36 tiles) |
| `scripts/create_detection_map.py` | Script | GeoJSON → Folium map | Working |
| `scripts/create_hotspot_overlay.py` | Script | Thermal validation overlay | Working |

---

## What Visualizations Do We Actually Need?

### From a GIS/Remote Sensing Perspective:

**1. Detection Validation Maps**
- Overlay detections on high-resolution imagery to visually confirm true/false positives
- Critical for tuning detection parameters
- Need: LiDAR detections, thermal detections, ground truth points (when available)

**2. Sensor Alignment / Registration QC**
- Verify LiDAR and thermal imagery are properly co-registered
- Show same area from both sensors side-by-side or overlaid
- Identify systematic offsets before fusion

**3. HAG/Temperature Distribution Analysis**
- Histograms and spatial plots showing where penguin-like signatures occur
- Help set detection thresholds
- Compare distributions across sites/conditions

**4. Coverage Maps**
- Show which areas have LiDAR coverage, thermal coverage, or both
- Identify gaps and overlaps
- Plan processing priorities

### From a Penguin Biology Perspective:

**1. Spatial Distribution Patterns**
- Where are penguins clustered vs. dispersed?
- Are there habitat associations (caves, plains, vegetation)?
- Does detection density match expected colony structure?

**2. Detection Size/Shape Analysis**
- Are detections consistent with individual penguin dimensions (~0.3-0.5m)?
- Identify potential false positives (rocks, vegetation) by morphology
- Flag potential clusters (multiple penguins in one detection)

**3. Ground Truth Comparison**
- Direct comparison: GPS waypoint locations vs. automated detections
- Calculate detection rates, false positive rates
- Identify what the algorithm misses and why

---

## Proposed Visualization Products

### Tier 1: Essential for Pipeline Development

| Product | Description | Script Exists? |
|---------|-------------|----------------|
| **Detection QC Map** | Single-site folium map: detections + satellite + optional ground truth | Yes (`create_detection_map.py`) |
| **HAG Detection Plot** | Static plot showing HAG raster with detection overlay | Yes (built into `run_lidar_hag.py`) |
| **Thermal Hotspot Overlay** | Thermal image with ground truth circles + detected hotspots | Yes (`create_hotspot_overlay.py`) |

### Tier 2: Needed for Validation

| Product | Description | Script Exists? |
|---------|-------------|----------------|
| **Multi-layer QC Map** | Folium map with toggleable layers: LiDAR, thermal, ground truth | No - extend `create_detection_map.py` |
| **Detection Statistics Panel** | Per-tile summary: count, density, HAG distribution | No |
| **Ground Truth Accuracy Report** | Precision/recall by site when ground truth available | No |

### Tier 3: Nice to Have (Later)

| Product | Description | Script Exists? |
|---------|-------------|----------------|
| **Site Overview Dashboard** | Multi-site comparison (counts, densities, coverage) | No |
| **Fusion Venn Diagram** | LiDAR-only vs. Thermal-only vs. Both detections | No |
| **Temporal Analysis** | If repeat flights exist, show consistency | No |

---

## Technical Approach

### Web Maps (Folium)
- Best for: Interactive exploration, ground-truthing, client demos
- Layers: Satellite basemap, detection points, ground truth polygons/points
- Output: Self-contained HTML files

### Static Plots (Matplotlib)
- Best for: Reports, batch QC, parameter tuning
- Examples: HAG histograms, detection size distributions, accuracy plots
- Output: PNG files in `qc/panels/` or alongside data

### Data Outputs
- GeoJSON/GeoPackage for detections (for loading in QGIS/GIS software)
- CSV summaries for statistics
- JSON for structured results

---

## Questions to Resolve

1. **What ground truth do we have ready to use?**
   - San Lorenzo GPS waypoints are extracted but not yet georeferenced to pixels
   - Caleta box counts have known penguin counts but no per-penguin coordinates

2. **What's the priority visualization need right now?**
   - Validating LiDAR detections on Argentina data?
   - Comparing LiDAR to thermal for same area?
   - Something else?

3. **Who is the audience?**
   - Just us (pipeline development)?
   - Client stakeholder updates?
   - Both?

---

## Next Steps

1. **Review this document** - Does this capture what we need?
2. **Prioritize** - What's the most valuable visualization to build next?
3. **Identify data gaps** - What inputs are missing for priority visualizations?
4. **Build incrementally** - Extend existing scripts rather than creating new ones

---

## Related Files

- `scripts/create_detection_map.py` - Existing folium map generator
- `scripts/create_hotspot_overlay.py` - Thermal validation
- `data/processed/san_lorenzo_waypoints.csv` - Extracted GPS waypoints
- `data/processed/san_lorenzo_analysis.json` - Count/density analysis

---

*Draft created: 2025-12-11*
*Pending: User review and prioritization*
