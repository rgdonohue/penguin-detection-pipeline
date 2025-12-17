# Senior GIS Analyst Assessment
## Penguin Detection Pipeline v4.0

**Date:** 2025-12-09
**Analyst:** External GIS/Remote Sensing Review
**Purpose:** Evaluate project state and gameplan for Argentina field data integration

---

## Executive Summary

The Penguin Detection Pipeline v4.0 is a well-architected system with **production-ready LiDAR detection** and **thermal infrastructure that remains blocked by calibration issues**. Argentina field observations provide **~3,705 total penguin counts** across sites (not georeferenced point locations); turning those counts into usable thermal ground truth still requires GPS→image/CRS mapping.

**Bottom Line:** Deploy LiDAR immediately (with TrueView 515 parameter check). Treat thermal as experimental context only until calibration and ground truth gaps are resolved.

---

## Project Maturity Assessment

| Component | Status | Confidence | Evidence |
|-----------|--------|------------|----------|
| **LiDAR Detection** | ✅ Production-ready | High | 802 detections reproducible, guardrails in `tests/test_golden_aoi.py` |
| **Thermal Extraction** | ✅ Infrastructure complete | Medium | 16-bit radiometric working, H20T + H30T supported |
| **Thermal Detection** | ⚠️ Research phase | Low | F1 scores 0.02-0.30 (frame-dependent), ~9°C calibration offset |
| **Fusion Pipeline** | ✅ Partial | Medium | `pipelines/fusion.py` implements KD-tree join (requires CRS `x/y` inputs) |
| **Ground Truth** | 🔄 Partially complete | Medium | Legacy: 60/137 (44%); Argentina: ~3,705 counts (not point locations) |

---

## Technical Findings

### 1. LiDAR Pipeline (Production Ready)

**Strengths:**
- Deterministic outputs (802 ± 5 detections on golden AOI)
- Comprehensive parameter tuning for Magellanic penguins (0.2-0.6m HAG)
- Morphological filtering with watershed splitting for clustered penguins
- Full provenance tracking and QC visualization
- Streaming architecture handles large tiles (5 GB/minute throughput)

**Gaps:**
- TrueView 515 (Argentina sensor) untested - may need parameter retune
- Full dataset (cloud0-4.las, 35 GB) not yet processed

**Parameters (Validated):**
```
--cell-res 0.25      # Grid resolution (meters)
--hag-min 0.2        # Minimum penguin height
--hag-max 0.6        # Maximum penguin height
--min-area-cells 2   # ~0.125 m² minimum
--max-area-cells 80  # ~5 m² maximum
--connectivity 2     # 8-connected regions
```

### 2. Thermal Pipeline (Research Phase)

**What Works:**
- 16-bit radiometric extraction from DJI RJPEG format
- Camera model and pose extraction from EXIF
- DSM-to-pixel back-projection for orthorectification
- Grid alignment validation (frame 0356: ratio=1.0, offsets=0.0)
- Auto-detection of H30T high-contrast mode (scale 96.0 vs 64.0)

**Critical Issues:**

| Issue | Impact | Mitigation Status |
|-------|--------|-------------------|
| ~9°C calibration offset | Absolute temperatures incorrect | Unresolved - 3 approaches documented |
| Variable thermal contrast | 0.14°C to 11°C between frames | Characterized, frame-dependent |
| Incomplete ground truth | Only 60/137 (44%) validated | 4 frames remaining (77 penguins) |
| Detection performance | F1 0.02-0.30 depending on contrast | Not production-viable |

**Transfer Function (Validated):**
```python
temperature_celsius = (DN >> 2) * 0.0625 - 273.15
```

### 3. Fusion Pipeline (Partially Implemented)

The fusion stage now provides a generic spatial join between LiDAR and thermal detections once both are expressed in the same projected CRS (meters).

**Current Capabilities:**
- Spatial join: LiDAR candidates + thermal detections (nearest-neighbor within `match_radius_m`)
- Label classification: Both / LiDAR-only / Thermal-only

**Remaining Work:** thermal pixel→CRS georeferencing; LiDAR-gated thermal scoring; CLI wrapper.

### 4. Argentina Field Data

**Available Ground Truth (~3,705 penguins):**

