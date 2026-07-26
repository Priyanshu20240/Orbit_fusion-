"""Bounded, masked composites.

Ordering contract (fixes the "SCL not in band list" trap): filter → sort →
limit → (S2: linkCollection cs_cdf) → map(mask) on the FULL band set → select
(narrow to reflectance + thermal) → reduce. Masking-then-median composites
only clear pixels. No `reproject` / `sampleRectangle` (those forced the old
numpy download path).
"""
from __future__ import annotations

import ee

from .masking import (
    CSPLUS_BAND,
    CSPLUS_ID,
    LANDSAT_REFLECTANCE_BANDS,
    LANDSAT_THERMAL_BAND,
    S2_REFLECTANCE_BANDS,
    mask_landsat,
    mask_s2,
)

S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
L8_COLLECTION = "LANDSAT/LC08/C02/T1_L2"
L9_COLLECTION = "LANDSAT/LC09/C02/T1_L2"


def _reduce(coll, method):
    if method == "mean":
        return coll.mean()
    if method == "mosaic":
        return coll.mosaic()
    return coll.median()


def s2_collection(geom, start_date, end_date, cloud_cover, max_scenes):
    """Masked + narrowed S2 collection, ready to reduce or count."""
    csplus = ee.ImageCollection(CSPLUS_ID)
    return (
        ee.ImageCollection(S2_COLLECTION)
        .filterBounds(geom)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", cloud_cover))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
        .limit(max_scenes)
        .linkCollection(csplus, [CSPLUS_BAND])   # attach cs_cdf BEFORE masking
        .map(mask_s2)                            # (1) MASK on full band set
        .select(S2_REFLECTANCE_BANDS)            # (2) NARROW to reflectance
    )


def landsat_collection(geom, start_date, end_date, cloud_cover, max_scenes):
    """Masked + narrowed Landsat 8/9 collection (reflectance + thermal)."""
    l8 = ee.ImageCollection(L8_COLLECTION)
    l9 = ee.ImageCollection(L9_COLLECTION)
    return (
        l8.merge(l9)
        .filterBounds(geom)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte("CLOUD_COVER", cloud_cover))
        .sort("CLOUD_COVER")
        .limit(max_scenes)
        .map(mask_landsat)                                          # (1) MASK
        .select(LANDSAT_REFLECTANCE_BANDS + [LANDSAT_THERMAL_BAND])  # (2) NARROW
    )


def composite(collection, method="mosaic"):
    """Reduce a masked+narrowed collection to a single image."""
    return _reduce(collection, method)


def scene_count(collection) -> int:
    """Real scene count — `size().getInfo()`, not a fabricated placeholder."""
    return collection.size().getInfo()
