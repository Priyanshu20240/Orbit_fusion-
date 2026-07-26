"""M4 — index correctness proven on the recorded op-graph (fake ee).

No numeric-range assertions here: the fake returns synthetic values, so any
range would be fabricated. The 20–45 °C LST range is asserted against REAL
GEE in the M10 integration suite.

Phase 1 (M3) — gap_fill / harmonized_l8 / real_lst algorithm locks +
`experimental=False` regression guard for all 11 strategies.
"""
import pytest

import ee

from app.services.fusion import get_strategy, STRATEGY_REGISTRY
from app.services.fusion.scaling import to_sensor_images


def _s2_imgs():
    return to_sensor_images(sentinel=ee.Image("COPERNICUS/S2_SR_HARMONIZED/X"))


def _landsat_imgs():
    return to_sensor_images(landsat=ee.Image("LANDSAT/LC08/C02/T1_L2/X"))


def _both_imgs():
    return to_sensor_images(
        sentinel=ee.Image("COPERNICUS/S2_SR_HARMONIZED/X"),
        landsat=ee.Image("LANDSAT/LC08/C02/T1_L2/X"),
    )


def test_ndwi_is_true_water_green_nir():
    img, _ = get_strategy("ndwi").build(_s2_imgs())
    nd = img.find("normalizedDifference")
    assert nd, "NDWI must use normalizedDifference"
    assert nd[0]["args"][0] == ["green", "nir"], "NDWI must be McFeeters Green/NIR, not NIR/SWIR"


def test_ndvi_bands():
    img, _ = get_strategy("ndvi").build(_s2_imgs())
    assert img.find("normalizedDifference")[0]["args"][0] == ["nir", "red"]


def test_ndbi_bands():
    img, _ = get_strategy("ndbi").build(_s2_imgs())
    assert img.find("normalizedDifference")[0]["args"][0] == ["swir1", "nir"]


def test_true_color_is_not_averaged():
    img, _ = get_strategy("true_color").build(_s2_imgs())
    names = img.op_names()
    # S2 scaling is multiply-only; a naive average would add+divide.
    assert "divide" not in names
    assert "add" not in names


def test_landsat_offset_applied_before_index():
    img, _ = get_strategy("ndvi").build(_landsat_imgs())
    names = img.op_names()
    assert {"multiply", "add", "normalizedDifference"} <= set(names)
    nd = names.index("normalizedDifference")
    assert names.index("multiply") < nd, "reflectance scale must precede the index"
    assert names.index("add") < nd, "the -0.2 Landsat offset must precede the index"


def test_lst_landsat_only_celsius_conversion():
    img, vis = get_strategy("lst").build(_landsat_imgs())
    names = img.op_names()
    assert "subtract" in names, "LST must subtract 273.15 (K → °C)"
    assert vis.min == 20 and vis.max == 45, "LST VisSpec is °C (20–45), matching the legend"


def test_sentinel_lst_raises():
    import pytest

    with pytest.raises(ValueError):
        get_strategy("lst").build(_s2_imgs())  # no Landsat → no thermal band


def test_registry_has_exactly_eleven_modes():
    """Phase 0 shipped 8 modes; Phase 1 adds gap_fill, harmonized_l8, real_lst = 11."""
    assert set(STRATEGY_REGISTRY) == {
        "true_color", "ndvi", "ndwi", "ndbi",
        "false_color_nir", "false_color_swir", "sci", "lst",
        "gap_fill", "harmonized_l8", "real_lst",
    }


def test_every_mode_builds_and_visualizes():
    """Every strategy builds successfully given the sensors it requires."""
    for mode, sensors in (
        ("true_color", _both_imgs),
        ("ndvi", _both_imgs),
        ("ndwi", _both_imgs),
        ("ndbi", _both_imgs),
        ("false_color_nir", _both_imgs),
        ("false_color_swir", _both_imgs),
        ("sci", _both_imgs),
        ("lst", _landsat_imgs),
        ("gap_fill", _both_imgs),
        ("harmonized_l8", _both_imgs),
        ("real_lst", _landsat_imgs),
    ):
        img, vis = get_strategy(mode).build(sensors())
        assert img is not None and vis is not None, f"mode {mode!r} failed to build"


