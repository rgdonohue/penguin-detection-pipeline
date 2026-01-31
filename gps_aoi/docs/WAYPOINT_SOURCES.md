# Waypoint sources by site

Notes on where GPS data for each AOI comes from in *GPS Ground Truthing Notes 2025 - RD.pdf*.

## Caleta

- **Tiny Island** (321 penguins, 0.7 ha): Boundary waypoints around the island.
- **Small Island** (1,557 penguins, 4 ha): Boundary waypoints around the island.
- **Box Count 1** (8 penguins): Single point or small polygon (rope bounds).
- **Box Count 2** (12 penguins): Single point or small polygon (rope bounds).

## San Lorenzo

- **Caves** (908 penguins): Start/end and right-edge waypoints. Convex hull used to form polygon.
- **Plains** (453 penguins): Top and bottom edge waypoints. Convex hull used.
- **Road** (359 penguins): Start/end waypoints if present in PDF (currently missing in CSV).
- **Box Caves** (32 penguins): Centre or corners of box.
- **Box Bushes** (55 penguins): Centre or corners of box.

## CSV format

Each `data/waypoints/<site_id>.csv` has:

- `lat`, `lon`: decimal degrees (WGS84).
- `point_type`: e.g. `start`, `end`, `edge`, `top_edge`, `bottom_edge` (used for logic in waypoints_to_geojson).
- `description`: optional label.

Rows with empty lat/lon are ignored. Argentina: lat about -42 to -43, lon about -64 to -66.

## San Lorenzo data already in repo

Caves and Plains waypoints were previously transcribed into `data/processed/san_lorenzo_waypoints.csv`. Those have been copied into `gps_aoi/data/waypoints/san_lorenzo_caves.csv` and `san_lorenzo_plains.csv`. Road, box counts, and Caleta waypoints still need to be taken from the PDF and added to the corresponding CSVs.
