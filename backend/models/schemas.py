"""
Pydantic models for API request/response schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


class BoundingBox(BaseModel):
    """Rectangular Area of Interest coordinates"""
    min_lon: float = Field(..., description="Minimum longitude (west)", ge=-180, le=180)
    min_lat: float = Field(..., description="Minimum latitude (south)", ge=-90, le=90)
    max_lon: float = Field(..., description="Maximum longitude (east)", ge=-180, le=180)
    max_lat: float = Field(..., description="Maximum latitude (north)", ge=-90, le=90)

    def to_list(self) -> List[float]:
        """Convert to [west, south, east, north] format for STAC API"""
        return [self.min_lon, self.min_lat, self.max_lon, self.max_lat]


class SearchRequest(BaseModel):
    """Request model for satellite data search"""
    bbox: BoundingBox
    start_date: date = Field(..., description="Start date for search range")
    end_date: date = Field(..., description="End date for search range")
    max_cloud_cover: Optional[float] = Field(
        default=20.0,
        description="Maximum cloud cover percentage (0-100)",
        ge=0,
        le=100
    )
    limit: Optional[int] = Field(
        default=10,
        description="Maximum number of results to return",
        ge=1,
        le=100
    )


class SatelliteScene(BaseModel):
    """Individual satellite scene/image metadata"""
    id: str
    satellite: str
    datetime: str
    cloud_cover: Optional[float] = None
    thumbnail_url: Optional[str] = None
    download_url: Optional[str] = None
    tile_url: Optional[str] = None
    bands: Optional[dict] = None
    geometry: Optional[dict] = None


class SearchResponse(BaseModel):
    """Response model for satellite data search"""
    satellite: str
    total_results: int
    scenes: List[SatelliteScene]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    services: dict


class FusionProcessingRequest(BaseModel):
    """Request model for multi-satellite data fusion and analysis"""
    scene_ids: List[str] = Field(..., description="List of scene IDs to fuse")
    method: str = Field("median", description="Fusion method: mean, median, best_pixel")
    index: str = Field("ndvi", description="Analysis index: ndvi, ndwi, rgb")
    roi: Optional[dict] = Field(None, description="Geometry to clip the fusion to")


class FusionProcessingResponse(BaseModel):
    """Response model for fusion processing"""
    fusion_id: str = Field(..., description="Unique identifier for the fused result")
    stats: dict = Field(..., description="Calculated statistics (NDVI/NDWI breakdown)")
    preview_url: str = Field(..., description="URL for a preview image of the fused result")
    tile_url: str = Field(..., description="Tile URL template for the fused data")
    bounds: List[float] = Field(..., description="Coverage bounds")
    message: str = Field(..., description="Status message")
