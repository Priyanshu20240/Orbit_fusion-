"""
ISRO Bhuvan Service
Integrates with ISRO's Bhuvan Web Map Service (WMS) for Indian satellite data
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Bhuvan WMS endpoints
BHUVAN_WMS_BASE = "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms"
BHUVAN_WMTS_BASE = "https://bhuvan-ras2.nrsc.gov.in/tilecache/tilecache.py"

# Available Bhuvan layers (limited selection for demo)
BHUVAN_LAYERS = {
    "india_mosaic": {
        "name": "India Satellite Mosaic",
        "layer_id": "india_sat",
        "description": "High-resolution satellite mosaic of India"
    },
    "lulc": {
        "name": "Land Use Land Cover",
        "layer_id": "lulc50k",
        "description": "Land use/land cover classification"
    },
    "dem": {
        "name": "Digital Elevation Model",
        "layer_id": "cartodem",
        "description": "CartoDEM elevation data"
    }
}


class BhuvanService:
    """
    Service for accessing ISRO Bhuvan WMS/WFS data.
    
    Note: Bhuvan provides WMS tiles, not individual scenes like Sentinel/Landsat.
    This service generates tile URLs for the frontend to display.
    """
    
    def __init__(self):
        self.wms_base = BHUVAN_WMS_BASE
        self.wmts_base = BHUVAN_WMTS_BASE
    
    def get_available_layers(self) -> dict:
        """Get list of available Bhuvan layers"""
        return BHUVAN_LAYERS
    
    def get_wms_url(self, layer_id: str = "india_sat") -> str:
        """
        Generate WMS URL for a Bhuvan layer.
        This URL can be used directly in Leaflet as a tile layer.
        
        Args:
            layer_id: The Bhuvan layer identifier
            
        Returns:
            WMS GetMap URL template
        """
        return (
            f"{self.wms_base}?"
            f"service=WMS&version=1.1.1&request=GetMap"
            f"&layers={layer_id}"
            f"&styles="
            f"&format=image/png"
            f"&transparent=true"
            f"&srs=EPSG:4326"
            f"&bbox={{bbox}}"
            f"&width=256&height=256"
        )
    
    def get_tile_url_template(self, layer_id: str = "india_sat") -> str:
        """
        Generate a Leaflet-compatible tile URL template.
        
        Returns:
            URL template with {z}/{x}/{y} placeholders
        """
        # Bhuvan TileCache URL pattern
        return f"{self.wmts_base}/{layer_id}/{{z}}/{{x}}/{{y}}.png"
    
    def get_layer_metadata(self, layer_id: str) -> Optional[dict]:
        """Get metadata for a specific layer"""
        for key, layer in BHUVAN_LAYERS.items():
            if layer["layer_id"] == layer_id:
                return {
                    "id": layer_id,
                    "name": layer["name"],
                    "description": layer["description"],
                    "wms_url": self.get_wms_url(layer_id),
                    "tile_url": self.get_tile_url_template(layer_id),
                    "source": "ISRO Bhuvan",
                    "coverage": "India"
                }
        return None


# Singleton instance
bhuvan_service = BhuvanService()
