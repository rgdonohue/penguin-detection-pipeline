# Thermal–LiDAR Cross-Reference Analysis

Date: 2026-02-02
Site: San Lorenzo Bushes box count area (55 penguins, field count)

## Purpose

Answer two questions:

1. **How well does LiDAR detect burrow-associated penguins?** The thermal labels provide 28 ground truth locations with category information (shallow burrow, deep burrow, empty burrow). Cross-referencing against LiDAR detections gives recall and precision estimates specific to burrow occupancy depth.

2. **Can thermal brightness distinguish penguins from empty burrows?** If the radiometric thermal data shows temperature differences between occupied and empty burrows, thermal could filter LiDAR false positives or detect penguins that LiDAR misses. We tested this without needing absolute temperature calibration — only relative brightness within each frame.

## Data Sources

### Thermal ground truth

| Item | Value |
|------|-------|
| Source CSV | `data/2025/thermal-penguin-labels/labels_my-project-name_2025-12-03-04-07-18.csv` |
| Images | 4 DJI H30T RJPEGs (1280x1024, Nov 9 2025) |
| Gimbal pitch | -45 deg (oblique, all 4 images) |
| GPS | RTK (per EXIF) |
| Total labels | 127 (48 Penguin in Burrow, 36 Penguin Deep in Burrow, 27 Empty Burrow, 16 Box Corner) |
| Unique locations | 28 (after multi-view clustering at 2.0 m radius) |
| Unique penguins | 21 (12 shallow, 9 deep) |
| Unique empty burrows | 7 |
| CRS | EPSG:32720 (UTM 20S) |

### LiDAR detections

| Item | Value |
|------|-------|
| Source tile | San Lorenzo Box Count 11.9.25 LAS (= box_count_11.9.las in UTM) |
| Sensor | TrueView 515 |
| Enriched JSON | `data/interim/san_lorenzo_box_enriched.json` (2,011 detections) |
| Native CRS | EPSG:5345 (POSGAR 2007 / Argentina zone 5) |
| Transformed to | EPSG:32720 (UTM 20S) via pyproj |
| Tile extent | ~177 m x 158 m (2.79 ha) |

### Reference box

The Bushes box count area is a ~14 m x 14 m reference box defined by 4 GPS corner stakes. Box corners in UTM 20S:

| Corner | Easting | Northing |
|--------|---------|----------|
| NW | 428282.59 | 5340393.86 |
| NE | 428296.26 | 5340392.33 |
| SE | 428295.23 | 5340379.11 |
| SW | 428279.59 | 5340380.17 |

Box area: ~193 m^2. The LiDAR tile covers a much larger area (2.79 ha) containing the box.

## Process 1: Thermal Label Georeferencing

**Goal:** Convert pixel coordinates of labeled penguins/burrows to UTM ground coordinates.

**Method:** Homography from box corner GCPs.

1. Each thermal image contains 4 labeled "Box Corner" pixels. The 4 box corners have known UTM positions from field GPS.

2. Per image, match pixel corners to compass corners (NW/NE/SE/SW) using a geometric heuristic based on gimbal yaw angle. The camera yaw determines which compass direction is "forward" in the image, allowing pixel-space ordering (top/bottom, left/right) to be mapped to compass directions.

3. Compute a 3x3 projective homography H (pixel → UTM) using normalized Direct Linear Transform (DLT). With exactly 4 point correspondences, the homography is exactly determined (reprojection error = 0).

4. Apply H to all non-corner label pixel coordinates → UTM easting/northing.

5. Since each penguin is labeled in all 4 images (from 4 different viewing angles), cluster the 4 per-penguin UTM projections using hierarchical clustering (complete linkage, 2.0 m radius) to produce a single location per unique penguin.

**Accuracy:** Mean multi-view spread 1.15 m, max 1.88 m. The spread is dominated by the oblique viewing angle (-45 deg), flat-ground assumption in the homography, and the fact that penguin thermal centroid shifts with viewing angle. Combined error budget is ~2 m.

**Script:** `scripts/georeference_thermal_labels.py`
**Output:** `data/processed/thermal_labels_georef.json`
**Method:** Homography-based georeferencing from box corner GCPs (4 H30T images).

