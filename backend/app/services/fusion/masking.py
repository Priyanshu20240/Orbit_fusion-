"""Per-pixel cloud/shadow masking + shared band constants.

S2 uses SCL + Cloud Score+ (`cs_cdf`); Landsat uses QA_PIXEL bit flags. Masking
runs on the FULL per-scene band set (SCL / cs_cdf / QA_PIXEL still present),
BEFORE band-narrowing — see composite.py.
"""
from __future__ import annotations

import ee

# ── Cloud Score+ (the P0 default S2 mask; QA60 is dead for 2023+ dates) ──
CSPLUS_ID = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
CSPLUS_BAND = "cs_cdf"
CSPLUS_THRESHOLD = 0.60

# ── reflectance band sets → common names shared by both sensors ──
S2_REFLECTANCE_BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]
LANDSAT_REFLECTANCE_BANDS = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
COMMON_OPTICAL = ["blue", "green", "red", "nir", "swir1", "swir2"]
LANDSAT_THERMAL_BAND = "ST_B10"

# SCL classes to DROP (0 no-data, 1 saturated, 3 shadow, 8/9 cloud, 10 cirrus, 11 snow).
_SCL_DROP = (0, 1, 3, 8, 9, 10, 11)


def mask_s2(img):
    """Mask S2 using SCL clear-sky classes AND Cloud Score+ clear probability."""
    scl = img.select("SCL")
    clear = scl.neq(_SCL_DROP[0])
    for cls in _SCL_DROP[1:]:
        clear = clear.And(scl.neq(cls))
    cs = img.select(CSPLUS_BAND).gte(CSPLUS_THRESHOLD)
    return img.updateMask(clear).updateMask(cs)


def mask_landsat(img):
    """Mask Landsat C2 L2 using QA_PIXEL bits 1–4 (dilated/cirrus/cloud/shadow)."""
    qa = img.select("QA_PIXEL")
    dilated = 1 << 1
    cirrus = 1 << 2
    cloud = 1 << 3
    shadow = 1 << 4
    clear = (
        qa.bitwiseAnd(dilated).eq(0)
        .And(qa.bitwiseAnd(cirrus).eq(0))
        .And(qa.bitwiseAnd(cloud).eq(0))
        .And(qa.bitwiseAnd(shadow).eq(0))
    )
    return img.updateMask(clear)
