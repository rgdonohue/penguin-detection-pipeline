# LiDAR Validation (AOI-Clipped) — San Lorenzo (Draft)

Last updated: 2026-01-07

## Summary

AOI-clipped candidate counts were generated for San Lorenzo using AOI polygons derived from the GPS Ground Truthing Notes PDF. These counts represent **LiDAR candidates**, not validated penguin counts.

Caleta island AOIs can be derived more reliably than San Lorenzo cave regions because islands form a closed natural boundary in LiDAR space. As of 2026-01-11, Caleta Small/Tiny Island AOIs have been generated from LiDAR coverage (EPSG:32720) and AOI-clipped counts are available (box count AOIs still pending).

## Inputs

- LiDAR summary: `data/interim/san_lorenzo_full.json`
- AOI polygons (EPSG:5345): `data/processed/aoi_san_lorenzo_epsg5345.geojson`
- AOI evaluation output: `data/processed/san_lorenzo_aoi_eval.json`
- Field counts reference: `data/processed/san_lorenzo_analysis.json`
- Source notes: `docs/GPS Ground Truthing Notes 2025 - RD.pdf`

Caleta (islands):
- LiDAR summaries:
  - `data/interim/caleta_small_island.json`
  - `data/interim/tiny_best.json`
- AOI polygons (EPSG:32720):
  - `data/processed/aoi_caleta_small_island_epsg32720.geojson`
  - `data/processed/aoi_caleta_tiny_island_epsg32720.geojson`
  - Combined: `data/processed/aoi_caleta_islands_epsg32720.geojson`
- AOI evaluation outputs:
  - `data/processed/caleta_small_island_aoi_eval.json`
  - `data/processed/caleta_tiny_island_aoi_eval.json`

## AOI Status

- **San Lorenzo Caves / Plains:** AOIs present (projected to EPSG:5345).
- **San Lorenzo Road / Box Counts:** AOIs missing (no polygon boundaries in the notes).
- **Caleta Small/Tiny Islands:** AOIs present (projected to EPSG:32720; derived from LiDAR footprint).
- **Caleta Box Counts:** AOIs missing (need digitized polygons in EPSG:32720).

## Results (Candidate Counts vs Field Counts)

| AOI | Field Count | LiDAR Candidates | Candidate/Field Ratio | Notes |
| --- | ---:| ---:| ---:| --- |
| San Lorenzo Caves | 908 | 263 | 0.29 | AOI derived from notes; polygon area differs from reported 0.60 ha. |
| San Lorenzo Plains | 453 | 86 | 0.19 | AOI derived from notes; polygon area differs from reported 0.98 ha. |

### Caleta (Islands)

| AOI | Field Count | LiDAR Candidates | Candidate/Field Ratio | Notes |
| --- | ---:| ---:| ---:| --- |
| Caleta Small Island | 1,557 | 1,255 | 0.81 | AOI derived from LiDAR footprint; polygon area ~4.07 ha (close to reported 4.0 ha). |
| Caleta Tiny Island | 321 | 315 | 0.98 | AOI derived from LiDAR footprint using Otsu thresholding to reject sparse water returns; polygon area ~0.53 ha vs reported 0.7 ha. |

## Interpretation

- These results are **not** accuracy metrics; they are AOI-clipped candidate counts.
- AOI geometry fidelity is the biggest current risk: boundaries are approximate and require field confirmation or digitized polygons from imagery.
  - San Lorenzo cave/plains AOIs are still approximate from waypoints and show significant area mismatches.
  - Caleta islands are more robust to derive from LiDAR, but shoreline/tide ambiguity and density-thresholding choices can still shift area.

## Next Steps

1. Confirm/digitize AOI polygons for San Lorenzo (caves, plains, road, box counts) and Caleta (small/tiny islands, box counts).
2. Regenerate AOI eval for all AOIs once polygons are vetted.
3. Perform manual precision audit (50–100 candidates) within AOIs.
