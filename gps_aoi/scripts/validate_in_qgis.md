# QGIS validation checklist

Use this when checking the GeoJSON AOIs in QGIS.

1. **Load layers**
   - Add `gps_aoi/data/output/*_wgs84.geojson` (or `all_aois_combined_wgs84.geojson`).
   - CRS: WGS84 (EPSG:4326).

2. **Basemap**
   - Add a satellite basemap (e.g. XYZ Tile: OpenStreetMap, Google Satellite, or Bing).

3. **Position**
   - Confirm each polygon sits on the expected landform (Caves/Plains on San Lorenzo; Caleta islands on the correct islands).
   - No large offset from visible coastlines or features.

4. **Shape and extent**
   - Polygons follow the intended survey boundary (or convex hull of waypoints) and do not clip the wrong area.
   - For box counts, the buffered point is an acceptable stand-in if true bounds are unknown.

5. **Area**
   - Optional: compute area in the project CRS and compare to expected ha (see WAYPOINT_SOURCES.md).

6. **Attributes**
   - Check that `aoi_id`, `name`, `penguin_count`, and `source` in the attribute table match the Ground Truthing notes.

7. **Issues**
   - Note any misalignments or wrong boundaries in `gps_aoi/docs/WAYPOINT_SOURCES.md` or a short QC log, and adjust waypoints in the CSVs or the extraction logic as needed.