| Site | Count | Area | Sensors |
|------|-------|------|---------|
| Caleta Tiny Island | 321 | 0.7 ha | DJI L2, H30T |
| Caleta Small Island | 1,557 | 4 ha | DJI L2, H30T |
| San Lorenzo Road | 359 | - | TrueView 515, H30T |
| San Lorenzo Plains | 453 | - | TrueView 515, H30T |
| San Lorenzo Caves | 908 | - | TrueView 515, H30T |
| Box Counts (4 sites) | 107 | - | H30T |

**LiDAR Data Received:**
- San Lorenzo Full: 23 GB .las
- San Lorenzo Box Counts: 1.2 GB + 345 MB
- Caleta sites: Multiple tiles across 4 locations

**Critical Integration Task:**
GPS waypoints (from Lydia's PDF) must be georeferenced to thermal image pixel coordinates. This would increase ground truth from 60 to ~3,765 labeled penguins (62x improvement).

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| TrueView 515 requires major retune | Medium | Medium | Test on sample tile first; parameters may transfer |
| Thermal calibration unfixable | Low | High | Fall back to relative contrast (penguins still warmer) |
| GPS waypoint georeferencing fails | Medium | High | Manual validation; spatial + temporal matching |
| Fusion blocked by thermal | High | Medium | Ship LiDAR-only counts; thermal as supplementary |
| Argentina data quality issues | Low | Medium | QC checks on sample before full processing |

---

## Critical Path Forward

### Phase 1: Immediate (This Week)
1. **Run LiDAR on Argentina sample tile** (San Lorenzo Box Count)
   - Validate TrueView 515 compatibility
   - Retune parameters if point density differs
   - Estimated: 1-2 hours

2. **Complete legacy ground truth** (4 frames, 77 penguins)
   - Manual annotation from PDF
   - Unblocks thermal parameter optimization
   - Estimated: 2-3 hours

### Phase 2: Short-term (1-2 Weeks)
3. **Georeference Argentina GPS waypoints**
   - Extract from PDF → structured format
   - Implement GPS→pixel projection using existing camera model
   - Validate accuracy (<5 pixel error for RTK GPS)
   - Estimated: 9-15 hours

4. **Investigate thermal calibration**
   - Option A: Decode ThermalCalibration blob (32KB)
   - Option B: Apply atmospheric correction (Planck law)
   - Option C: Empirical offset (match to ambient)
   - Estimated: 4-6 hours

### Phase 3: Medium-term (2-4 Weeks)
5. **Optimize thermal detection parameters**
   - Sweep: threshold (0.1-0.5°C), window (5-11px), cluster (1-5px)
   - Target: F1 > 0.1 (vs baseline 0.043)
   - Estimated: 4-6 hours

6. **Full dataset processing**
   - LiDAR: 5 tiles, ~35 GB legacy + 25 GB Argentina
   - Thermal: ~1533 frames (batch processing)
   - Estimated: 4-8 hours runtime

7. **Implement fusion pipeline**
   - `pipelines/fusion.py` library
   - `scripts/run_fusion_join.py` CLI
   - Test coverage in `tests/test_fusion.py`
   - Estimated: 6-8 hours

---

## MCP Tool Integration Recommendations

For enhanced GIS/remote sensing capabilities, integrate these Model Context Protocol servers:

### 1. GDAL-MCP (Highest Priority)
**Repository:** [Wayfinder-Foundry/gdal-mcp](https://github.com/Wayfinder-Foundry/gdal-mcp)

**Capabilities:**
- Rasterio/GeoPandas/PyProj operations via Claude
- CRS transformations (critical for GPS→pixel projection)
- Raster metadata inspection and format conversion
- Vector clipping, buffer operations

**Installation:**
```bash
uvx --from gdal-mcp gdal --transport stdio
```

**Value for This Project:**
- Accelerate Argentina data integration
- Automate CRS transforms between WGS84 and EPSG:32720
- Raster statistics for thermal QC

### 2. GIS-MCP (Recommended)
**Repository:** [mahdin75/gis-mcp](https://github.com/mahdin75/gis-mcp)

**Capabilities:**
- 89 geospatial functions (Shapely, GeoPandas, PySAL)
- Geometric operations, coordinate transforms
- Spatial statistics and analysis

**Value for This Project:**
- Fusion analysis (spatial joins, buffers)
- Ground truth validation (point-in-polygon)
- Detection clustering analysis

### 3. QGIS-MCP (Optional)
**Repository:** [jjsantos01/qgis_mcp](https://github.com/jjsantos01/qgis_mcp)

**Capabilities:**
- Control QGIS Desktop from Claude
- Visualization and cartography
- PyQGIS code execution

**Value for This Project:**
- QC panel generation
- Client-ready map outputs
- Interactive data exploration

### Configuration Example
```json
// ~/.claude/mcp_servers.json
{
  "mcpServers": {
    "gdal-mcp": {
      "command": "uvx",
      "args": ["--from", "gdal-mcp", "gdal", "--transport", "stdio"],
      "env": {
        "GDAL_MCP_WORKSPACES": "/Users/richard/Documents/projects/penguins-4.0/data"
      }
    }
  }
}
```

---

## Documentation Health

### Strengths
- Comprehensive PRD with clear success criteria
- RUNBOOK follows "only tested commands" principle
- Provenance tracking via harvest manifests
- Single source of truth for tasks (`notes/pipeline_todo.md`)

### Concerns
- Documentation sprawl (40+ markdown files)
- Some overlap between STATUS.md, NEXT_STEPS.md, pipeline_todo.md
- Outdated planning docs not archived

### Recommendations
1. Archive `PLAN.md`, `PLAN_103125.md` to `docs/archive/`
2. Consolidate 8 thermal investigation docs into single summary
3. Move experimental scripts to `scripts/archive/`
4. Update RUNBOOK with GDAL installation status

---

## Deliverables Checklist

### Ready Now
- [x] LiDAR detection on legacy golden AOI (802 detections)
- [x] Test suite (12 golden AOI + 5 thermal tests)
- [x] Thermal extraction infrastructure
- [x] Provenance tracking system
- [x] Updated CLAUDE.md with current state

### Blocked
- [ ] Thermal detection with acceptable F1 (blocked by calibration + ground truth)
- [ ] Fusion analysis (blocked by thermal)
- [ ] Full Argentina processing (blocked by TrueView 515 validation)

### Not Started
- [ ] GPS waypoint georeferencing
- [ ] Batch thermal processing on full dataset
- [ ] Client presentation package

---

## Conclusion

The Penguin Detection Pipeline v4.0 is **architecturally sound** with a **production-ready LiDAR component**. The thermal pipeline has solid infrastructure but is blocked by a calibration issue that may require empirical correction rather than first-principles resolution.

**Recommended Deployment Strategy:**
1. **LiDAR-first:** Deploy immediately with TrueView 515 parameter check
2. **Thermal as context:** Use for visual confirmation, not automated counts
3. **Prioritize georeferencing:** The Argentina GPS waypoints are the fastest path to thermal pipeline maturity

The ~3,705 penguins counted in Argentina field observations represent a 62x increase in available ground truth *if* converted into georeferenced labels. The current repository contains 48 GPS boundary/route waypoints; GPS→image/CRS mapping is still required before these counts can drive thermal optimisation.

---

**Report Author:** Senior GIS Analyst (External Review)
**Last Updated:** 2025-12-09
**Next Review:** Post-Argentina LiDAR validation

---

## References

- `PRD.md` - Product requirements document
- `RUNBOOK.md` - Authoritative tested commands
- `docs/reports/STATUS.md` - Current implementation state
- `docs/planning/ARGENTINA_DATA_INTEGRATION_SUMMARY.md` - Field data integration plan
- `docs/planning/GROUND_TRUTH_GEOREFERENCING_PLAN.md` - GPS→pixel projection plan
- `notes/pipeline_todo.md` - Single task tracker
- `CLIENT_STATUS_REPORT_2025-11-20.md` - Client-facing status

### MCP Tool Sources
- [GDAL-MCP GitHub](https://github.com/Wayfinder-Foundry/gdal-mcp)
- [GIS-MCP GitHub](https://github.com/mahdin75/gis-mcp)
- [QGIS-MCP GitHub](https://github.com/jjsantos01/qgis_mcp)
- [CARTO MCP Server](https://carto.com/blog/carto-mcp-server-turn-your-ai-agents-into-geospatial-experts)
