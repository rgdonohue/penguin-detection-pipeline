# LiDAR Penguin Detection — Methodology

## 1. Pipeline Overview

The LiDAR detection pipeline identifies Magellanic penguin candidates from drone-collected point clouds using a Height Above Ground (HAG) analysis approach. The pipeline operates in three stages per tile:

1. **Ground DEM estimation** — Stream LAS/LAZ points to build a minimum-Z (or p05 quantile) ground surface on a regular XY grid.
2. **HAG computation** — Stream points again to compute the maximum (or p95) height above the ground DEM per cell.
3. **Detection** — Threshold the HAG grid to a height window consistent with penguin body size, apply morphological cleanup, label connected components, filter by area and shape, and optionally split large blobs via watershed.

Cross-tile deduplication merges detections within a configurable radius at the batch level. All outputs include provenance metadata and CRS information.

**Entry point:** `scripts/run_lidar_hag.py`
**Library functions:** `scripts/run_lidar_hag.py` (self-contained; also importable as `run_lidar_hag`)

## 2. Algorithm Description

### 2.1 Ground DEM Estimation

Points are streamed in chunks (default 1M points) and binned into grid cells. For each cell, the minimum Z value is tracked using an in-place `np.minimum.at` reduction. No-data cells (no points fell within them) are filled via nearest-neighbor interpolation using `scipy.ndimage.distance_transform_edt`.

An alternative `p05` ground method maintains online per-cell 5th-percentile estimates using a streaming quantile update with configurable learning rate. This is more robust to noise in the lowest returns but requires an additional streaming pass worth of state.

### 2.2 HAG Computation

A second streaming pass computes height-above-ground per point (`z - DEM[cell]`) and tracks the per-cell maximum (or p95 quantile via online tracking). The result is a 2D grid where each cell contains the tallest above-ground feature height.

An optional Z-score cap (`--top-zscore-cap`) clips outlier HAG values beyond `mean + cap * std` to suppress noise from birds in flight, power lines, or sensor artifacts.

### 2.3 Detection

1. **Optional smoothing** — Gaussian filter on the HAG grid (disabled by default).
2. **Optional percentile refinement** — Per-cell percentile filter to suppress spike artifacts.
3. **Thresholding** — Binary mask where `hag_min <= HAG <= hag_max`.
4. **Morphological cleanup** — Binary opening then closing with a disk structuring element (radius derived from `se_radius_m / cell_res`). The original threshold mask is re-applied after morphology to prevent over-dilation.
5. **Connected component labeling** — `skimage.measure.label` with configurable connectivity (1=4-connected, 2=8-connected).
6. **Region filtering** — Regions outside `[min_area_cells, max_area_cells]` are rejected. Bounding-box fill ratio < 0.1 rejects extremely elongated shapes. Circularity and solidity thresholds reject irregular shapes.
7. **Optional slope gating** — Ground slope at each region centroid is checked against `slope_max_deg`; detections on steep terrain (cliff faces, burrow walls) are rejected.
8. **Border trimming** — Detections within `border_trim_px` pixels of any grid edge are rejected to avoid edge artifacts.
9. **Optional watershed splitting** — For blobs exceeding `min_split_area_cells`, h-maxima seeds are extracted from the HAG surface and watershed segmentation splits multi-penguin clusters. Each resulting sub-region gets a globally unique label.

### 2.4 Post-Processing

- **Coordinate mapping** — Cell centroids are converted to projected coordinates using the grid origin and cell resolution.
- **Confidence scoring** — Optional `--compute-confidence` assigns a [0, 1] score per detection as the geometric mean of: HAG Gaussian membership (centered 0.35m), area Gaussian membership, and shape score (circularity + solidity weighted combination).
- **Intensity features** — Optional `--extract-intensity` builds a mean-intensity grid and attaches `intensity_mean`, `intensity_min`, `intensity_max` per detection.
- **Cross-tile deduplication** — `--dedupe-radius-m` clusters detections across tiles using cKDTree ball queries and union-find, selecting one representative per cluster by deterministic sort key (file, id, x, y).

## 3. Parameter Reference

### Core Parameters

| Parameter | CLI Flag | Default | Valid Range | Description |
|-----------|----------|---------|-------------|-------------|
| Cell resolution | `--cell-res` | 0.25 | > 0 | Grid cell size in meters |
| HAG minimum | `--hag-min` | 0.20 | >= 0, < hag_max | Minimum height above ground (m) |
| HAG maximum | `--hag-max` | 0.60 | > hag_min | Maximum height above ground (m) |
| Min area (cells) | `--min-area-cells` | 2 | >= 1, < max_area | Minimum blob size in grid cells |
| Max area (cells) | `--max-area-cells` | 80 | > min_area | Maximum blob size in grid cells |
| Chunk size | `--chunk-size` | 1,000,000 | > 0 | Points per streaming chunk |
| Connectivity | `--connectivity` | 2 | {1, 2} | Label connectivity (1=4-conn, 2=8-conn) |

### Ground/Top Surface

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| Ground method | `--ground-method` | min | `min` or `p05` quantile estimator |
| Top method | `--top-method` | p95 | `max` or `p95` quantile estimator |
| Z-score cap | `--top-zscore-cap` | 3.0 | Cap top surface outliers beyond mean + cap*std |
| Quantile LR | `--top-quantile-lr` | 0.05 | Learning rate for online quantile tracking |

### Morphology and Shape

