"""GeoTIFF and PNG Export Engine with Scientific Metadata Sidecar Generation.

Generates download URLs for Earth Engine composite images via `getDownloadURL`
and pairs them with scientific metadata JSON sidecars (sensors, dates, cloud %, CRS).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import ee

logger = logging.getLogger(__name__)

def generate_export_download(
    image: ee.Image,
    geometry: ee.Geometry,
    strategy_id: str,
    sensor_names: list[str],
    date_range: list[str],
    cloud_cover: float,
    scale: int = 10,
    format_type: str = "GEO_TIFF"
) -> Dict[str, Any]:
    """Generates an export download URL and metadata sidecar payload."""
    try:
        export_args = {
            "name": f"orbiter_fusion_{strategy_id}",
            "scale": scale,
            "crs": "EPSG:4326",
            "region": geometry,
            "filePerBand": False
        }
        
        if format_type.upper() in ["GEO_TIFF", "GEOTIFF", "TIF"]:
            export_args["format"] = "GEO_TIFF"
        else:
            export_args["format"] = "PNG"

        download_url = image.getDownloadURL(export_args)

        metadata = {
            "platform": "Orbiter Fusion (ASTRAVISION)",
            "strategy": strategy_id,
            "sensors": sensor_names,
            "date_range": date_range,
            "cloud_cover_percent": cloud_cover,
            "spatial_resolution_meters": scale,
            "coordinate_reference_system": "EPSG:4326",
            "download_url": download_url,
            "format": export_args["format"]
        }

        return {
            "success": True,
            "download_url": download_url,
            "metadata": metadata
        }
    except Exception as e:
        logger.error(f"Export generation failed: {e}")
        raise e