## Process 2: Spatial Cross-Reference (LiDAR vs Thermal GT)

**Goal:** Determine LiDAR recall (what fraction of known penguins does LiDAR detect?) and precision (what fraction of LiDAR detections near known penguins are real?) at a burrow site.

**Method:** Nearest-neighbor spatial matching using scipy cKDTree.

1. Transform all LiDAR detections from EPSG:5345 (POSGAR) to EPSG:32720 (UTM 20S) via pyproj. This is necessary because the enriched LiDAR JSON stores coordinates in the native POSGAR CRS (easting ~3,675,000) while thermal labels are in UTM (easting ~428,000).

2. Build a KD-tree from the 28 thermal ground truth locations.

3. For each LiDAR detection, find the nearest ground truth point. If the distance is within the match radius, classify the detection as matched (and record the GT category). Test at multiple radii (1.0, 1.5, 2.0, 2.5, 3.0, 5.0 m) to assess sensitivity to the error budget.

4. Separately, count LiDAR detections inside the 14 m reference box (point-in-polygon test) for a localized precision estimate.

### Results: Recall by category

| Radius | Penguin in Burrow (12) | Deep in Burrow (9) | All Penguins (21) | Empty Burrow (7) |
|--------|----------------------|-------------------|------------------|-----------------|
| 1.0 m | 1 (8%) | 1 (11%) | 2 (10%) | 2 |
| 1.5 m | 2 (17%) | 3 (33%) | 5 (24%) | 3 |
| **2.0 m** | **6 (50%)** | **3 (33%)** | **9 (43%)** | **4 (57%)** |
| 2.5 m | 6 (50%) | 3 (33%) | 9 (43%) | 5 |
| 3.0 m | 6 (50%) | 3 (33%) | 9 (43%) | 5 |
| 5.0 m | 12 (100%) | 7 (78%) | 19 (90%) | 7 |

At the 2.0 m match radius (consistent with the ~2 m error budget):
- **43% of labeled penguins have a LiDAR detection nearby.**
- Shallow burrow penguins (50%) are detected more often than deep burrow penguins (33%), consistent with the physical expectation that LiDAR detects above-ground signatures.
- Recall saturates at 2.0 m (no improvement from 2.0 to 3.0 m), then jumps again at 5.0 m — the additional matches at large radius are likely coincidental proximity rather than true detections.

### Results: In-box precision

7 LiDAR detections fall inside the 14 m x 14 m reference box. All 7 are within 2 m of a labeled penguin. This gives 100% local precision (n=7), though the sample is too small for a confident estimate.

### Results: Empty burrows as false positive source

4 of 7 (57%) empty burrows have a LiDAR detection within 2 m. This confirms that burrow rim structure creates above-ground height signatures that pass the pipeline's HAG filter, producing false positives that are geometrically indistinguishable from penguin detections.

### Parameter sensitivity note

The cross-reference used the enriched JSON (2,011 detections from one LiDAR parameter set). The January 30 session report used a different run with TrueView 515-specific parameters (cell_res=0.30, HAG 0.28–0.48, min_area 3, max_area 50) and found 15 in-box detections with 52% overall recall at 2 m. The qualitative conclusions are the same: LiDAR recall at burrow sites is 40–55% depending on parameters, precision in-box is high, and empty burrows generate false positives.

**Output:** `data/interim/thermal_lidar_crossref.json`

## Process 3: Thermal Discrimination Proof of Concept

**Goal:** Determine whether relative thermal brightness (temperature above frame background) can distinguish penguins from empty burrows, without requiring absolute temperature calibration.

**Motivation:** The pipeline's ~9 deg C calibration offset is unresolved, but if relative brightness within a single frame separates occupied from empty burrows, absolute calibration is unnecessary for discrimination.

**Method:** Direct pixel sampling from radiometric thermal images.

1. For each of the 4 thermal images, extract the full 16-bit radiometric array using `pipelines/thermal.py:extract_thermal_data()` → float32 Celsius grid.

2. Compute frame background as the median pixel temperature.

