"""Radiometric scaling → reflectance, centralized in ONE place.

- Sentinel-2 SR: DN × 0.0001 (purely multiplicative — indices are invariant).
- Landsat C2 L2 SR: DN × 0.0000275 − 0.2 (the additive offset MATTERS for indices).
- Landsat thermal ST_B10: DN × 0.00341802 + 149.0 (→ Kelvin), then − 273.15 (→ °C).

Both sensors are renamed to the shared COMMON_OPTICAL band names so strategies
are sensor-agnostic. The Landsat image also carries an `lst` band in °C.

Phase 1 (HLS-style harmonization): the `HLSCoefficients` dataclass + the
`apply_hls_bandpass` helper transform Landsat 8/9 reflectance into the
Sentinel-2 reflectance space via the Claverie et al. 2018 per-band linear
bandpass. Defaults are the HLS S30↔L30 v1.5 operational coefficients; the
`from_env` classmethod lets an operator drop in a regional refit via
`ORBITER_HLS_COEFFS=./hls_coeffs.json`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import ee

from .masking import (
    COMMON_OPTICAL,
    LANDSAT_REFLECTANCE_BANDS,
    LANDSAT_THERMAL_BAND,
    S2_REFLECTANCE_BANDS,
)


@dataclass
class SensorImages:
    """Reflectance-domain images, common band names. `landsat` has an `lst` band (°C)."""
    sentinel: Optional[Any] = None
    landsat: Optional[Any] = None


# ────────────────────────────────────────────────────────────────────
# Phase 1: HLS-style harmonization (Claverie et al. 2018, operational v1.5)
# ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class HLSCoefficients:
    """Per-band linear bandpass ρ_S2 = slope·ρ_L8 + intercept.

    Defaults are the HLS S30↔L30 v1.5 operational coefficients. Override via
    `ORBITER_HLS_COEFFS=./hls_coeffs.json` (see `from_env`) for a regional
    refit. Each tuple is `(slope, intercept)`; the bands are the common
    optical band names so the helper doesn't need band-renaming logic.
    """
    blue:  tuple[float, float] = (0.8474,  0.0088)
    green: tuple[float, float] = (0.8833,  0.0069)
    red:   tuple[float, float] = (0.9277,  0.0055)
    nir:   tuple[float, float] = (0.7381,  0.0182)
    swir1: tuple[float, float] = (1.2910, -0.0048)
    swir2: tuple[float, float] = (1.0010,  0.0042)

    @classmethod
    def from_env(cls, cfg) -> "HLSCoefficients":
        """Load coefficients from `cfg.hls_coeffs_path` if set, else return defaults.

        The file is a JSON object whose values are [slope, intercept] pairs:
            {"blue": [0.8474, 0.0088], "green": [...], ...}
        Any missing band falls back to the operational default.
        """
        path = getattr(cfg, "hls_coeffs_path", None)
        if not path:
            return cls()
        import json
        with open(path) as f:
            d = json.load(f)
        return cls(
            blue=tuple(d.get("blue",  cls.blue))  if isinstance(d.get("blue"),  list) else cls.blue,
            green=tuple(d.get("green", cls.green)) if isinstance(d.get("green"), list) else cls.green,
            red=tuple(d.get("red",   cls.red))   if isinstance(d.get("red"),   list) else cls.red,
            nir=tuple(d.get("nir",   cls.nir))   if isinstance(d.get("nir"),   list) else cls.nir,
            swir1=tuple(d.get("swir1", cls.swir1)) if isinstance(d.get("swir1"), list) else cls.swir1,
            swir2=tuple(d.get("swir2", cls.swir2)) if isinstance(d.get("swir2"), list) else cls.swir2,
        )


def apply_hls_bandpass(l8_reflectance, coefs: HLSCoefficients):
    """Per-band linear: ρ_S2 = slope·ρ_L8 + intercept. Landsat 8/9 → harmonized.

    Operates on an image already in the common optical band names
    (`COMMON_OPTICAL`); the result is an image with the same band names
    but in the S2 reflectance space. Masked pixels stay masked (GEE
    propagates masks through arithmetic).
    """
    # First band: rename, then addBands the rest.
    first = l8_reflectance.select(["blue"]).multiply(coefs.blue[0]).add(coefs.blue[1]).rename(["blue"])
    out = first
    for band in ("green", "red", "nir", "swir1", "swir2"):
        slope, intercept = getattr(coefs, band)
        out = out.addBands(
            l8_reflectance.select([band]).multiply(slope).add(intercept).rename([band])
        )
    return out


# ────────────────────────────────────────────────────────────────────
# Sensor scaling (Phase 0 — unchanged)
# ────────────────────────────────────────────────────────────────────

def scale_s2(img):
    """Sentinel-2 SR → reflectance (multiplicative only), renamed to common bands."""
    return img.select(S2_REFLECTANCE_BANDS).multiply(0.0001).rename(COMMON_OPTICAL)


def scale_landsat(img):
    """Landsat SR → reflectance (scale+offset) + `lst` band in °C."""
    optical = (
        img.select(LANDSAT_REFLECTANCE_BANDS)
        .multiply(0.0000275)
        .add(-0.2)
        .rename(COMMON_OPTICAL)
    )
    lst_c = (
        img.select([LANDSAT_THERMAL_BAND])
        .multiply(0.00341802)
        .add(149.0)       # → Kelvin (ST_B10 is emissivity-adjusted; no Planck inversion)
        .subtract(273.15)  # → °C
        .rename(["lst"])
    )
    return optical.addBands(lst_c)


def to_sensor_images(sentinel=None, landsat=None) -> SensorImages:
    return SensorImages(
        sentinel=scale_s2(sentinel) if sentinel is not None else None,
        landsat=scale_landsat(landsat) if landsat is not None else None,
    )
