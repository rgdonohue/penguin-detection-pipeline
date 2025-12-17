from pathlib import Path

import numpy as np
import pytest

from pipelines.thermal import _convert_raw_to_celsius


def _const_raw(shape, celsius, scale):
    kelvin = celsius + 273.15
    dn = int(round(kelvin * scale))
    return np.full(shape, dn, dtype=np.uint16)


def test_h30t_normal_uses_scale_64():
    raw = _const_raw((1024, 1280), celsius=25.0, scale=64.0)
    temps, scale, mode = _convert_raw_to_celsius(raw, image_path=Path("normal.JPG"))
    assert mode == "normal"
    assert scale == pytest.approx(64.0, rel=1e-6)
    assert float(temps.mean()) == pytest.approx(25.0, abs=0.1)


def test_h30t_high_contrast_uses_scale_96():
    raw = _const_raw((1024, 1280), celsius=25.0, scale=96.0)
    with pytest.warns(RuntimeWarning):
        temps, scale, mode = _convert_raw_to_celsius(raw, image_path=Path("high_contrast.JPG"))
    assert mode == "high_contrast"
    assert scale == pytest.approx(96.0, rel=1e-6)
    assert float(temps.mean()) == pytest.approx(25.0, abs=0.1)


def test_dynamic_fallback_triggers_when_candidates_fail():
    raw = np.zeros((1024, 1280), dtype=np.uint16)
    raw.ravel()[::2] = 65535
    with pytest.warns(RuntimeWarning):
        temps, scale, mode = _convert_raw_to_celsius(raw, image_path=Path("weird.JPG"))
    assert mode == "dynamic"
    assert scale > 0
    assert temps.dtype == np.float32

