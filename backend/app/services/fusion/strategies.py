"""The 8 P0 visualization strategies (honest single-sensor views) + 3 P1 fusion strategies.

ids MUST match the frontend `VISUALIZATIONS` and the `FusionRequest` Literal:
    true_color, ndvi, ndwi, ndbi, false_color_nir, false_color_swir, sci, lst
    gap_fill, harmonized_l8, real_lst                         (Phase 1)

Index math is computed on scale+offset-corrected reflectance (see scaling.py),
so the Landsat additive-offset bug is fixed by construction. NDWI is true
McFeeters water (Green/NIR). LST is Landsat-only, in °C.

Phase 1 fusion strategies (see PHASE1.md):
  - gap_fill:      S2 master, Landsat fill (`s2.unmask(l8)`).
  - harmonized_l8: HLS-style per-band linear bandpass (Claverie 2018).
  - real_lst:      NDVI-based emissivity (Sobrino 2004) + grey-body correction.
"""
from __future__ import annotations

import ee

from .registry import VisSpec, register
from .scaling import HLSCoefficients, apply_hls_bandpass
from .masking import COMMON_OPTICAL

# ── color ramps (GIS / Earth Engine standards) ──
# NDVI: Deep Blue/Water (low < 0) → Light Tan/Soil → Yellow-Green → Lush Forest Green (high > 0.4)
_NDVI_PALETTE = ["#000080", "#4575b4", "#e0f3f8", "#fee090", "#d9ef8b", "#91cf60", "#1a9850", "#004d00"]
# NDWI: Tan/Sand (non-water) → Cyan → Deep Blue (water)
_WATER_PALETTE = ["#fdae61", "#ffffbf", "#e0f3f8", "#abd9e9", "#2c7fb8", "#253494", "#081d58"]
# NDBI: Vegetation/Water (blue/green) → Yellow → Built-up Urban (Red)
_BUILTUP_PALETTE = ["#1a9850", "#91cf60", "#ffffbf", "#fdae61", "#d73027"]
# Thermal LST: Cold Blue → Cool Cyan → Neutral Yellow → Warm Orange → Hot Red
_THERMAL_PALETTE = ["#313695", "#4575b4", "#74add1", "#abd9e9", "#e0f3f8", "#fee090", "#fdae61", "#f46d43", "#d73027"]

# True Color / False Color RGB stretch: Natural sunlit reflectance (0 to 0.35, gamma 1.3)
_RGB_MIN, _RGB_MAX, _RGB_GAMMA = 0.0, 0.35, 1.3


def _optical(images):
    """Prefer Sentinel-2 (10 m) when present, else Landsat. P0 is single-sensor."""
    img = images.sentinel if images.sentinel is not None else images.landsat
    if img is None:
        raise ValueError("fusion requires at least one image")
    return img


class _RGB:
    """Base for straight band-triplet composites (no averaging)."""
    id = ""
    sensors = ["sentinel", "landsat"]
    bands: list = []

    def build(self, images):
        img = _optical(images).select(self.bands)
        return img, VisSpec(
            bands=self.bands,
            min=_RGB_MIN,
            max=_RGB_MAX,
            gamma=_RGB_GAMMA,
            provenance="measured",
            citation="Direct Multi-Spectral Reflectance (Sentinel-2 / Landsat 8/9 SR)"
        )


class TrueColor(_RGB):
    id = "true_color"
    bands = ["red", "green", "blue"]


class FalseColorNIR(_RGB):
    id = "false_color_nir"
    bands = ["nir", "red", "green"]


class FalseColorSWIR(_RGB):
    id = "false_color_swir"
    bands = ["swir1", "nir", "red"]


class SCI(_RGB):
    """Scientific / Agriculture composite (SWIR2 / NIR / Blue) — matches legacy SR_B7,SR_B5,SR_B2."""
    id = "sci"
    bands = ["swir2", "nir", "blue"]


class _NormalizedDifference:
    """Base for (a−b)/(a+b) indices on reflectance."""
    id = ""
    sensors = ["sentinel", "landsat"]
    pair: list = []
    vis: VisSpec = VisSpec()

    def build(self, images):
        idx = _optical(images).normalizedDifference(self.pair).rename(self.id)
        return idx, self.vis


class NDVI(_NormalizedDifference):
    id = "ndvi"
    pair = ["nir", "red"]
    vis = VisSpec(
        bands=["ndvi"],
        min=-0.2,
        max=0.8,
        palette=_NDVI_PALETTE,
        provenance="measured",
        citation="Rouse et al. (1973) Normalized Difference Vegetation Index"
    )


class NDWI(_NormalizedDifference):
    # True McFeeters water = (Green − NIR)/(Green + NIR) — NOT NIR/SWIR moisture.
    id = "ndwi"
    pair = ["green", "nir"]
    vis = VisSpec(
        bands=["ndwi"],
        min=-0.3,
        max=0.5,
        palette=_WATER_PALETTE,
        provenance="measured",
        citation="McFeeters (1996) Normalized Difference Water Index"
    )


class NDBI(_NormalizedDifference):
    id = "ndbi"
    pair = ["swir1", "nir"]
    vis = VisSpec(
        bands=["ndbi"],
        min=-0.3,
        max=0.3,
        palette=_BUILTUP_PALETTE,
        provenance="measured",
        citation="Zha et al. (2003) Normalized Difference Built-Up Index"
    )