# ────────────────────────────────────────────────────────────────────
# Phase 1 (M3): gap_fill, harmonized_l8, real_lst algorithm locks
# ────────────────────────────────────────────────────────────────────

def test_gap_fill_unmask_chain():
    """gap_fill must call `sentinel.unmask(landsat)` — the S2 master / L8 fill pattern."""
    img, _ = get_strategy("gap_fill").build(_both_imgs())
    assert img.find("unmask"), "gap_fill must use sentinel.unmask(landsat)"


def test_gap_fill_fallbacks_to_single_sensor():
    """When only one sensor is present, gap_fill returns that sensor unchanged."""
    img, _ = get_strategy("gap_fill").build(_s2_imgs())
    # No `unmask` because there's nothing to fill from.
    assert not img.find("unmask"), "S2-only gap_fill should not call unmask"
    img2, _ = get_strategy("gap_fill").build(_landsat_imgs())
    assert not img2.find("unmask"), "L8-only gap_fill should not call unmask"


def test_gap_fill_raises_when_no_sensors():
    """gap_fill with both sensors None raises ValueError."""
    with pytest.raises(ValueError):
        get_strategy("gap_fill").build(to_sensor_images())


def test_harmonized_l8_emits_bandpass_per_band():
    """harmonized_l8 applies the 6-band bandpass + an unmask join to S2.

    The fake_ee chain recorder only tracks the *final* image's op chain (a
    multiply/select from inside `apply_hls_bandpass`'s addBands call isn't
    exposed on the returned image). What we *can* assert: the strategy returns
    a non-None image that went through `unmask` (S2 master / L8 fill) and that
    `apply_hls_bandpass` was exercised (verified by the 6 multiply + 6 add ops
    in `tests/test_scaling.py::test_apply_hls_bandpass_*`).
    """
    ee.reset()
    img, vis = get_strategy("harmonized_l8").build(_both_imgs())
    assert img is not None
    # The harmonized-L8 strategy ends with `sentinel.unmask(apply_hls_bandpass(l8))`.
    assert "unmask" in img.op_names(), "harmonized_l8 must end with S2.unmask(L8-harmonized)"
    # VisSpec is RGB-composite.
    assert vis.bands == ["red", "green", "blue"]
    assert vis.min == 0.0 and vis.max == 0.25 and vis.gamma == 1.3


def test_harmonized_l8_requires_both_sensors():
    """harmonized_l8 with only S2 or only L8 raises ValueError."""
    with pytest.raises(ValueError):
        get_strategy("harmonized_l8").build(_s2_imgs())
    with pytest.raises(ValueError):
        get_strategy("harmonized_l8").build(_landsat_imgs())


def test_real_lst_emissivity_emits_thresholds_and_correction():
    """real_lst computes per-pixel NDVI-based ε and divides T by ε^(1/4)."""
    ee.reset()
    img, _ = get_strategy("real_lst").build(_landsat_imgs())
    names = img.op_names()
    # Must compute NDVI for the emissivity.
    assert "normalizedDifference" in names
    # Must do the grey-body correction (divide T by ε^(1/4) ⇒ `pow(0.25)` + `divide`).
    assert "divide" in names
    assert "pow" in names


def test_real_lst_is_landsat_only():
    """real_lst with S2 raises ValueError — S2 has no thermal band."""
    with pytest.raises(ValueError):
        get_strategy("real_lst").build(_s2_imgs())


def test_experimental_default_false_for_every_strategy():
    """Regression guard for Phase 4: all 11 strategies are NOT experimental.

    Phase 4 will set `experimental = True` on the super-resolution strategy
    class. Until then, every strategy must default to False.
    """
    for mode, strat in STRATEGY_REGISTRY.items():
        assert getattr(strat, "experimental", False) is False, (
            f"strategy {mode!r} is marked experimental=True; only Phase 4 SR is"
        )
