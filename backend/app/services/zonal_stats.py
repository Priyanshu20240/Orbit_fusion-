"""Zonal Statistics Time-Series Calculation Engine.

Computes reduceRegion mean, stdDev, min, and max over spatial AOI geometries across multi-temporal acquisition dates.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List
import ee

logger = logging.getLogger(__name__)

def compute_zonal_time_series(
    collection: ee.ImageCollection,
    geometry: ee.Geometry,
    band_name: str = "NDVI",
    scale: int = 30
) -> List[Dict[str, Any]]:
    """Calculates zonal mean, min, max, and stdDev per image in collection over geometry."""
    results = []
    try:
        def calculate_stats(img):
            date_str = img.date().format("YYYY-MM-dd")
            reduced = img.select(band_name).reduceRegion(
                reducer=ee.Reducer.mean()
                .combine(ee.Reducer.minMax(), sharedInputs=True)
                .combine(ee.Reducer.stdDev(), sharedInputs=True),
                geometry=geometry,
                scale=scale,
                maxPixels=1e9
            )
            return ee.Feature(None, {
                "date": date_str,
                "mean": reduced.get(f"{band_name}_mean"),
                "min": reduced.get(f"{band_name}_min"),
                "max": reduced.get(f"{band_name}_max"),
                "stdDev": reduced.get(f"{band_name}_stdDev")
            })

        fc = collection.map(calculate_stats).getInfo()
        
        for feat in fc.get("features", []):
            props = feat.get("properties", {})
            if props.get("mean") is not None:
                results.append({
                    "date": props.get("date"),
                    "mean": round(float(props.get("mean")), 4),
                    "min": round(float(props.get("min")), 4),
                    "max": round(float(props.get("max")), 4),
                    "stdDev": round(float(props.get("stdDev")), 4)
                })
        return results
    except Exception as e:
        logger.error(f"Zonal statistics computation failed: {e}")
        return results