3. For each labeled pixel location, sample a 5x5 patch centered on the label and compute the mean. Express as delta = (patch mean) - (frame median).

4. Group deltas by category (Penguin in Burrow, Penguin Deep in Burrow, Empty Burrow) and compare.

5. Additionally, project LiDAR detections into thermal pixel space using the inverse homography (UTM → pixel), sample thermal values, and compare penguin-matched vs unmatched LiDAR detections.

### Results: Label-level thermal separation

| Category | n (across 4 images) | Mean delta | Std | Cohen's d vs Empty |
|----------|-----|------------|-----|-------------------|
| Penguin in Burrow (shallow) | 48 | +0.60 C | 1.32 C | 0.22 (small) |
| Penguin Deep in Burrow | 36 | +0.13 C | 0.77 C | -0.29 |
| Empty Burrow | 27 | +0.39 C | 0.90 C | — |
| **All penguins vs empty** | **84 vs 27** | — | — | **0.04 (negligible)** |

### Results: LiDAR detection thermal signal

LiDAR detections projected into thermal frames and classified by GT match status:

| Group | n (image-projections) | Mean delta | Fraction > 1.0 C |
|-------|----|-----------|-----------------|
| Matched to penguin | 20 | -0.02 C | 0% |
| Matched to empty burrow | 8 | -0.01 C | 12% |
| Unmatched | 153 | +0.06 C | 7% |

Cohen's d (penguin-matched vs unmatched) = -0.17 (wrong direction — penguin-matched LiDAR detections are slightly *cooler*). Top 10% hottest LiDAR detections contain 0 penguin-matched points.

### Interpretation

**Thermal discrimination does not work at this site and camera configuration.**

The physical reason: at -45 deg oblique pitch, the camera views burrow openings from the side. What it sees is the burrow rim and surrounding soil/vegetation, not the penguin's body. An occupied burrow and an empty burrow present nearly identical thermal profiles from this angle. The weak positive signal from "Penguin in Burrow" (+0.6 C) is confounded by empty burrows also reading warm (+0.4 C) — burrow features are warmer than flat ground regardless of penguin presence.

**Output:** `data/interim/thermal_discrimination_poc.json`

## Conclusions

### What LiDAR can and cannot do at burrow sites

LiDAR detects above-ground height signatures. At the San Lorenzo Bushes site:

- **43% of burrow-associated penguins are detected** at a 2 m match radius. This is below the 55-field-count implied by the site, but only 21 of those 55 penguins were labeled (all burrow-associated). Standing/exposed penguins were not labeled and may account for some of the unmatched LiDAR detections.

- **Shallow burrow penguins are detected more often (50%) than deep burrow penguins (33%).** This is the expected physics: penguins sitting at burrow entrances create a partial above-ground signature, while penguins deep in burrows are fully occluded.

- **LiDAR detections in the reference box are real.** 7/7 in-box detections match a labeled penguin (100% local precision, n=7). LiDAR is finding something — the question is completeness, not accuracy.

- **Empty burrow rims cause false positives.** 57% of empty burrows trigger a LiDAR detection. Burrow rim and mound structure creates a HAG signature in the 0.2–0.6 m penguin height band. This is a structural false positive that geometric filters cannot distinguish from a penguin.

### Why thermal does not help (at this site)

The oblique camera angle means thermal sees the burrow cavity exterior, not the penguin body. Occupied and empty burrows have the same thermal signature. This is not a calibration problem or an engineering problem — it is a geometry problem specific to oblique views at burrow sites.

Thermal discrimination *might* work with:
- **Nadir thermal views** looking straight down into burrow openings (untested, would require different data collection)
- **Open-colony sites** where penguins stand exposed on rock (expected 5–10 C contrast, but no labeled data to test)

Neither is available in the current dataset.

### Net assessment for burrow sites

LiDAR alone achieves ~43% recall and high precision at this burrow site. The 57% of penguins it misses are underground and invisible to overhead sensing. Thermal imaging from oblique angles does not close this gap. Operational counting at burrow-heavy sites requires supplementary methods: field-derived burrow occupancy rates as a correction factor, or direct field counts.
