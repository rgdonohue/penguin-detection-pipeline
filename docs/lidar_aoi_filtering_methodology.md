# LiDAR AOI Filtering Methodology

## Objective
Introduce an **optional** Area of Interest (AOI) filter for the LiDAR Height-Above-Ground (HAG) detection pipeline so that operators can exclude non-habitat terrain supplied by the client without altering the proven default workflow.

## Scope & Principles
- **Default behaviour remains unchanged**: running the LiDAR pipeline with no AOI input must continue to produce the baseline 862 ± 5 detections on the golden tile.
- **Optional input**: AOI filtering is only activated when a vetted polygon/raster is provided (e.g., `--aoi habitat_polygon.geojson`).
- **Reproducibility**: AOI files are treated as first-class inputs—hashed, recorded in manifests, and referenced in RUNBOOK commands.
- **Auditability**: Both filtered and unfiltered counts are logged so stakeholders can see the effect of the mask.

## Inputs
- LiDAR tiles under `data/legacy_ro/penguin-2.0/data/raw/LiDAR/`.
- Existing HAG configuration (`scripts/run_lidar_hag.py`).
- Client-provided AOI polygon/GeoJSON/GeoPackage defining the colony footprint (optional).
- Golden AOI regression test (`tests/test_golden_aoi.py`) to verify no regressions.

## Workflow Overview
1. **Baseline run (no AOI)**
   ```bash
   make test-lidar
   # or
   python scripts/run_lidar_hag.py \
     --data-root data/legacy_ro/penguin-2.0/data/raw/LiDAR/sample \
     --out data/interim/lidar_golden.json \
     --cell-res 0.25 \
     --hag-min 0.2 --hag-max 0.6 \
     --min-area-cells 2 --max-area-cells 80 \
     --emit-geojson --plots
   ```
   - Confirms 862 detections and captures unfiltered outputs for provenance.

2. **AOI-enabled run**
   ```bash
   python scripts/run_lidar_hag.py \
     --data-root data/legacy_ro/penguin-2.0/data/raw/LiDAR \
     --out data/processed/lidar_aoi.json \
     --cell-res 0.25 \
     --hag-min 0.2 --hag-max 0.6 \
     --min-area-cells 2 --max-area-cells 80 \
     --emit-geojson --plots \
     --aoi data/intake/client_habitat.geojson
   ```
   - Script internally clips detections whose centroids fall outside the AOI; both raw and filtered counts are emitted in the summary JSON.

3. **Logging & provenance**
   - Record the AOI file in `manifests/harvest_manifest.csv` (source path, SHA256, notes).
   - Write a provenance entry noting the AOI hash and filtering effect (`pipelines/utils/provenance.py` helper).

4. **Regression testing**
   - Extend `tests/test_golden_aoi.py` with a case that runs the script with an AOI covering the golden tile and asserts the count still lands at 862 ± 5.
   - Ensure CI runs the AoI-enabled test to guard against future regressions.

## Operator Steps
1. **Obtain/vet AOI polygon**
   - Confirm the client-supplied polygon reflects approved habitat boundaries.
   - Store it under `data/intake/` or another writable directory; record it in the manifest.

2. **Run baseline**
   - Execute the standard LiDAR command (no AOI) and capture counts/plots for comparison.

3. **Run with AOI**
   - Invoke the `--aoi` variant; review the summary JSON for `total_count`, `filtered_count`, and `% filtered`.

4. **Review outputs**
   - Inspect GeoJSON/plots to ensure masking behaves as expected; spot-check that detections near AOI edges are correctly handled.
   - Document any notable reductions in `status.md` (e.g., “AOI mask removed 38% of detections corresponding to off-colony terrain”).

5. **Share with client**
   - Provide both unfiltered and filtered counts, coupled with the AOI polygon hash so stakeholders can trace the exact mask applied.

## Safeguards & Considerations
- **Determinism**: AOI filtering must be pure geometry; avoid heuristic density/slope rules unless separately validated.
- **Archival**: Always keep unmasked detection outputs; filtered results are supplemental.
- **Edge cases**: Ensure AOI polygons account for buffer regions to avoid chopping legitimate detections near the boundary.
- **Performance**: Clipping is lightweight (vector predicate), so runtime impact should be minimal; monitor and document any changes.

## Next Steps
1. Add `--aoi` support to `scripts/run_lidar_hag.py`, leveraging `shapely`/`geopandas` to filter detection centroids.
2. Update RUNBOOK with AOI-enabled command examples and expected outputs.
3. Extend `tests/test_golden_aoi.py` to cover the AOI path.
4. Coordinate with the client to obtain their official habitat polygon and checksum it into the manifest.

