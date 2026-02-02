# Waypoint sources by site

Notes on where GPS data for each AOI comes from in *GPS Ground Truthing Notes 2025 - RD.pdf*.

## Extraction from PDF

Waypoints are encoded in the PDF as decimal degrees with hemisphere (e.g. `42.085273 S, 63.866958 W`). To repopulate CSVs from a text export of the PDF:

```bash
# Export PDF to text (e.g. pdftotext "GPS Ground Truthing Notes 2025 - RD.pdf" pdf_extract.txt)
python gps_aoi/scripts/extract_waypoints.py --from-pdf-text gps_aoi/data/raw/pdf_extract.txt --out-dir gps_aoi/data/waypoints
```

A pre-extracted text snapshot is in `gps_aoi/data/raw/pdf_extract.txt`. The parser applies a known typo fix for Plains: longitude `63.860152` → `63.870152` (outlier ~1 km east of cluster).

## Caleta

- **Tiny Island** (321 penguins, 0.7 ha): Boundary waypoints around the island. *Not present in PDF text; CSV empty.*
- **Small Island** (1,557 penguins, 4 ha): Boundary waypoints around the island. *Not present in PDF text; CSV empty.*
- **Box Count 1** (8 penguins): Single point or small polygon (rope bounds). *Not in PDF; CSV empty.*
- **Box Count 2** (12 penguins): Single point or small polygon (rope bounds). *Not in PDF; CSV empty.*

## San Lorenzo

- **Caves** (908 penguins): Start/end and right-edge waypoints. Polygon: convex hull of all points. Extracted from PDF.
- **Plains** (453 penguins): Top and bottom edge waypoints. Polygon: perimeter winding (top edge W→E, bottom edge E→W) to avoid bowtie; fallback convex hull if edges missing. Extracted from PDF; typo fix applied.
- **Road** (359 penguins): No waypoints documented in PDF (Start:/End:/Along Edges: blank). CSV empty; boundary data needed from field team.
- **Box Caves** (32 penguins): No corner coordinates in PDF. CSV empty.
- **Box Bushes** (55 penguins): Four corners under "COORDINATES:" on p.4 of PDF; extracted. **Caveat:** diagnostic confirms these coords fall inside LAS tile 11.9 (Caves), not 11.10 (Bushes); possible mislabel or internal waypoints—client clarification requested.

## CSV format

Each `data/waypoints/<site_id>.csv` has:

- `lat`, `lon`: decimal degrees (WGS84).
- `point_type`: e.g. `start`, `end`, `edge`, `top_edge`, `bottom_edge`, `point` (used by `waypoints_to_geojson.py` for Plains perimeter and box corners).
- `description`: optional label.

Rows with empty lat/lon are ignored. Argentina: lat about -42 to -43, lon about -64 to -66.

## Polygon construction

- **Plains:** `point_type` `top_edge` and `bottom_edge` are used to build an explicit perimeter (no convex hull).
- **Box Bushes:** Four points with `point_type` `point` form a closed quad in CSV order.
- **Caves / other boundary sites:** Convex hull of all waypoints.
- **Point sites (single coord):** 15 m buffer square.
