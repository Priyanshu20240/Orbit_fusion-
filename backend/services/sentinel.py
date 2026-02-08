import planetary_computer
from pystac_client import Client
from typing import List, Optional
from datetime import date
import logging
import time

logger = logging.getLogger(__name__)

# Microsoft Planetary Computer STAC endpoint
PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# Sentinel-2 collection IDs (Planetary Computer)
SENTINEL_2_L2A = "sentinel-2-l2a"

class SentinelService:
    """Service for querying and fetching Sentinel-2 imagery via Planetary Computer"""
    
    def __init__(self):
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the STAC client with signing"""
        try:
            # Use sign_inplace to automatically sign assets with SAS tokens
            self.client = Client.open(
                PC_STAC_URL,
                modifier=planetary_computer.sign_inplace
            )
            logger.info("Successfully connected to Planetary Computer STAC API (Sentinel)")
        except Exception as e:
            logger.error(f"Failed to connect to STAC API: {e}")
            self.client = None
    
    def search_scenes(
        self,
        bbox: List[float],
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
        limit: int = 10
    ) -> dict:
        if not self.client:
            self._initialize_client()
            if not self.client:
                return {"total_results": 0, "scenes": [], "error": "STAC client unavailable"}
        
        try:
            datetime_range = f"{start_date.isoformat()}/{end_date.isoformat()}"
            
            # Query the STAC catalog
            search = self.client.search(
                collections=[SENTINEL_2_L2A],
                bbox=bbox,
                datetime=datetime_range,
                query={
                    "eo:cloud_cover": {"lt": max_cloud_cover}
                },
                max_items=limit
            )
            
            scenes = []
            # Iterate generator directly to allow sleeping between sign_inplace calls
            for item in search.items():
                scene = self._parse_stac_item(item)
                scenes.append(scene)
                time.sleep(0.2)  # Short sleep to pace requests
            
            return {
                "total_results": len(scenes),
                "scenes": scenes
            }
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {"total_results": 0, "scenes": [], "error": str(e)}
    
    def _parse_stac_item(self, item) -> dict:
        properties = item.properties
        assets = item.assets
        
        # Key Sentinel-2 bands (PC naming)
        # PC usually uses B02, B03 etc.
        bands = {}
        band_mapping = {
            "B02": "blue",
            "B03": "green",
            "B04": "red",
            "B08": "nir",
            "B11": "swir16",
            "B12": "swir22",
            "SCL": "scl"
        }
        
        for asset_key, asset in assets.items():
            if asset_key in band_mapping:
                bands[band_mapping[asset_key]] = asset.href
            elif asset_key.lower() in ["red", "green", "blue", "nir"]:
                # Sometimes aliased
                bands[asset_key.lower()] = asset.href
        
        # Thumbnail/Visual
        # PC Sentinel-2 usually has 'visual' (TCI) and 'preview' (reduced res)
        thumbnail_url = None
        if "visual" in assets:
             thumbnail_url = assets["visual"].href
        elif "rendered_preview" in assets:
             thumbnail_url = assets["rendered_preview"].href
             
        visual_url = None
        if "visual" in assets:
            visual_url = assets["visual"].href
            bands["visual"] = visual_url
        
        # Try to get tile URL from tilejson or rendered_preview asset
        # These assets are pre-configured by PC to work directly
        tile_url = None
        
        if "tilejson" in assets:
            # tilejson contains URLs for interactive map tiles
            tilejson_url = assets["tilejson"].href
            # Extract the tiles URL template from tilejson (we'll use a simplified approach)
            # The tilejson href often looks like: .../tilejson.json?assets=visual&...
            # We can transform it to a direct tiles endpoint
            tile_url = tilejson_url.replace("/tilejson.json", "/tiles/WebMercatorQuad/{z}/{x}/{y}@1x.png")
        elif "rendered_preview" in assets:
            # rendered_preview is a good fallback for thumbnails
            tile_url = assets["rendered_preview"].href
        elif bands.get("red"):
            # Last resort: use local Titiler with individual band
            tile_url = (
                "http://localhost:8000/api/cog/tiles/WebMercatorQuad/{z}/{x}/{y}"
                f"?url={bands['red']}&rescale=0,10000"
            )
        
        return {
            "id": item.id,
            "satellite": "Sentinel-2",
            "datetime": properties.get("datetime", ""),
            "cloud_cover": properties.get("eo:cloud_cover"),
            "thumbnail_url": thumbnail_url,
            "download_url": visual_url,
            "tile_url": tile_url,
            "bands": bands,
            "geometry": item.geometry if hasattr(item, 'geometry') else None,
            "properties": {
                "platform": properties.get("platform", "sentinel-2"),
                "sun_elevation": properties.get("sun_elevation"),
                "proj:epsg": properties.get("proj:epsg", 32632),
            }
        }
        
    def get_scene_by_id(self, scene_id: str) -> Optional[dict]:
        if not self.client:
            self._initialize_client()
        try:
            search = self.client.search(collections=[SENTINEL_2_L2A], ids=[scene_id])
            items = list(search.items())
            if items:
                return self._parse_stac_item(items[0])
            return None
        except Exception as e:
            logger.error(f"Failed to get scene: {e}")
            return None

    def get_band_url(self, scene_id: str, band: str) -> Optional[str]:
        # Simple implementation, relies on full search or we could optimizing by ID
        scene = self.get_scene_by_id(scene_id)
        if scene and scene.get("bands"):
             return scene["bands"].get(band)
        return None

sentinel_service = SentinelService()
