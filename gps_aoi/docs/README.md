# GPS AOI Extraction

Extract AOI polygons from GPS boundary waypoints in the client’s Ground Truthing PDF, then produce GeoJSON for QGIS.

## Purpose

LiDAR-derived AOIs (e.g. Caleta Small Island) follow LiDAR coverage, not the surveyed area. This workspace uses **GPS waypoints** from *GPS Ground Truthing Notes 2025 - RD.pdf* to define AOIs and output GeoJSON for checking in QGIS.

## Layout

```
gps_aoi/
  docs/           Process docs and QGIS checklist
  data/
    raw/          Symlink to PDF (GPS_Ground_Truthing_Notes_2025.pdf)
    waypoints/    One CSV per site: lat,lon,point_type,description
    output/       GeoJSON (WGS84) for QGIS
  scripts/
    extract_waypoints.py   Templates + validation
    waypoints_to_geojson.py   CSV → GeoJSON
```

## Workflow

1. **Waypoints**
   - Add or edit CSVs in `data/waypoints/` (from PDF or field notes).
   - Columns: `lat`, `lon`, `point_type`, `description`.
   - Decimal degrees, Argentina: lat ~-42 to -43, lon ~-64 to -66.
   - **Extract from PDF text:** If you have a text export of the Ground Truthing PDF (e.g. `gps_aoi/data/raw/pdf_extract.txt` or `pdftotext ...`), run:
     ```bash
     python gps_aoi/scripts/extract_waypoints.py --from-pdf-text gps_aoi/data/raw/pdf_extract.txt --out-dir gps_aoi/data/waypoints
     ```
     This overwrites Caves, Plains, and Box Bushes CSVs with parsed coordinates (and applies the Plains longitude typo fix). See `docs/WAYPOINT_SOURCES.md`.

2. **Templates**
   ```bash
   cd gps_aoi/scripts && python extract_waypoints.py --templates --out-dir ../data/waypoints
   ```

3. **Validation**
   ```bash
   python extract_waypoints.py --validate ../data/waypoints/san_lorenzo_caves.csv
   ```

4. **GeoJSON**
   From project root:
   ```bash
   python gps_aoi/scripts/waypoints_to_geojson.py \
     --waypoints-dir gps_aoi/data/waypoints \
     --out-dir gps_aoi/data/output
   ```
   From `gps_aoi/scripts/`:
   ```bash
   python waypoints_to_geojson.py
   ```
   Writes per-site `*_wgs84.geojson` and `all_aois_combined_wgs84.geojson` into `data/output/`.

5. **QGIS**
   - Load `data/output/*.geojson` (or the combined file).
   - Add a satellite basemap and check alignment.
   - See `docs/validate_in_qgis.md` for a short checklist.

## Sites

| Site ID | Name | Type |
|---------|------|------|
| caleta_tiny_island | Caleta Tiny Island | boundary |
| caleta_small_island | Caleta Small Island | boundary |
| caleta_box1 | Caleta Box Count 1 | point |
| caleta_box2 | Caleta Box Count 2 | point |
| san_lorenzo_caves | High Density Caves | edge |
| san_lorenzo_plains | The Plains | edge |
| san_lorenzo_road | Road Total Count | edge |
| san_lorenzo_box_caves | Box Caves | point |
| san_lorenzo_box_bushes | Box Bushes | point |

Sites with no valid waypoints are skipped. Point-type sites use a small buffer (default 15 m).

## Dependencies

- Python 3.11+
- pyproj (e.g. `pip install pyproj`)

## After QGIS checks

Once polygons look correct in QGIS, they can be copied into `data/processed/` as the canonical AOIs and wired into the main catalogue/scripts as needed.
