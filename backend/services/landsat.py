"""
Landsat 8/9 Data Service
Fetches satellite imagery from Microsoft Planetary Computer STAC API
"""
import planetary_computer
from pystac_client import Client
from typing import List, Optional
from datetime import date
import logging
import time

logger = logging.getLogger(__name__)

# Microsoft Planetary Computer STAC endpoint (free, no API key required for catalog)
PLANETARY_COMPUTER_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# Landsat collection IDs
LANDSAT_C2_L2 = "landsat-c2-l2"  # Landsat Collection 2 Level-2


class LandsatService:
    """Service for querying and fetching Landsat 8/9 imagery"""
    
    def __init__(self):
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the STAC client for Planetary Computer"""
        try:
            self.client = Client.open(
                PLANETARY_COMPUTER_URL,
                modifier=planetary_computer.sign_inplace
            )
            logger.info("Successfully connected to Planetary Computer STAC API")
        except Exception as e:
            logger.error(f"Failed to connect to Planetary Computer: {e}")
            self.client = None
    
    def search_scenes(
        self,
        bbox: List[float],
        start_date: date,
        end_date: date,
        max_cloud_cover: float = 20.0,
        limit: int = 10
    ) -> dict:
        """
        Search for Landsat 8/9 scenes within a bounding box and date range.
        
        Args:
            bbox: [min_lon, min_lat, max_lon, max_lat] in EPSG:4326
            start_date: Start date for search
            end_date: End date for search
            max_cloud_cover: Maximum cloud cover percentage (0-100)
            limit: Maximum number of results
            
        Returns:
            dict with 'total_results' and 'scenes' list
        """
        if not self.client:
            self._initialize_client()
            if not self.client:
                return {"total_results": 0, "scenes": [], "error": "STAC client unavailable"}
        
        try:
            # Format date range for STAC query
            datetime_range = f"{start_date.isoformat()}/{end_date.isoformat()}"
            
            # Query the STAC catalog
            search = self.client.search(
                collections=[LANDSAT_C2_L2],
                bbox=bbox,
                datetime=datetime_range,
                query={
                    "eo:cloud_cover": {"lt": max_cloud_cover}
                },
                max_items=limit
            )
            
            # Process results
            scenes = []
            # Iterate generator directly to allow sleeping
            for item in search.items():
                scene = self._parse_stac_item(item)
                scenes.append(scene)
                time.sleep(0.2)  # Pace requests
            
            return {
                "total_results": len(scenes),
                "scenes": scenes
            }
            
        except Exception as e:
            logger.error(f"Landsat search failed: {e}")
            return {"total_results": 0, "scenes": [], "error": str(e)}
    
    def _parse_stac_item(self, item) -> dict:
        """Parse a STAC item into our scene format"""
        properties = item.properties
        
        # Extract band URLs
        bands = {}
        assets = item.assets
        
        # Key Landsat bands (30m resolution, except thermal)
        band_mapping = {
            "blue": "blue",          # Band 2
            "green": "green",        # Band 3
            "red": "red",            # Band 4
            "nir08": "nir",          # Band 5 (NIR)
            "swir16": "swir16",      # Band 6 (SWIR)
            "swir22": "swir22",      # Band 7 (SWIR)
            "qa_pixel": "qa_pixel"   # Quality assessment
        }
        
        for asset_key, asset in assets.items():
            if asset_key in band_mapping:
                bands[band_mapping[asset_key]] = asset.href
        
        # Get thumbnail
        thumbnail_url = None
        if "thumbnail" in assets:
            thumbnail_url = assets["thumbnail"].href
        elif "rendered_preview" in assets:
            thumbnail_url = assets["rendered_preview"].href
        
        # Try to get tile URL from tilejson or rendered_preview asset
        tile_url = None
        
        if "tilejson" in assets:
            tilejson_url = assets["tilejson"].href
            tile_url = tilejson_url.replace("/tilejson.json", "/tiles/WebMercatorQuad/{z}/{x}/{y}@1x.png")
        elif "rendered_preview" in assets:
            tile_url = assets["rendered_preview"].href
        elif bands.get("red"):
            tile_url = (
                "http://localhost:8000/api/cog/tiles/WebMercatorQuad/{z}/{x}/{y}"
                f"?url={bands['red']}&rescale=0,30000"
            )
        
        visual_url = None
        if "visual" in assets:
            visual_url = assets["visual"].href
            bands["visual"] = visual_url
        
        # Fallback for download_url: use visual if available, else red band for basic rendering
        download_url = visual_url or bands.get("red")
        
        return {
            "id": item.id,
            "satellite": f"Landsat-{properties.get('landsat:satellite', '8/9')}",
            "datetime": properties.get("datetime", ""),
            "cloud_cover": properties.get("eo:cloud_cover"),
            "thumbnail_url": thumbnail_url,
            "download_url": download_url,
            "tile_url": tile_url, # New field
            "bands": bands,
            "geometry": item.geometry if hasattr(item, 'geometry') else None,
            "properties": {
                "platform": properties.get("platform", "landsat"),
                "landsat:scene_id": properties.get("landsat:scene_id"),
                "landsat:wrs_path": properties.get("landsat:wrs_path"),
                "landsat:wrs_row": properties.get("landsat:wrs_row"),
                "resolution": 30,
            }
        }
    
    def get_scene_by_id(self, scene_id: str) -> Optional[dict]:
        """Get a specific scene by its ID"""
        if not self.client:
            self._initialize_client()
            if not self.client:
                return None
        
        try:
            search = self.client.search(
                collections=[LANDSAT_C2_L2],
                ids=[scene_id]
            )
            
            items = list(search.items())
            if items:
                return self._parse_stac_item(items[0])
            return None
            
        except Exception as e:
            logger.error(f"Failed to get Landsat scene {scene_id}: {e}")
            return None


# Singleton instance
landsat_service = LandsatService()
