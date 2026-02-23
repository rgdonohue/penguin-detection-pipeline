# Blocked AOIs

This registry-backed list documents AOIs that must not be used for official reporting until authoritative geometry is provided.

Machine-readable source: `manifests/aoi_registry.json`.

## Current Blocked AOIs

| AOI ID | Status | Blocked Since | Reason | Required Client Input |
|---|---|---|---|---|
| `san_lorenzo_box_bushes` | BLOCKED | 2026-02-23 | Geometry unresolved/contradictory | Authoritative Bushes polygon coordinates in the project CRS (or WGS84 with explicit CRS metadata) |
| `sl_box_bushes` | BLOCKED | 2026-02-23 | Alias for the same unresolved Bushes AOI | Same as above |

## Enforcement

- Official runs (`scripts/run_lidar_hag.py --official-reporting`) check `--aoi-id` against the registry.
- If AOI status is `BLOCKED`, official runs fail unless `--override-blocked-aoi` is explicitly set.
- Overrides are recorded in `lidar_run_manifest.json` and summary outputs.

## Change Control

- Do not update AOI geometry here.
- Only update block status/reason when new authoritative client coordinates are received and ingested.
