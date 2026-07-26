"""
Pydantic models for API request/response schemas.
"""
from datetime import date
from typing import Optional, List, Literal

from pydantic import BaseModel, Field, conlist, field_validator


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


# ─────────────────────────────────────────────────────────────────────────
# P0: the getMapId fusion contract. Schemas live here exclusively.
# ─────────────────────────────────────────────────────────────────────────

# ids MUST stay in lockstep with services.fusion.STRATEGY_REGISTRY and the
# frontend VISUALIZATIONS array.
Visualization = Literal[
    "true_color", "ndvi", "ndwi", "ndbi",
    "false_color_nir", "false_color_swir", "sci", "lst",
    # Phase 1 & 3: fusion & super-res strategies.
    "gap_fill", "harmonized_l8", "real_lst", "thermal_10m", "sar_optical",
]


class SceneCounts(BaseModel):
    """Real per-sensor scene counts (from size().getInfo())."""
    sentinel: int = 0
    landsat: int = 0


class FusionRequest(BaseModel):
    """Typed request for a getMapId fusion tile layer."""
    bounds: conlist(float, min_length=4, max_length=4) = Field(
        ..., description="[west, south, east, north] in EPSG:4326"
    )
    start_date: date
    end_date: date
    cloud_cover: float = Field(20.0, ge=0, le=100)
    visualization: Visualization = "true_color"
    platforms: List[Literal["sentinel", "landsat"]] = Field(
        default_factory=lambda: ["sentinel", "landsat"]
    )
    geojson: Optional[dict] = None

    @field_validator("end_date")
    @classmethod
    def _end_after_start(cls, v, info):
        start = info.data.get("start_date")
        if start is not None and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v


class FusionMapResponse(BaseModel):
    """Response: an XYZ tile template + real metadata (no server-side PNG)."""
    fusion_id: str
    tile_url_template: str = Field(..., description="XYZ template with {z}/{x}/{y}")
    bounds: List[List[float]] = Field(..., description="Leaflet [[S,W],[N,E]]")
    visualization: Visualization
    scene_counts: SceneCounts
    expires_at: str = Field(..., description="ISO-8601 mapid expiry")
    max_native_zoom: int = 14
    mapid: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────
# Phase 2: per-scene date list for the time-series scrubber.
# ─────────────────────────────────────────────────────────────────────────


class SceneDateEntry(BaseModel):
    """One per-scene date in the time-series overlap window.

    Returned by ``/api/scenes/overlap``. The frontend caches this list and
    loops the existing ``/api/fusion/gee-harmonize`` once per entry to mint
    a per-scene mapid.
    """
    # Pydantic v2 disallows a field name clashing with its type annotation
    # (`date: date` is rejected), so we use `python.alias` to keep the
    # external JSON name `date` while the attribute is `acquisition_date`.
    acquisition_date: date = Field(
        ...,
        alias="date",
        description="Acquisition date (day-rounded from STAC datetime)",
    )
    sensor: Literal["sentinel", "landsat"]
    scene_id: str
    cloud_cover: Optional[float] = None

    model_config = {"populate_by_name": True}


class ScenesOverlapResponse(BaseModel):
    """Response for ``/api/scenes/overlap``."""
    frames: List[SceneDateEntry] = Field(
        ..., description="Sorted by date asc, deduped on (date, sensor, scene_id)"
    )
    bucket: Literal["scene"] = "scene"  # future: "month" | "quarter" (not in Phase 2)
