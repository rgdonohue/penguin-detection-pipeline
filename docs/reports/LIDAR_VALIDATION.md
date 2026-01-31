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

- **San Lorenzo Caves:** AOI present (convex hull of start/end/edge waypoints, EPSG:5345). Area: 0.60 ha (matches reported).
- **San Lorenzo Plains:** AOI present (perimeter winding of top/bottom edge waypoints, EPSG:5345). Area: 0.73 ha (vs reported 0.98 ha; perimeter is more accurate than convex hull).
- **San Lorenzo Bushes Box Count:** AOI present from GPS corners in PDF. Area: 0.02 ha. **CAVEAT:** diagnostic confirms these coordinates fall inside the Caves tile (11.9), not the Bushes tile (11.10). Likely a PDF mislabeling or internal waypoints, not box corners. Client clarification requested.
- **San Lorenzo Caves Box Count:** AOI missing. 32 penguins counted but no GPS corners provided in notes.
- **San Lorenzo Road:** AOI missing. 359 penguins counted but no waypoints documented.
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

## AOI Clarification Requests (Client Action Needed)

The following items require client input to resolve AOI boundary uncertainties:

1. **San Lorenzo Road (359 penguins):** No waypoints were documented in the PDF for this zone. Without boundary coordinates, these penguins cannot be included in AOI-clipped evaluation. Request: provide boundary waypoints or digitized polygon from imagery.

2. **San Lorenzo Caves Box Count (32 penguins):** The PDF notes a box count of 32 penguins but does not provide GPS corners for this box. Request: provide 4 corner coordinates.

3. **Bushes Box Count GPS Mismatch:** The 4 GPS coordinates labeled "Box Count High Density Bushes: 55 penguins" in the PDF (p.4) produce a polygon that falls inside the Caves tile (11.9), not the Bushes tile (11.10). The polygon area is also ~200 m² vs the reported ~37,984 m². This suggests either:
   - (a) The coordinates are mislabeled and actually belong to the Caves box count area, or
   - (b) They are internal waypoints, not box corners.
   Request: clarify which area these coordinates represent, and provide correct box corner coordinates if needed.

4. **Plains AOI Approximation:** The perimeter winding of top/bottom edge waypoints gives 0.73 ha vs the reported 0.98 ha. The discrepancy likely arises because the GPS waypoints were recorded at internal transect endpoints, not at the actual survey boundary. Request: provide digitized boundary or annotated imagery for accurate AOI.

## Next Steps

1. Resolve AOI clarification requests above.
2. Regenerate AOI eval for all AOIs once boundaries are confirmed.
3. Perform manual precision audit (50–100 candidates) within AOIs.
