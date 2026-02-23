# LiDAR Project Review (PR-Ready)

Date: 2026-02-23  
Repository: `penguins-4.0`

## Definition Of Done Checklist

- [x] Official reporting mode enforces deterministic defaults (`p05` ground, `max` top).  
  Evidence: `scripts/run_lidar_hag.py:2649-2668`, `scripts/run_lidar_hag.py:2568-2572`.
- [x] Official multi-tile runs require dedupe and fail loudly if missing.  
  Evidence: `scripts/run_lidar_hag.py:2849-2852`, `scripts/run_lidar_hag.py:2902-2906`.
- [x] Raw + deduped + official-labeled counts are emitted.  
  Evidence: `scripts/run_lidar_hag.py:3264-3279`.
- [x] Run manifest is emitted with run status, degraded reasons, warnings, git context, CRS, tile list, AOI metadata, method flags.  
  Evidence: `scripts/run_lidar_hag.py:2851-2894`, `scripts/run_lidar_hag.py:3317-3332`.
- [x] Degraded run logic implemented; official mode exits non-zero unless `--allow-degraded`.  
  Evidence: `scripts/run_lidar_hag.py:2909-2916`, `scripts/run_lidar_hag.py:3349-3355`.
- [x] AOI registry blocking implemented; Bushes AOI marked blocked without geometry edits.  
  Evidence: `manifests/aoi_registry.json`, `docs/process/BLOCKED_AOIS.md`, `scripts/run_lidar_hag.py:2795-2816`.
- [x] Fusion runtime supports thermal window sampling (`mean`, `max`, local `z`) with nodata handling and CRS hard checks.  
  Evidence: `pipelines/fusion.py:58-66`, `pipelines/fusion.py:345-349`, `pipelines/fusion.py:398`, `pipelines/fusion.py:305-312`.
- [x] Synthetic tests added for thermal nodata behavior, window math, CRS mismatch.  
  Evidence: `tests/test_fusion_sampling.py:32-136`.
- [x] Validation harness labels subset evaluation explicitly and emits summary table + radius sensitivity note.  
  Evidence: `scripts/validate_lidar_labeled_subset.py:509-516`, `scripts/validate_lidar_labeled_subset.py:560-561`.
- [x] Stratified audit protocol template added.  
  Evidence: `docs/VALIDATION_PROTOCOL.md`.
- [x] One-command reproducibility targets added for official run and fusion sampling.  
  Evidence: `Makefile:122-174`.

## Done vs Blocked

## DONE

- Official reporting hardening (gates, manifest, degraded-state handling).
- AOI uncertainty enforcement via machine-readable block registry + operator docs.
- Fusion thermal sampling implementation and tests.
- Validation harness messaging and output structure for subset QA defensibility.

## BLOCKED (Client Input Required)

- **San Lorenzo Bushes AOI geometry remains blocked** and is not to be fixed locally.  
  Evidence: `manifests/aoi_registry.json` (`san_lorenzo_box_bushes`, `sl_box_bushes`), `docs/process/BLOCKED_AOIS.md`.

## Prioritized Issues (Remaining)

| Severity | Issue | Evidence | Recommended fix | Risk |
|---|---|---|---|---|
| blocker | Bushes AOI geometry unresolved (official reporting must block). | `manifests/aoi_registry.json`; `scripts/run_lidar_hag.py:2805-2815` | Keep blocked until authoritative client geometry payload is provided; then update registry status only after ingest validation. | Low (policy enforcement already in place). |
| major | `make validate` currently depends on `python3.12` on `PATH`, causing environment-level failure even when `.venv` exists. | `Makefile:23`, `Makefile:45-47` | Update validation path to prefer `.venv/bin/python` when available. | Low (build-system only). |
| minor | Fusion coordinate plausibility warning can trigger on synthetic/small-coordinate fixtures (not a runtime failure). | `pipelines/fusion.py:108-127`; warning observed in test runs | Keep warning as-is for production, but suppress in synthetic tests or use projected-scale test coordinates. | Low. |

## How To Run (Reproducible)

## 1) Official reporting mode

```bash
source .venv/bin/activate
make official-run \
  OFFICIAL_DATA_ROOT="data/2025/Caleta Tiny Island" \
  OFFICIAL_AOI_ID=caleta_tiny_island \
  OFFICIAL_AOI_GEOJSON=data/processed/aoi_caleta_tiny_island_epsg32720.geojson
```

## 2) Labeled subset QA evaluation

```bash
source .venv/bin/activate
python scripts/validate_lidar_labeled_subset.py \
  --lidar-summary data/interim/sl_box_bushes/sl_box_bushes.json \
  --labels data/processed/thermal_labels_georef.geojson \
  --aoi-geojson data/processed/aoi_san_lorenzo_boxes_epsg5345.geojson \
  --aoi-crs-epsg 5345 \
  --radii-m 1.0,1.5,2.0,2.5,3.0 \
  --out data/interim/validation/lidar_labeled_subset_eval_box_aoi.json
```

## 3) Fusion thermal sampling

```bash
source .venv/bin/activate
make fusion-sample \
  FUSION_LIDAR_SUMMARY=path/to/lidar_summary.json \
  FUSION_THERMAL_SUMMARY=path/to/thermal_summary.json \
  FUSION_THERMAL_RASTER=path/to/thermal_utm.tif
```

## Tests run for this review

```bash
.venv/bin/python -m pytest -q \
  tests/test_official_reporting_mode.py \
  tests/test_fusion_join.py \
  tests/test_fusion_cli.py \
  tests/test_fusion_sampling.py \
  tests/test_lidar_labeled_subset_validation.py \
  tests/test_lidar_dem_hag_unit.py
```

Observed result: `50 passed, 1 skipped`.

## Required Client Payload To Close Blocked AOI Items

For each blocked AOI (currently Bushes), provide:

1. `aoi_id` (stable identifier, e.g. `san_lorenzo_box_bushes`).
2. Polygon coordinates with explicit CRS:
   - Preferred: projected CRS used for analysis (e.g. EPSG:5345 or EPSG:32720), or
   - WGS84 (`EPSG:4326`) with explicit CRS metadata.
3. Coordinate order declaration (`x,y` for projected; `lon,lat` for geographic).
4. Source authority metadata:
   - survey date,
   - collection method (GNSS, digitized from orthomosaic, etc.),
   - uncertainty estimate (meters),
   - operator/reviewer name.
5. Expected area metadata (`area_m2` or `area_ha`) for integrity cross-check.

After receipt, update:

- `manifests/aoi_registry.json` (status from `BLOCKED` to approved state).
- AOI geometry file under approved AOI data path.
- Re-run official mode and AOI integrity checks before reporting.
