  Expert-Level Confidence Checks

  1. Re-run the legacy wrapper directly (python data/legacy_ro/penguin-2.0/scripts/
     lidar_detect_penguins.py --data-root data/legacy_ro/penguin-2.0/data/raw/LiDAR/sample --out
     data/interim/repro.json --cell-res 0.25 ...) and confirm identical counts/hash against
     test_run.json.
  2. Load cloud3_detections.geojson in QGIS alongside the LAS tile (via PDAL/LAStools) to visually
     verify detections align with elevated clusters in the 0.2–0.6 m HAG band.
  3. Use PDAL (pdal info --stats) on cloud3.las to confirm point density (≥150 pts/m²) and that HAG
     normalization matches the reported grid dimensions (~150 m × 105 m).
  4. Sample raw cross-sections in CloudCompare/LASview to spot-check 5–10 detections, ensuring the
     polygon footprints and HAG heights match penguin-sized objects.
  5. Compare against any known ground-truth or legacy rollups, and log SHA256 hashes of
     cloud3_detections.geojson and plots in manifests/qc_report.md for reproducibility.

  Following these steps grounds the claim in observable geospatial outputs rather than text, giving a
  remote sensing reviewer concrete evidence that the LiDAR detector is genuinely working.

  