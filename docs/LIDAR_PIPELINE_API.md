# LiDAR Penguin Detection Pipeline API

## Overview

The LiDAR pipeline detects Magellanic penguins from drone-collected point clouds using Height-Above-Ground (HAG) analysis. The algorithm identifies objects in the 0.2-0.6m height range (typical penguin standing height) with penguin-like size and shape characteristics.

**Script:** `scripts/run_lidar_hag.py`

## Pipeline Stages

```
LAS/LAZ Files → Ground DEM → HAG Grid → Blob Detection → Filtering → Detections
```

### 1. Ground DEM Construction
- Streams LAS points in chunks (memory-efficient)
- Bins points into XY grid cells at specified resolution
- Computes ground surface per cell (min Z or 5th percentile)
- Fills gaps via nearest-neighbor interpolation

### 2. HAG Grid Computation
- Second streaming pass over points
- Computes `HAG = point_z - ground_z` per cell
- Takes max (or 95th percentile) HAG per cell
- Result: 2D raster of maximum object heights

### 3. Blob Detection
- Thresholds HAG within `[hag_min, hag_max]` range
- Morphological opening/closing to clean noise
- Connected component labeling (8-connectivity)
- Optional watershed splitting for clustered penguins

### 4. Shape Filtering
- Area filter: `min_area_cells` to `max_area_cells`
- Circularity: `4π × area / perimeter²` (penguins are ~round)
- Solidity: `area / convex_hull_area` (compact objects)
- Border trim: exclude detections near tile edges
- Optional slope gating (reject steep terrain)

### 5. Cross-Tile Deduplication
- Union-find clustering within `dedupe_radius_m`
- Prevents double-counting at tile boundaries

## Command Line Interface

```bash
python3 scripts/run_lidar_hag.py \
  --data-root <path>        # Folder with LAS/LAZ files
  --out <path.json>         # Output JSON path
  [options]
```

## Parameters Reference

### Core Detection Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--cell-res` | 0.25 | Grid cell size in meters |
| `--hag-min` | 0.2 | Minimum HAG threshold (m) |
| `--hag-max` | 0.6 | Maximum HAG threshold (m) |
| `--min-area-cells` | 2 | Minimum blob size in cells |
| `--max-area-cells` | 80 | Maximum blob size in cells |

### Shape Filters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--circularity-min` | 0.2 | Min circularity (0-1, 1=perfect circle) |
| `--solidity-min` | 0.7 | Min solidity (0-1, 1=convex) |
| `--se-radius-m` | 0.15 | Morphological structuring element radius |

### Advanced Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--ground-method` | min | Ground estimator: `min` or `p05` |
| `--top-method` | p95 | Top surface: `max` or `p95` |
| `--connectivity` | 2 | Labeling connectivity (1=4-conn, 2=8-conn) |
| `--dedupe-radius-m` | None | Cross-tile deduplication radius |
| `--slope-max-deg` | None | Reject if ground slope > N degrees |
| `--border-trim-px` | 0 | Ignore detections N pixels from edge |
| `--chunk-size` | 1000000 | LAS streaming chunk size |

### Watershed Splitting (for clustered penguins)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--watershed` | False | Enable watershed splitting |
| `--h-maxima` | 0.05 | h-maxima seed extraction (m) |
| `--min-split-area-cells` | 12 | Only split blobs >= this size |

### Output Options

| Parameter | Description |
|-----------|-------------|
| `--plots` | Generate HAG + detection PNG per tile |
| `--emit-geojson` | Write GeoJSON per tile |
| `--crs-epsg` / `--crs-wkt` | CRS for input XY coordinates (required for GeoJSON/GPKG outputs) |
| `--geojson-wgs84` | Transform GeoJSON output to EPSG:4326 (requires CRS + pyproj) |
| `--emit-gpkg` | Write GeoPackage with `detections` (+ `detections_deduped` if enabled) |
| `--gpkg-path` | Optional GeoPackage path |
| `--emit-csv` | Write aggregated CSV |
| `--verbose` | Print progress |

## Tuned Parameter Sets

### DJI L2 (Caleta Sites)
```bash
--cell-res 0.25 --hag-min 0.28 --hag-max 0.48 \
--min-area-cells 3 --max-area-cells 60 --dedupe-radius-m 0.5
```
**Accuracy:** ±6% on Caleta Tiny/Small Islands

