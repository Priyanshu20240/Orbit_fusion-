"""
Tile Service - Generate tile URLs for satellite imagery
Provides XYZ tile URL templates for COG (Cloud Optimized GeoTIFF) files
"""
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

# Use local Titiler instance to avoid rate limiting and external failures
TITILER_ENDPOINT = "http://localhost:8000/api/cog"

# Alternative: Use Planetary Computer's tile endpoint
PC_TILE_ENDPOINT = "https://planetarycomputer.microsoft.com/api/data/v1"


class TileService:
    """
    Service for generating XYZ tile URLs from COG sources.
    Uses Titiler for dynamic tile generation from Cloud Optimized GeoTIFFs.
    """
    
    def __init__(self):
        self.titiler_url = TITILER_ENDPOINT
    
    def get_sentinel_tile_url(self, scene: dict, bands: List[str] = None) -> Optional[str]:
        """
        Generate XYZ tile URL for a Sentinel-2 scene.
        
        Args:
            scene: Scene dict with band URLs
            bands: List of bands to use [red, green, blue] or None for natural color
            
        Returns:
            XYZ tile URL template with {z}/{x}/{y} placeholders
        """
        if not scene or not scene.get("bands"):
            return None
        
        scene_bands = scene.get("bands", {})
        
        # Default to natural color (RGB)
        if bands is None:
            bands = ["red", "green", "blue"]
        
        # Get band URLs
        band_urls = []
        for band in bands:
            if band in scene_bands:
                band_urls.append(scene_bands[band])
            else:
                logger.warning(f"Band {band} not found in scene")
                return None
        
        if len(band_urls) < 3:
            return None
        
        # Generate Titiler XYZ URL
        # Format: /cog/tiles/{z}/{x}/{y}?url=COG_URL
        tile_url = (
            f"{self.titiler_url}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}@2x.png"
            f"?url={band_urls[0]}"
            f"&bidx=1"
            f"&rescale=0,3000"
            f"&colormap_name=viridis"
        )
        
        return tile_url
    
    def get_sentinel_rgb_tile_url(self, scene: dict) -> Optional[str]:
        """
        Generate RGB composite tile URL for Sentinel-2.
        Uses the visual band if available, otherwise constructs from R/G/B.
        """
        if not scene:
            return None
        
        # Check for pre-rendered visual asset
        if scene.get("download_url"):
            visual_url = scene["download_url"]
            return (
                f"{self.titiler_url}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}@2x.png"
                f"?url={visual_url}"
                f"&rescale=0,255"
            )
        
        return self.get_sentinel_tile_url(scene)
    
    def get_landsat_tile_url(self, scene: dict) -> Optional[str]:
        """
        Generate XYZ tile URL for a Landsat scene.
        Landsat uses different band naming.
        """
        if not scene or not scene.get("bands"):
            return None
        
        bands = scene.get("bands", {})
        
        # Landsat natural color uses bands 4, 3, 2 (red, green, blue)
        if "red" in bands:
            red_url = bands["red"]
            return (
                f"{self.titiler_url}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}@2x.png"
                f"?url={red_url}"
                f"&bidx=1"
                f"&rescale=0,30000"
            )
        
        return None
    
    def get_ndvi_tile_url(self, scene: dict, satellite: str = "sentinel") -> Optional[str]:
        """
        Generate NDVI tile URL.
        NDVI = (NIR - Red) / (NIR + Red)
        """
        if not scene or not scene.get("bands"):
            return None
        
        bands = scene.get("bands", {})
        
        if "nir" not in bands or "red" not in bands:
            logger.warning("NIR or Red band not available for NDVI")
            return None
        
        nir_url = bands["nir"]
        red_url = bands["red"]
        
        # Titiler expression for NDVI
        # Using the expression endpoint
        return (
            f"{self.titiler_url}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}@2x.png"
            f"?url={nir_url}"
            f"&expression=(b1-b2)/(b1+b2)"
            f"&rescale=-1,1"
            f"&colormap_name=rdylgn"
        )
    
    def get_bhuvan_wms_url(self, layer_id: str = "india_sat") -> str:
        """
        Get Bhuvan WMS tile URL template.
        """
        return (
            "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms?"
            f"service=WMS&version=1.1.1&request=GetMap"
            f"&layers={layer_id}"
            f"&styles=&format=image/png&transparent=true"
            f"&srs=EPSG:3857"
            f"&bbox={{bbox-epsg-3857}}"
            f"&width=256&height=256"
        )
    
    def get_scene_tile_info(self, scene: dict) -> Dict:
        """
        Get all available tile URLs for a scene.
        """
        satellite = scene.get("satellite", "").lower()
        
        result = {
            "scene_id": scene.get("id"),
            "satellite": satellite,
            "tiles": {}
        }
        
        if "sentinel" in satellite:
            rgb_url = self.get_sentinel_rgb_tile_url(scene)
            if rgb_url:
                result["tiles"]["rgb"] = rgb_url
            
            ndvi_url = self.get_ndvi_tile_url(scene, "sentinel")
            if ndvi_url:
                result["tiles"]["ndvi"] = ndvi_url
                
        elif "landsat" in satellite:
            rgb_url = self.get_landsat_tile_url(scene)
            if rgb_url:
                result["tiles"]["rgb"] = rgb_url
        
        return result


# Singleton instance
tile_service = TileService()
