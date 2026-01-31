# Session: Thermal Label Georeferencing — 2026-01-30

## What Was Done

Georeferenced 127 thermal penguin labels from the client-provided labeling CSV to UTM ground coordinates, then spatially matched against LiDAR detections.

## Data Inventory

| Item | Value |
|------|-------|
| Labels CSV | `data/2025/thermal-penguin-labels/labels_my-project-name_2025-12-03-04-07-18.csv` |
| Thermal images | 4 DJI H30T images (1280×1024), Nov 9, 2025 |
| Camera | DJI H30T, focal length 24mm, DFOV ~40° |
| Gimbal pitch | -45° (oblique, all images) |
| GPS status | RTK (per EXIF `Gps Status: RTK`, `Altitude Type: RtkAlt`) |
| Site | Bushes box count area, San Lorenzo |
| Ground truth | 55 penguins (field count) |

### Per-Image EXIF (extracted via exiftool)

| Frame | Lat | Lon | Alt MSL | Alt AGL | Yaw | Pitch |
|-------|-----|-----|---------|---------|-----|-------|
| 0076 | -42.0852775 | -63.8664954 | 59.2m | 35.4m | -88.4° (W) | -45° |
| 0116 | -42.0857238 | -63.8670125 | 56.0m | 32.2m | +1.4° (N) | -45° |
| 0158 | -42.0853613 | -63.8675492 | 58.5m | 34.7m | +89.5° (E) | -45° |
| 0197 | -42.0849066 | -63.8670938 | 59.4m | 35.6m | -179.3° (S) | -45° |

### Label Counts

| Category | Per-Image (varies) | Total | Unique (clustered) |
|----------|-------------------|-------|-------------------|
| Penguin in Burrow | 12-14 | 48 | 12 |
| Penguin Deep in Burrow | 9-10 | 36 | 9 |
| Empty Burrow | 7-8 | 27 | 7 |
| Box Corner | 4 | 16 | 4 (GCPs) |
| **Total** | 31-35 | **127** | **28** |

## Method

1. **Corner matching:** Each image has 4 labeled "Box Corner" pixels and 4 known GPS positions for the Bushes box corners (NW/NE/SE/SW from field notes). Used geometric heuristic based on gimbal yaw to match pixel corners to compass labels (far/near split by Y coordinate, left/right by X relative to viewing direction).

2. **Homography:** Computed per-image 3×3 projective transform (normalized DLT) mapping pixel (u,v) → UTM (easting, northing). Reprojection errors: 0.000m (4 points exactly determine H).

3. **Projection:** Applied homography to all non-corner labels → UTM coordinates.

4. **Multi-view clustering:** Hierarchical clustering (complete linkage, 2.0m radius) merged projections from 4 views into unique physical locations.

5. **LiDAR spatial match:** Ran `run_lidar_hag.py` on `San_Lorenzo_UTM/box_count_11.9.las` (TrueView 515 params: cell_res=0.30, HAG 0.28-0.48, min_area 3, max_area 50, dedupe 0.5m). Matched georeferenced labels to nearest LiDAR detection.

### Script

```bash
python scripts/georeference_thermal_labels.py \
  --labels-csv data/2025/thermal-penguin-labels/labels_my-project-name_2025-12-03-04-07-18.csv \
  --image-dir data/2025/thermal-penguin-labels \
  --out-json data/processed/thermal_labels_georef.json
```

## Results

### Georeferencing Quality

- **21 unique penguins** identified across 4 views
- **Mean 4.0 views per location** — every penguin seen in all 4 images
- **Multi-view spread: mean 1.15m, max 1.88m** — this is the projection accuracy

### LiDAR Detection Rates

15 LiDAR detections within the box area (vs 55 ground truth = 27% raw rate).

Detection rate vs match radius:

| Radius | Penguin in Burrow | Deep in Burrow | All Penguins | Empty Burrow |
|--------|------------------|----------------|-------------|-------------|
| 1.5m | 2/12 (17%) | 4/9 (44%) | 6/21 (29%) | 2/7 |
| **2.0m** | **7/12 (58%)** | **4/9 (44%)** | **11/21 (52%)** | **3/7** |
| 2.5m | 9/12 (75%) | 4/9 (44%) | 13/21 (62%) | 4/7 |
| 4.0m | 11/12 (92%) | 6/9 (67%) | 17/21 (81%) | 7/7 |
| 5.0m | 12/12 (100%) | 8/9 (89%) | 20/21 (95%) | 7/7 |

