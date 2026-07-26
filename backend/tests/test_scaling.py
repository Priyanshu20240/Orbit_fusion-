"""M4 — radiometric scaling op-graph.

Phase 1 (M1) — HLS bandpass + HLSCoefficients.from_env.
"""
import json
import os
import tempfile
from dataclasses import FrozenInstanceError

import ee
import pytest

from app.services.fusion.scaling import (
    HLSCoefficients,
    apply_hls_bandpass,
    scale_landsat,
    scale_s2,
    to_sensor_images,
)


def test_s2_scaling_is_multiplicative_only():
    names = scale_s2(ee.Image("S2")).op_names()
    assert "multiply" in names
    assert "add" not in names  # S2 offset-free


def test_landsat_scaling_has_scale_and_offset():
    names = scale_landsat(ee.Image("L8")).op_names()
    assert "multiply" in names and "add" in names
    assert names.index("multiply") < names.index("add")


def test_landsat_thermal_converted_to_celsius():
    names = scale_landsat(ee.Image("L8")).op_names()
    # thermal chain applies subtract(273.15) after the K conversion
    assert "subtract" in names


def test_to_sensor_images_optional_sensors():
    imgs = to_sensor_images(sentinel=ee.Image("S2"))
    assert imgs.sentinel is not None and imgs.landsat is None
    imgs2 = to_sensor_images(landsat=ee.Image("L8"))
    assert imgs2.landsat is not None and imgs2.sentinel is None


# ────────────────────────────────────────────────────────────────────
# Phase 1 (M1): HLS bandpass + HLSCoefficients.from_env
# ────────────────────────────────────────────────────────────────────

def test_hls_defaults_match_claverie_v15_operational():
    """Defaults match the HLS S30↔L30 v1.5 release notes verbatim."""
    c = HLSCoefficients()
    assert c.blue  == (0.8474,  0.0088)
    assert c.green == (0.8833,  0.0069)
    assert c.red   == (0.9277,  0.0055)
    assert c.nir   == (0.7381,  0.0182)
    assert c.swir1 == (1.2910, -0.0048)
    assert c.swir2 == (1.0010,  0.0042)


def test_hls_coefficients_is_frozen():
    """Coefficient mutation at runtime would be a bug; the dataclass is frozen."""
    c = HLSCoefficients()
    with pytest.raises(FrozenInstanceError):
        c.blue = (0.5, 0.0)


def test_hls_from_env_returns_defaults_when_path_unset():
    """No `hls_coeffs_path` ⇒ defaults (the operational v1.5 values)."""
    cfg = type("Cfg", (), {"hls_coeffs_path": None})()
    c = HLSCoefficients.from_env(cfg)
    assert c == HLSCoefficients()


def test_hls_from_env_overrides_from_json_file():
    """A JSON file at `hls_coeffs_path` overrides one or more bands."""
    payload = {
        "blue": [0.5, 0.1],
        "nir":  [0.6, 0.0],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        path = f.name
    try:
        cfg = type("Cfg", (), {"hls_coeffs_path": path})()
        c = HLSCoefficients.from_env(cfg)
        assert c.blue  == (0.5, 0.1)
        assert c.nir   == (0.6, 0.0)
        # Unspecified bands fall back to defaults.
        assert c.green == HLSCoefficients().green
        assert c.swir2 == HLSCoefficients().swir2
    finally:
        os.unlink(path)


def test_apply_hls_bandpass_emits_one_multiply_one_add_per_band():
    """Each of the 6 bands produces exactly one `multiply(slope)` + one `add(intercept)`."""
    ee.reset()
    l8 = ee.Image.constant(0.1)
    apply_hls_bandpass(l8, HLSCoefficients())

    # fake_ee exposes `op_names()` on the chainable recorder. Count multiply/add
    # in the recorded op chain — 6 optical bands × 2 ops (multiply + add) = 12.
    names = l8.op_names()
    assert names.count("multiply") == 6
    assert names.count("add") == 6
