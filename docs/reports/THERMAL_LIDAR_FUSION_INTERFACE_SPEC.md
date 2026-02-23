# Thermal-LiDAR Fusion Interface Spec

## Purpose
Define a reproducible, auditable handoff contract between LiDAR candidate detection and thermal GIS analysis for San Lorenzo / Caleta workflows.

Fusion runtime (`pipelines/fusion.py`) now supports nearest-neighbor spatial join plus optional thermal raster sampling at LiDAR candidate points.

## Shared CRS + Resampling Rules

- Canonical working CRS for fusion deliverables: `EPSG:32720` (WGS 84 / UTM zone 20S).
- LiDAR outputs:
  - If source CRS is not `EPSG:32720`, transform candidate geometries before fusion.
  - Preserve original CRS metadata in run manifest.
- Thermal orthomosaic / raster products:
  - Reproject to `EPSG:32720`.
  - Use `bilinear` resampling for continuous thermal values.
  - Use `nearest` for masks/class labels.
- Axis order:
  - Always serialize coordinates as `(x=easting, y=northing)`.
  - Never use lat/lon ordering in fusion candidate files.

## Candidate Exchange Format

Primary artifact: `candidates.gpkg`, layer `detections`.

Required geometry and fields:

| Field | Type | Description |
|---|---|---|
| `candidate_id` | string | Stable ID (`<tile>:<index>`), unique per run |
| `source` | string | `lidar` or `thermal` |
| `x` | float64 | Easting in meters (EPSG:32720) |
| `y` | float64 | Northing in meters (EPSG:32720) |
| `tile_id` | string | Source tile/frame key |
| `hag_mean` | float32 nullable | LiDAR HAG mean for blob |
| `hag_max` | float32 nullable | LiDAR HAG max for blob |
| `area_m2` | float32 nullable | Blob area in square meters |
| `confidence` | float32 nullable | Optional model/confidence score |
| `run_id` | string | Immutable run identifier (hash/timestamp) |

Optional second layer: `detections_deduped` when LiDAR dedupe is enabled.

## Thermal Sampling at Candidate Points

For each LiDAR candidate point (when `--thermal-raster` is provided):

- Sampling windows (meters, raster CRS):
  - Core radius `r_core = 0.5` (default)
  - Neighborhood annulus `r_inner = 1.0`, `r_outer = 2.0` (default)
- Metrics:
  - `thermal_mean_c`: mean temperature in window.
  - `thermal_max_c`: max temperature in window.
  - `thermal_z_local`: local z-score vs annulus neighborhood.
  - `thermal_n_core`: valid core pixels used.
  - `thermal_n_neighborhood`: valid neighborhood pixels used.
  - `thermal_sample_reason`: null on success; otherwise reason (`core_nodata`, `insufficient_neighborhood`, `point_outside_raster`, etc.).
- Local z-score methods:
  - `robust` (default): median/MAD; falls back to mean/std when MAD is zero.
  - `standard`: mean/std.
- Nodata behavior:
  - If no valid core pixels, `thermal_mean_c`, `thermal_max_c`, and `thermal_z_local` are null with `thermal_sample_reason=core_nodata`.
  - CRS mismatch between detections and thermal raster is a hard error.

## Joint Labeling Rules

Given LiDAR and thermal detections in same CRS and match radius `R`:

- `both`: LiDAR candidate has thermal match within `R`.
- `lidar_only`: LiDAR candidate has no thermal match within `R`.
- `thermal_only`: Thermal detection has no LiDAR match within `R`.

Suggested default `R = 0.5 m` for orthorectified products; evaluate `R ∈ {0.5, 1.0, 1.5}` during QA.

## QA Gates (Must Pass Before Reporting)

1. CRS gate:
   - Inputs must declare CRS and match after transform (`EPSG:32720`).
2. Alignment gate:
   - Checkpoint RMSE between thermal control points and LiDAR reference: `<= 2.0 m`.
3. Seam/duplicate gate:
   - Run LiDAR dedupe across tile boundaries; verify no seam clusters exceed expected radius policy.
4. AOI gate:
   - AOI geometry area must match property area within tolerance (`<= 5%`) or be flagged.
5. Panel gate:
   - Export visual QA panel with overlays (LiDAR, thermal, AOI, match links) before analyst sign-off.

## Required Run Artifacts

- `lidar_summary.json` (`purpose=lidar_candidates`)
- `thermal_summary.json` (`purpose=qc_alignment` until calibrated counting is validated)
- `fusion_rollup.json` (`purpose=qc_alignment`)
- `config.effective.json`
- `provenance_lidar.json` + thermal provenance
- `candidates.gpkg` (+ `detections_deduped` if enabled)
- `qa_panel.*` visualization

## Working Agreement Template (Thermal GIS Analyst)

Use this message as the default kickoff handoff:

> We need from you: thermal raster deliverables in `EPSG:32720`, alignment metadata (control points + RMSE report), and nodata conventions.  
> We will provide: LiDAR candidates in `candidates.gpkg` (`detections` layer with stable IDs, `x/y`, run metadata) plus deduped official counts and run manifest.  
> Joint method: classify each candidate as `both`, `lidar_only`, or `thermal_only` using agreed match radius and thermal sampling windows (`0.5m` core, `1-2m` neighborhood default).  
> Discrepancy handling: review mismatches in shared QA panels, record per-case disposition, and only finalize reporting after CRS parity, RMSE <= 2.0m, seam checks, and AOI integrity gates pass.
