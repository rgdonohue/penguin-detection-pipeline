"""Pipelines package.

Keep `pipelines` import lightweight: do not eagerly import submodules with optional
heavy dependencies (e.g., `scipy`, GDAL stack). Import the specific pipeline you
need instead (e.g. `from pipelines import aoi_eval` or `import pipelines.lidar`).
"""

__all__ = [
    "aoi_eval",
    "contracts",
    "fusion",
    "golden",
    "label_sample",
    "lidar",
    "lidar_profiles",
    "thermal",
    "thermal_crs",
]

# Optional convenience imports (best-effort). These are wrapped so lightweight
# tools (e.g. AOI eval) don't fail just because a different stage dependency is
# missing in the current environment.
try:  # pragma: no cover
    from . import aoi_eval as aoi_eval  # noqa: F401
    from . import contracts as contracts  # noqa: F401
    from . import fusion as fusion  # noqa: F401
    from . import golden as golden  # noqa: F401
    from . import label_sample as label_sample  # noqa: F401
    from . import lidar as lidar  # noqa: F401
    from . import lidar_profiles as lidar_profiles  # noqa: F401
    from . import thermal as thermal  # noqa: F401
    from . import thermal_crs as thermal_crs  # noqa: F401
except Exception:
    # Intentionally swallow to keep package import lightweight.
    pass
