#!/usr/bin/env python3
"""
Test radiometric thermal extraction integration.

Validates that 16-bit thermal data extraction is properly integrated
into pipelines/thermal.py and produces expected float32 output.
"""

import pytest
from pathlib import Path
import sys
import tempfile
import numpy as np

# Add project root to path
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.thermal import extract_thermal_data, extract_thermal_frame


def test_extract_thermal_data_exists():
    """Test that extract_thermal_data function is available."""
    assert extract_thermal_data is not None
    assert callable(extract_thermal_data)


def test_extract_thermal_data_signature():
    """Test extract_thermal_data has expected signature."""
    import inspect
    sig = inspect.signature(extract_thermal_data)
    params = list(sig.parameters.keys())

    assert 'image_path' in params
    assert 'temp_dir' in params

    # Check defaults
    assert sig.parameters['temp_dir'].default is not inspect.Parameter.empty


@pytest.mark.skipif(
    not Path("data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5/DJI_20241106194542_0356_T.JPG").exists(),
    reason="Test thermal image not available"
)
def test_extract_thermal_data_frame_0356():
    """Test thermal extraction on validated frame 0356."""
    image_path = Path("data/legacy_ro/penguin-2.0/data/raw/thermal-images/DJI_202411061712_006_Create-Area-Route5/DJI_20241106194542_0356_T.JPG")

    with tempfile.TemporaryDirectory() as tmpdir:
        celsius = extract_thermal_data(image_path, Path(tmpdir))

    # Validate output
    assert isinstance(celsius, np.ndarray)
    assert celsius.dtype == np.float32
    assert celsius.shape == (512, 640)

    # Validate expected temperature range (from validation results)
    assert celsius.min() >= -20.0  # Should be around -13.77°C
    assert celsius.max() <= 20.0    # Should be around 12.16°C
    assert -10.0 < celsius.mean() < 0.0  # Should be around -5.69°C

    # Check that temperatures are realistic
    assert not np.all(np.isnan(celsius))
    assert np.isfinite(celsius).all()


@pytest.mark.skipif(
    not Path("data/legacy_ro/penguin-2.0/data/pilot_frames/DJI_20241106184025_0007_T.JPG").exists(),
    reason="Pilot frame not available"
)
def test_extract_thermal_data_pilot_frame():
    """Test thermal extraction on a pilot frame."""
    image_path = Path("data/legacy_ro/penguin-2.0/data/pilot_frames/DJI_20241106184025_0007_T.JPG")

    with tempfile.TemporaryDirectory() as tmpdir:
        celsius = extract_thermal_data(image_path, Path(tmpdir))

    # Validate basic output properties
    assert isinstance(celsius, np.ndarray)
    assert celsius.dtype == np.float32
    assert celsius.shape == (512, 640)
    assert np.isfinite(celsius).all()


def test_extract_thermal_data_missing_file():
    """Test that missing file raises appropriate error."""
    image_path = Path("/nonexistent/thermal.JPG")

    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises((FileNotFoundError, RuntimeError)):
            extract_thermal_data(image_path, Path(tmpdir))


def test_extract_thermal_frame_h30t_normal(tmp_path: Path):
    """H30T normal mode frames should decode to 1280×1024 with scale 64."""
    image_path = Path("data/intake/h30t/flight_001/normal_0001_T.JPG")
    if not image_path.exists():
        pytest.skip("H30T normal sample not available")

    frame = extract_thermal_frame(image_path, temp_dir=tmp_path)

    assert isinstance(frame.celsius, np.ndarray)
    assert frame.celsius.dtype == np.float32
    assert frame.celsius.shape == (1024, 1280)
    assert frame.mode == "normal"
    assert frame.scale == pytest.approx(64.0, rel=1e-6)
    assert frame.raw_stats["min"] < frame.raw_stats["max"]
    assert 0.0 < frame.celsius.mean() < 40.0


def test_extract_thermal_frame_h30t_high_contrast(tmp_path: Path):
    """High-contrast capture should trigger alternate scaling heuristics."""
    image_path = Path("data/intake/h30t/flight_002/high_contrast_0001_T.JPG")
    if not image_path.exists():
        pytest.skip("H30T high-contrast sample not available")

    with pytest.warns(RuntimeWarning):
        frame = extract_thermal_frame(image_path, temp_dir=tmp_path)

    assert frame.celsius.shape == (1024, 1280)
    assert frame.celsius.dtype == np.float32
    assert frame.mode == "high_contrast"
    assert frame.scale == pytest.approx(96.0, rel=1e-6)
    assert -40.0 < frame.celsius.min() < 10.0
    assert frame.celsius.max() < 60.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