### TrueView 515 (San Lorenzo Sites)
```bash
--cell-res 0.3 --hag-min 0.28 --hag-max 0.48 \
--min-area-cells 3 --max-area-cells 50 --dedupe-radius-m 0.5
```
**Accuracy:** ~1% on San Lorenzo Box Count 11.9

## Output Format

### JSON Structure
```json
{
  "data_root": "/path/to/data",
  "params": {
    "cell_res": 0.25,
    "hag_min": 0.28,
    "hag_max": 0.48,
    "min_area_cells": 3,
    "max_area_cells": 60
  },
  "files": [
    {
      "path": "/path/to/cloud0.las",
      "count": 192,
      "time_s": 1.23,
      "grid_shape": [400, 350],
      "detections": [
        {
          "row": 123.5,
          "col": 234.2,
          "x": 449164.99,
          "y": 5308574.24,
          "area_cells": 5,
          "area_m2": 0.3125,
          "circularity": 0.85,
          "solidity": 0.92,
          "hag_mean": 0.35,
          "hag_max": 0.48
        }
      ]
    }
  ],
  "total_count": 1473,
  "total_count_deduped": 1450
}
```

### GeoJSON Structure
Each detection becomes a Point feature with properties:
- `area_cells`, `area_m2`
- `circularity`, `solidity`
- `hag_mean`, `hag_max`
- `tile`, `file`, `id` (stable join keys for fusion/audit)

Each GeoJSON includes a `metadata` object describing coordinates:
- `metadata.crs`: `{ "epsg": <int> }` and/or `{ "wkt": "<...>" }` (required unless you pass `--allow-unknown-crs`)
- `metadata.coord_units`: `"meters"` for projected XY, or `"degrees"` when `--geojson-wgs84` is used

If you want strict RFC 7946-style GeoJSON (WGS84 lon/lat), run with `--geojson-wgs84` (requires `--crs-epsg/--crs-wkt`).

## Usage Examples

### Basic Detection
```bash
python3 scripts/run_lidar_hag.py \
  --data-root data/2025/Caleta\ Small\ Island \
  --out data/interim/detections.json
```

### With Plots and GeoJSON
```bash
python3 scripts/run_lidar_hag.py \
  --data-root data/2025/Caleta\ Small\ Island \
  --out data/interim/detections.json \
  --plots --emit-geojson --crs-epsg 32720 --verbose
```

### Production Run (tuned for DJI L2)
```bash
python3 scripts/run_lidar_hag.py \
  --data-root data/2025/Caleta\ Small\ Island \
  --out data/interim/caleta_small_island.json \
  --cell-res 0.25 --hag-min 0.28 --hag-max 0.48 \
  --min-area-cells 3 --max-area-cells 60 \
  --dedupe-radius-m 0.5 \
  --emit-geojson --crs-epsg 32720 --plots --strict-outputs
```

## Algorithm Details

### HAG Calculation
```
For each cell (i,j):
  ground[i,j] = min(Z) for all points in cell
  top[i,j] = max(Z) for all points in cell
  HAG[i,j] = top[i,j] - ground[i,j]
```

### Blob Metrics
```
circularity = 4π × area / perimeter²
solidity = area / convex_hull_area
fill_ratio = area / bounding_box_area
```

### Deduplication
Uses union-find clustering:
1. Build KD-tree of all detection centroids
2. Query neighbors within `dedupe_radius_m`
3. Union overlapping detections
4. Choose one deterministic representative per cluster (stable by `file`, `id`, `x`, `y`)
5. Emit:
   - `total_count_deduped` in the main summary JSON
   - `lidar_hag_detections_deduped.csv` / `lidar_hag_detections_deduped.json` (includes `dedupe_index` for auditability)

## Dependencies

- `laspy>=2.6.1` - LAS/LAZ I/O
- `numpy>=2.0` - Array operations
- `scipy>=1.13` - Spatial operations, morphology
- `scikit-image>=0.24` - Image processing
- `matplotlib>=3.9` - Plotting (optional)

## Validation Results (Argentina 2025)

| Site | Sensor | Ground Truth | Detections | Error |
|------|--------|--------------|------------|-------|
| Caleta Tiny Island | DJI L2 | 321 | 340 | +6% |
| Caleta Small Island | DJI L2 | 1,557 | 1,473 | -5% |
| San Lorenzo Box 11.9 | TrueView 515 | 107 | 108 | +1% |

**Combined Caleta accuracy:** -3.5% (1,813 detected vs 1,878 GT)
