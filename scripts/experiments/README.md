# Experiments (Prototype Scripts)

This directory contains one-off prototypes and investigation scripts.

These files are **not** part of the supported pipeline surface area and may be
out of date relative to `pipelines/` and the main entrypoints in `scripts/`.

**Supported entrypoints**
- `scripts/run_lidar_hag.py` (LiDAR detection)
- `scripts/run_thermal_ortho.py` (thermal orthorectification)
- `scripts/run_thermal_detection_batch.py` (thermal detection batch runner)

If you need to run an experiment, prefer starting from the supported entrypoints
or porting the logic into `pipelines/` with tests.