| Parameter | CLI Flag | Default | Valid Range | Description |
|-----------|----------|---------|-------------|-------------|
| SE radius | `--se-radius-m` | 0.15 | >= 0 | Structuring element radius (meters) |
| Circularity min | `--circularity-min` | 0.20 | [0, 1] | Minimum 4*pi*area/perimeter^2 |
| Solidity min | `--solidity-min` | 0.70 | [0, 1] | Minimum area/convex_hull_area |
| Border trim | `--border-trim-px` | 0 | >= 0 | Reject detections within N pixels of edge |
| Refine percentile | `--refine-grid-pct` | None | (0, 100] | Percentile filter for spike suppression |

### Watershed

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| Enable | `--watershed` | off | Enable h-maxima + watershed blob splitting |
| h-maxima height | `--h-maxima` | 0.05 | Height parameter for seed extraction (m) |
| Min split area | `--min-split-area-cells` | 12 | Only split blobs larger than this |

### Terrain and Memory

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| Slope max | `--slope-max-deg` | None | Reject detections on slopes steeper than this |
| Max grid MB | `--max-grid-mb` | 512 | Memory limit per tile grid estimate |
| Skip oversized | `--skip-oversized-tiles` | off | Skip (rather than fail) oversized tiles |
| Dedupe radius | `--dedupe-radius-m` | None | Cross-tile deduplication radius (meters) |

### Output Options

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| Plots | `--plots` | off | Save HAG + detection PNGs |
| GeoJSON | `--emit-geojson` | off | Write per-tile detection GeoJSON |
| GeoPackage | `--emit-gpkg` | off | Write consolidated GeoPackage |
| CSV | `--emit-csv` | off | Write aggregated detections CSV |
| WGS84 output | `--geojson-wgs84` | off | Transform GeoJSON to EPSG:4326 |
| Confidence | `--compute-confidence` | off | Compute per-detection confidence scores |
| Intensity | `--extract-intensity` | off | Extract per-cell intensity features |

## 4. Known Limitations

### Burrow Occlusion (~43% Ceiling)

Thermal label analysis of 84 penguins found 36 (43%) classified as "deep in burrow." These penguins have no above-ground height signature, establishing a theoretical detection ceiling of ~57% for overhead LiDAR even with perfect parameters. This is a fundamental physical constraint, not a pipeline deficiency.

### Adjacent Penguin Merging

Two or more penguins standing close together may produce a single connected component in the HAG grid, especially at 0.25m cell resolution where a penguin body spans only 1-3 cells. Watershed splitting partially addresses this for large blobs but is not a reliable individual counter.

### Blob != Individual

Each detection is the centroid of a thresholded HAG blob. A detection represents a "penguin-sized above-ground feature," not a validated individual penguin. False positives include rocks, vegetation, burrow rims, and guano mounds. False negatives include occluded penguins, penguins lying flat, and penguins on steep terrain filtered by the slope gate.

### AOI Boundary Sensitivity

Detection counts are highly sensitive to the spatial extent used for clipping. San Lorenzo site boundaries are approximate (derived from sparse GPS waypoints) and may include or exclude detections near edges. Caleta island boundaries are more reliable (derived from LiDAR footprint) but still sensitive to shoreline definition.

### Sensor-Specific Tuning

Different LiDAR sensors require different parameter settings. DJI L2 (Caleta) and TrueView 515 (San Lorenzo) have different point densities, noise characteristics, and return patterns. The default parameters are tuned for the legacy Punta Tombo dataset.

## 5. Per-Site Validation Results

| Site | Sensor | Ground Truth | Candidates | Ratio | Cell (m) | HAG Range (m) | Confidence |
|------|--------|------------:|----------:|------:|--------:|-------------:|------------|
| Caleta Tiny Island | DJI L2 | 321 | 315 | 0.98 | 0.25 | 0.28–0.48 | High — closed boundary, LiDAR-derived AOI |
| Caleta Small Island | DJI L2 | 1,557 | 1,255 | 0.81 | 0.25 | 0.28–0.48 | High — LiDAR-derived AOI |
| San Lorenzo Caves | TrueView 515 | 908 | 263 | 0.29 | 0.30 | 0.28–0.48 | Low — approximate AOI, burrow-dominated |
| San Lorenzo Plains | TrueView 515 | 453 | 86 | 0.19 | 0.30 | 0.28–0.48 | Low — approximate AOI, sparse density |

**Legacy benchmark (Punta Tombo):** Golden AOI produces exactly 802 detections with SHA256-verified signature, cell 0.25m, HAG 0.20–0.60m.

### Interpretation Guide

- **Ratio > 0.9:** Pipeline performing well for this site/AOI combination.
- **Ratio 0.5–0.9:** Expected range given burrow occlusion and parameter sensitivity.
- **Ratio < 0.3:** Likely dominated by AOI boundary error, parameter mismatch, or terrain complexity (burrow-heavy sites).

## 6. Quality Gates

| Gate | Criteria | Status |
|------|----------|--------|
| Golden AOI reproducibility | Exactly 802 detections, SHA256 signature match | Passing |
| CRS contracts | Output CRS matches input or explicit override | Passing |
| Grid memory safety | Tile grid estimate vs `--max-grid-mb` limit | Passing |
| Parameter validation | All CLI params checked before processing | Passing |
| Deterministic output | Same inputs → identical JSON for any run | Passing |
| Cross-tile dedup | Union-find clustering, deterministic representative selection | Passing |