### Interpretation

At r=2.0m (reasonable for ~1.15m projection error):
- **"Penguin in Burrow" detection: 58%** — partial above-ground signature detectable
- **"Penguin Deep in Burrow" detection: 44%** — lower, as expected for deeper occlusion
- **Empty burrow false detection: 43%** — burrow structure creates HAG signatures
- At r=5m, 1/9 deep-burrow penguins still has NO LiDAR match (truly occluded)

### Unmatched LiDAR Detections

15 LiDAR detections in box, 6-11 matched to labeled penguins (radius-dependent), leaving 4-9 unmatched. These are likely standing/exposed penguins (not labeled — CSV only contains burrow-associated labels) or false positives from rocks/vegetation.

## Corrections and Caveats

### Tile naming vs coordinates (IMPORTANT)

The gameplan (`LIDAR_40_HOUR_GAMEPLAN_2026-01-21.md` line 28-29) maps:
- `San Lorenzo Box Count 11.10 LAS.las` → Bushes (55 penguins)
- `San Lorenzo Box Count 11.9.25 LAS.las` → Caves (32 penguins)

**This naming is WRONG.** Coordinate bounds from the LAS headers show:
- `box_count_11.9` (POSGAR: x 3676359-3676599, y 5338510-5338776) **contains** the Bushes box centroid (3676484, 5338650)
- `box_count_11.10` (POSGAR: x 3675798-3676080, y 5338155-5338460) does **not**

Verified in both POSGAR (EPSG:5345) and UTM (EPSG:32720) projections. The spatial match in this session used the correct tile (11.9).

### Projection accuracy limitations

- The -45° oblique view amplifies projection errors compared to nadir
- Homography assumes flat ground; terrain relief introduces additional error
- Penguin thermal centroid ≠ LiDAR blob centroid (different physical measurement)
- Combined error budget: ~2m, limiting spatial match precision

### Label coverage

- Labels only cover burrow-associated penguins (21 of 55)
- No "standing penguin" category in the labeling
- Cannot compute overall LiDAR precision from this data alone

### Per-image penguin counts vary

Per-image penguin label counts: 22, 21, 24, 22 (not exactly 21 each). The 21 unique count comes from multi-view clustering.

## Camera Model Issue — FIXED

The `pipelines/thermal.py` rotation matrix (`rotation_from_ypr`) produced out-of-frame projections at -45° pitch. Forward-projecting the 4 GPS box corners gave pixel Y values of 10,000-50,000 (image is 1024 pixels tall).

**Root cause:** Missing body-to-camera axis permutation matrix. The intrinsic ZYX rotation `R_ned = Rz(yaw) @ Ry(pitch) @ Rx(roll)` maps *body* frame to NED, but the body frame (NED-aligned at zero angles: x=North, y=East, z=Down) is NOT the camera frame (x=right, y=down, z=forward). At zero gimbal angles (horizontal, facing North):

- Camera-z (forward) = North = body-x
- Camera-x (right) = East = body-y
- Camera-y (down) = Down = body-z

This requires a permutation: `v_body = C @ v_cam` where `C = [[0,0,1],[1,0,0],[0,1,0]]`. The full rotation is `R_cam_to_ned = R_ned @ C`, then `R_cam_to_enu = M @ R_ned @ C` for ENU output.

The old code used `R = M @ R_ned @ M.T` (similarity transform, treating camera as body frame). The fix uses `R = M @ R_ned @ C`.

**Validation:** 16 GCP forward projections (4 box corners × 4 images at -45° pitch) now project within the 1280×1024 image frame. Tests added: 13 rotation-specific tests + 2 GCP validation tests. Full suite: 96 pass, 2 skip.

## Output Files

| File | Contents |
|------|----------|
| `data/processed/thermal_labels_georef.json` | Georeferenced positions (gitignored) |
| `data/interim/lidar_san_lorenzo_utm_detections.json` | LiDAR detection results (gitignored) |
| `scripts/georeference_thermal_labels.py` | Georeferencing script |