class LST:
    """Single-sensor Landsat Surface Temperature (uncorrected)."""
    id = "lst"
    sensors = ["landsat"]

    def build(self, images):
        if images.landsat is None:
            raise ValueError("LST requires Landsat imagery (Sentinel-2 has no thermal band)")
        lst = images.landsat.select(["lst"])
        # Ensure temperature is in Celsius
        lst_celsius = lst.where(lst.gt(100.0), lst.subtract(273.15))
        return lst_celsius, VisSpec(
            bands=["lst"],
            min=15,
            max=45,
            palette=_THERMAL_PALETTE,
            provenance="measured",
            citation="Landsat 8/9 TIRS Band 10 Surface Temperature"
        )


# ────────────────────────────────────────────────────────────────────
# Phase 1: real fusion strategies
# ────────────────────────────────────────────────────────────────────

class GapFill:
    """S2 (10 m) authoritative everywhere it has a clear pixel; Landsat 8/9 fills
    only S2 cloud/shadow gaps via `sentinel.unmask(landsat)`.
    """
    id = "gap_fill"
    sensors = ["sentinel", "landsat"]
    experimental = False

    def build(self, images):
        if images.sentinel is None and images.landsat is None:
            raise ValueError("gap_fill requires at least one sensor")
        if images.sentinel is None:
            return images.landsat.select(COMMON_OPTICAL), VisSpec(
                bands=["red", "green", "blue"],
                min=_RGB_MIN,
                max=_RGB_MAX,
                gamma=_RGB_GAMMA,
                provenance="modeled",
                citation="Landsat 8/9 Fill"
            )
        if images.landsat is None:
            return images.sentinel.select(COMMON_OPTICAL), VisSpec(
                bands=["red", "green", "blue"],
                min=_RGB_MIN,
                max=_RGB_MAX,
                gamma=_RGB_GAMMA,
                provenance="measured",
                citation="Sentinel-2 SR"
            )
        
        # Match band sets strictly (select 6 optical bands, excluding lst)
        s2_opt = images.sentinel.select(COMMON_OPTICAL)
        l8_opt = images.landsat.select(COMMON_OPTICAL)
        filled = s2_opt.unmask(l8_opt)
        return filled, VisSpec(
            bands=["red", "green", "blue"],
            min=_RGB_MIN,
            max=_RGB_MAX,
            gamma=_RGB_GAMMA,
            provenance="modeled",
            citation="Harmonized S2 + L8 Cloud-Gap Fill Fusion"
        )


class HarmonizedL8:
    """HLS-style S2 + harmonized-L8 (Claverie et al. 2018). Interleaved 30 m
    mosaic at the S2 footprint.
    """
    id = "harmonized_l8"
    sensors = ["sentinel", "landsat"]
    experimental = False

    def __init__(self, coefs: HLSCoefficients | None = None):
        self.coefs = coefs or HLSCoefficients()

    def build(self, images):
        if images.sentinel is None or images.landsat is None:
            raise ValueError("harmonized_l8 requires both Sentinel-2 and Landsat 8/9")
        s2_opt = images.sentinel.select(COMMON_OPTICAL)
        l8_opt = images.landsat.select(COMMON_OPTICAL)
        l8_h = apply_hls_bandpass(l8_opt, self.coefs)
        fused = s2_opt.unmask(l8_h)
        return fused, VisSpec(
            bands=["red", "green", "blue"],
            min=_RGB_MIN,
            max=_RGB_MAX,
            gamma=_RGB_GAMMA,
            provenance="modeled",
            citation="Claverie et al. (2018) Harmonized Landsat Sentinel (HLS) Algorithm"
        )


class RealLST:
    """Real Landsat LST product: per-pixel NDVI-based emissivity (Sobrino 2004)
    + grey-body correction `T_raw / ε^(1/4)`.
    """
    id = "real_lst"
    sensors = ["landsat"]
    experimental = False

    def build(self, images):
        if images.landsat is None:
            raise ValueError("real_lst requires Landsat imagery (Sentinel-2 has no thermal band)")
        l8 = images.landsat
        ndvi = l8.normalizedDifference(["nir", "red"]).rename("ndvi")
        # Sobrino NDVI-threshold emissivity:
        #   NDVI < 0.2           → ε = 0.97  (bare soil)
        #   NDVI > 0.5           → ε = 0.99  (full vegetation)
        #   0.2 ≤ NDVI ≤ 0.5     → linear ramp
        bare = ndvi.lt(0.2).multiply(0.97)
        veg  = ndvi.gt(0.5).multiply(0.99)
        mid  = (
            ndvi.gte(0.2).And(ndvi.lte(0.5))
               .multiply(0.97)
               .add(
                   ndvi.gte(0.2).And(ndvi.lte(0.5))
                      .multiply(ndvi.subtract(0.2))
                      .divide(0.3)
                      .multiply(0.02)
               )
        )
        epsilon = bare.add(veg).add(mid).rename("epsilon")
        # Grey-body approximation: T_corrected = T_raw / ε^(1/4).
        T_c = l8.select(["lst"])
        T_celsius = T_c.where(T_c.gt(100.0), T_c.subtract(273.15))
        eps_clamped = epsilon.clamp(0.85, 1.0)
        T_corrected = T_celsius.divide(eps_clamped.pow(0.25)).rename(["lst"])
        return T_corrected, VisSpec(
            bands=["lst"],
            min=15,
            max=45,
            palette=_THERMAL_PALETTE,
            provenance="modeled",
            citation="Sobrino et al. (2004) Per-pixel NDVI Emissivity & Grey-Body Correction"
        )


from .thermal_sharpening import ThermalSuperRes
from .sar_fusion import SAROpticalFusion

for _s in (
    TrueColor(), NDVI(), NDWI(), NDBI(),
    FalseColorNIR(), FalseColorSWIR(), SCI(), LST(),
    GapFill(), HarmonizedL8(), RealLST(), ThermalSuperRes(), SAROpticalFusion(),
):
    register(_s)
