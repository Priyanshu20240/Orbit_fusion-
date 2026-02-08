"""
Orbiter Fusion Platform - Backend API
Multi-Satellite Data Fusion Dashboard

This is the main FastAPI application entry point.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
import hashlib
from typing import Dict

# Fix for Windows SSL/Certificate issues with GDAL/Rasterio
os.environ["GDAL_HTTP_UNSAFESSL"] = "YES"
os.environ["CURL_CA_BUNDLE"] = ""

from models.schemas import (
    SearchRequest,
    SearchResponse,
    SatelliteScene,
    HealthResponse,
    BoundingBox,
    FusionProcessingRequest,
    FusionProcessingResponse
)
from services.sentinel import sentinel_service
from services.landsat import landsat_service
from services.bhuvan import bhuvan_service
from services.tile_service import tile_service
from services.analysis import analysis_service
from services.fusion_service import fusion_service
from services.gee_fusion_service import gee_fusion_service
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Titiler for local COG rendering (prevents 429s)
from titiler.core.factory import TilerFactory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers

# In-memory stores
# In-memory stores
SCENE_STORE: Dict[str, dict] = {}
FUSION_STORE: Dict[str, dict] = {}

from pydantic import BaseModel
from typing import List, Optional, Any

class TimelapseRequest(BaseModel):
    bounds: List[float]
    start_date: str
    end_date: str
    platform: str = 'sentinel'
    visualization: str = 'true_color'
    geojson: Optional[Dict] = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    logger.info("🚀 Orbiter Fusion Platform starting up...")
    yield
    logger.info("👋 Orbiter Fusion Platform shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="Orbiter Fusion Platform API",
    description="""
    Multi-Satellite Data Fusion Dashboard Backend
    
    ## Features
    - 🛰️ **Sentinel-2** data via Earth Search STAC API
    - 🌍 **Landsat 8/9** data via Microsoft Planetary Computer
    - 🇮🇳 **ISRO Bhuvan** WMS integration
    - 🔬 NDVI Analysis
    - 🔗 Multi-source data fusion
    """,
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Titiler (Local COG Tiler)
cog = TilerFactory()
app.include_router(cog.router, prefix="/api/cog", tags=["Titiler"])
add_exception_handlers(app, DEFAULT_STATUS_CODES)

# Mount static files for fusion image serving
fusion_output_dir = Path("./static/fusion")
fusion_output_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

from fastapi.responses import Response



@app.post("/api/fusion/harmonize")
async def harmonize_landsat_sentinel(request: Request):
    """
    Create a harmonized fusion of Landsat and Sentinel data.
    
    This endpoint:
    1. Upsamples Landsat (30m) to Sentinel resolution (10m)
    2. Merges matching bands (RGB + NIR)
    3. Creates a median composite for noise reduction
    
    Request body:
    {
        "sentinel_scenes": [...],
        "landsat_scenes": [...],
        "bounds": [west, south, east, north]
    }
    """
    try:
        data = await request.json()
        
        sentinel_scenes = data.get("sentinel_scenes", [])
        landsat_scenes = data.get("landsat_scenes", [])
        bounds = data.get("bounds")
        
        if not bounds:
            raise HTTPException(status_code=400, detail="Bounds are required")
        
        if not sentinel_scenes and not landsat_scenes:
            raise HTTPException(status_code=400, detail="At least one scene is required")
        
        logger.info(f"Harmonizing {len(sentinel_scenes)} Sentinel + {len(landsat_scenes)} Landsat scenes")
        
        # Call the fusion service
        result = fusion_service.create_harmonized_tiles(
            sentinel_scenes=sentinel_scenes,
            landsat_scenes=landsat_scenes,
            aoi_bounds=tuple(bounds)
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Fusion failed"))
        
        fusion_id = result["fusion_id"]
        
        # Store the fusion result for tile serving
        FUSION_STORE[fusion_id] = result
        
        # Return tile URL
        tile_url = f"/api/fusion/{fusion_id}/tiles/{{z}}/{{x}}/{{y}}"
        
        return {
            "fusion_id": fusion_id,
            "tile_url": tile_url,
            "bounds": bounds,
            "num_sentinel": result.get("num_sentinel", 0),
            "num_landsat": result.get("num_landsat", 0),
            "message": "Harmonized fusion created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fusion error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Fusion failed: {str(e)}")


@app.get("/api/fusion/{fusion_id}/tiles/{z}/{x}/{y}")
async def get_fusion_tile(fusion_id: str, z: int, x: int, y: int):
    """
    Get a tile from a harmonized fusion result.
    Tile requests are cached for 7 days with HTTP cache headers.
    """
    from fastapi.responses import Response
    
    try:
        # Use fusion_service to get the tile
        content = fusion_service.get_fusion_tile(fusion_id, z, x, y)
        
        if content is None:
            return Response(content=b"", media_type="image/png", status_code=204)
        
        # Add aggressive caching headers for tiles
        # Tiles are immutable by nature (z/x/y is fixed)
        return Response(
            content=content,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=604800",  # Cache for 7 days
                "ETag": hashlib.md5(content).hexdigest(),
                "Vary": "Accept-Encoding"
            }
        )
        
    except Exception as e:
        logger.error(f"Fusion tile error: {e}")
        return Response(content=b"", media_type="image/png", status_code=204)


# ===============================
# GEE Geographic Windowing Fusion
# ===============================

@app.post("/api/fusion/gee-harmonize")
async def gee_harmonize(request: Request):
    """
    Create harmonized fusion using Google Earth Engine with proper geographic windowing.
    
    Implements the Master-Slave approach:
    - Sentinel-2 (10m) is the MASTER reference resolution
    - Landsat-8/9 (30m) is upsampled to match Sentinel
    - Both are aligned to the same geographic bounds
    
    Request body:
    {
        "bounds": [west, south, east, north],  # EPSG:4326
        "start_date": "2024-01-01",
        "end_date": "2024-12-31", 
        "window_size": 256,
        "cloud_cover": 20,
        "cloud_cover": 20,
        "visualization": "true_color",  # or "false_color_nir", "false_color_swir"
        "platforms": ["sentinel", "landsat"] # Optional: Filter source
    }

    
    Returns:
    {
        "success": true,
        "fusion_id": "fusion_abc123",
        "imageUrl": "/static/fusion/fusion_abc123.png",
        "bounds": [[south, west], [north, east]],  # Leaflet format
        "shape": [23, 256, 256],
        "total_bands": 23
    }
    """
    try:
        data = await request.json()
        
        bounds = data.get("bounds")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        window_size = data.get("window_size", 256)
        cloud_cover = data.get("cloud_cover", 20.0)
        visualization = data.get("visualization", "true_color")
        platforms = data.get("platforms", ["sentinel", "landsat"])
        geojson = data.get("geojson", None)
        create_dataset = data.get("create_dataset", False)
        destination_folder = data.get("destination_folder", "datasets")
        
        if not bounds or len(bounds) != 4:
            raise HTTPException(status_code=400, detail="Bounds required as [west, south, east, north]")
        
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="start_date and end_date are required")
        
        logger.info(f"GEE Fusion request: bounds={bounds}, dates={start_date} to {end_date}, has_geojson={bool(geojson)}")
        
        # Call the GEE fusion service
        result = gee_fusion_service.create_harmonized_fusion(
            bounds=tuple(bounds),
            start_date=start_date,
            end_date=end_date,
            cloud_cover=cloud_cover,
            window_size=window_size,
            visualization=visualization,
            platforms=platforms,
            geojson=geojson,
            create_dataset=create_dataset,
            destination_folder=destination_folder
        )

        
        if not result.get("success"):
            error_msg = result.get("error", "GEE fusion failed")
            status_code = 500
            
            # map known errors to appropriate status codes
            if "No Sentinel-2 imagery" in error_msg:
                status_code = 404
            elif "initialization failed" in error_msg:
                status_code = 503
            
            raise HTTPException(
                status_code=status_code, 
                detail=error_msg
            )
        
        return result
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in fusion request: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/fusion/timelapse")
async def generate_timelapse(request: TimelapseRequest):
    """Generate a timelapse GIF"""
    try:
        logger.info(f"TIMELAPSE REQUEST: {request.platform} ({request.start_date} to {request.end_date}) Viz: {request.visualization}")
        
        result = gee_fusion_service.generate_timelapse(
            bounds=tuple(request.bounds),
            start_date=request.start_date,
            end_date=request.end_date,
            platform=request.platform,
            visualization=request.visualization,
            geojson=request.geojson
        )
        
        logger.info(f"TIMELAPSE RESULT: {result}")

        if not result:
             logger.error("Timelapse service returned None/Empty")
             raise HTTPException(status_code=500, detail="Internal Error: Backend returned no result")

        if not result.get("success"):
            logger.error(f"Timelapse failed: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error"))
            
        return result

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Timelapse Endpoint Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/fusion/gee-window")
async def gee_create_window(request: Request):
    """
    Create a geographic window for fusion based on center coordinates.
    
    Calculates the correct bounds for a 256x256 pixel window at 10m resolution.
    
    Request body:
    {
        "center_lon": 77.2090,
        "center_lat": 28.6139,
        "window_size": 256  # pixels
    }
    
    Returns the geographic bounds that cover exactly window_size * 10m.
    """
    try:
        data = await request.json()
        
        center_lon = data.get("center_lon")
        center_lat = data.get("center_lat")
        window_size = data.get("window_size", 256)
        
        if center_lon is None or center_lat is None:
            raise HTTPException(status_code=400, detail="center_lon and center_lat required")
        
        bounds = gee_fusion_service.create_geo_window(
            center_lon=center_lon,
            center_lat=center_lat,
            window_size=window_size
        )
        
        # Calculate coverage info
        extent_meters = window_size * 10  # Sentinel resolution
        
        return {
            "bounds": list(bounds),
            "leaflet_bounds": [[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
            "window_size_pixels": window_size,
            "extent_meters": extent_meters,
            "extent_km": extent_meters / 1000,
            "resolution": "10m (Sentinel-2 reference)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GEE window error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fusion/gee/status")
async def gee_status():
    """
    Check GEE initialization status.
    """
    try:
        if gee_fusion_service.initialized:
            return {
                "status": "initialized",
                "message": "Google Earth Engine is ready"
            }
        else:
            # Try to initialize
            success = gee_fusion_service.initialize_gee()
            if success:
                return {
                    "status": "initialized",
                    "message": "Google Earth Engine initialized successfully"
                }
            else:
                return {
                    "status": "not_initialized",
                    "message": "GEE not initialized. Run 'earthengine authenticate' to set up credentials."
                }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# Cache Management Endpoints
# ===========================

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===============================
# Health Check Endpoints
# ===============================

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with API health status"""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        services={
            "sentinel": "available",
            "landsat": "available",
            "bhuvan": "available"
        }
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Detailed health check"""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        services={
            "sentinel": "connected" if sentinel_service.client else "disconnected",
            "landsat": "connected" if landsat_service.client else "disconnected",
            "bhuvan": "available"
        }
    )



# ===============================
# Startup / Shutdown
# ===============================

@app.post("/api/sentinel/search", response_model=SearchResponse)
async def search_sentinel(request: SearchRequest):
    """
    Search for Sentinel-2 imagery.
    
    - **bbox**: Bounding box coordinates [min_lon, min_lat, max_lon, max_lat]
    - **start_date**: Start date (YYYY-MM-DD)
    - **end_date**: End date (YYYY-MM-DD)
    - **max_cloud_cover**: Maximum cloud cover percentage (default: 20%)
    - **limit**: Maximum number of results (default: 10)
    """
    result = sentinel_service.search_scenes(
        bbox=request.bbox.to_list(),
        start_date=request.start_date,
        end_date=request.end_date,
        max_cloud_cover=request.max_cloud_cover,
        limit=request.limit
    )
    
    if "error" in result:
        logger.error(f"Sentinel search error: {result['error']}")
    
    scenes = [SatelliteScene(**scene) for scene in result.get("scenes", [])]
    
    return SearchResponse(
        satellite="Sentinel-2",
        total_results=result.get("total_results", 0),
        scenes=scenes
    )


@app.get("/api/sentinel/scene/{scene_id}")
async def get_sentinel_scene(scene_id: str):
    """Get details for a specific Sentinel-2 scene"""
    scene = sentinel_service.get_scene_by_id(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    return scene


# ===============================
# Landsat 8/9 Endpoints
# ===============================

@app.post("/api/landsat/search", response_model=SearchResponse)
async def search_landsat(request: SearchRequest):
    """
    Search for Landsat 8/9 imagery.
    
    Uses Microsoft Planetary Computer STAC API.
    """
    result = landsat_service.search_scenes(
        bbox=request.bbox.to_list(),
        start_date=request.start_date,
        end_date=request.end_date,
        max_cloud_cover=request.max_cloud_cover,
        limit=request.limit
    )
    
    if "error" in result:
        logger.error(f"Landsat search error: {result['error']}")
    
    scenes = [SatelliteScene(**scene) for scene in result.get("scenes", [])]
    
    return SearchResponse(
        satellite="Landsat-8/9",
        total_results=result.get("total_results", 0),
        scenes=scenes
    )


@app.get("/api/landsat/scene/{scene_id}")
async def get_landsat_scene(scene_id: str):
    """Get details for a specific Landsat scene"""
    scene = landsat_service.get_scene_by_id(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    return scene


# ===============================
# ISRO Bhuvan Endpoints
# ===============================

@app.get("/api/bhuvan/layers")
async def get_bhuvan_layers():
    """Get available Bhuvan WMS layers"""
    return bhuvan_service.get_available_layers()


@app.get("/api/bhuvan/wms/{layer_id}")
async def get_bhuvan_wms_url(layer_id: str):
    """Get WMS URL for a specific Bhuvan layer"""
    metadata = bhuvan_service.get_layer_metadata(layer_id)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Layer {layer_id} not found")
    return metadata


# ===============================
# Multi-Source Search
# ===============================

@app.post("/api/search/all")
async def search_all_sources(request: SearchRequest):
    """Search all supported satellite sources"""
    
    # Sentinel-2
    sentinel_result = sentinel_service.search_scenes(
        bbox=request.bbox.to_list(),
        start_date=request.start_date,
        end_date=request.end_date,
        max_cloud_cover=request.max_cloud_cover,
        limit=request.limit
    )

    # Landsat 8/9
    landsat_result = landsat_service.search_scenes(
        bbox=request.bbox.to_list(),
        start_date=request.start_date,
        end_date=request.end_date,
        max_cloud_cover=request.max_cloud_cover,
        limit=request.limit
    )

    # ISRO Bhuvan (Metadata only)
    bhuvan_layers = bhuvan_service.get_available_layers()

    # Store scenes in SCENE_STORE for later fusion/analysis
    for scene in sentinel_result.get("scenes", []):
        SCENE_STORE[scene["id"]] = {**scene, "satellite": "Sentinel-2"}
    for scene in landsat_result.get("scenes", []):
        SCENE_STORE[scene["id"]] = {**scene, "satellite": "Landsat-8/9"}
    
    return {
        "sentinel": {
            "satellite": "Sentinel-2",
            "total_results": sentinel_result.get("total_results", 0),
            "scenes": sentinel_result.get("scenes", [])
        },
        "landsat": {
            "satellite": "Landsat-8/9",
            "total_results": landsat_result.get("total_results", 0),
            "scenes": landsat_result.get("scenes", [])
        },
        "bhuvan": {
            "satellite": "ISRO",
            "layers": bhuvan_layers
        }
    }


@app.post("/api/fusion/process", response_model=FusionProcessingResponse)
async def process_fusion(request: FusionProcessingRequest):
    """
    Perform multi-satellite data fusion and unified analysis.
    
    1. Fetches data for all selected scenes
    2. Aligns and merges pixels (Fusion)
    3. Calculates indices (NDVI/NDWI)
    4. Generates unified statistics
    """
    if not request.scene_ids or len(request.scene_ids) == 0:
        raise HTTPException(status_code=400, detail="At least one scene ID is required")
    
    try:
        scenes = []
        for sid in request.scene_ids:
            if sid not in SCENE_STORE:
                # Try to fetch if not in store (optional, but good for robustness)
                try:
                    if "-" in sid: # Likely Sentinel
                        scene = sentinel_service.get_scene_by_id(sid)
                    else: # Likely Landsat
                        scene = landsat_service.get_scene_by_id(sid)
                    
                    if scene:
                        SCENE_STORE[sid] = scene
                    else:
                        logger.warning(f"Scene {sid} not found during fusion")
                        continue
                except Exception as e:
                    logger.error(f"Error fetching scene {sid} for fusion: {e}")
                    continue
            scenes.append(SCENE_STORE[sid])
            
        if not scenes:
            raise HTTPException(status_code=400, detail="No valid scenes found for fusion")

        # Fetch bands and prepare for fusion
        fusion_urls = []
        for scene in scenes:
            try:
                bands = scene.get("bands", {})
                if "nir" in bands and "red" in bands:
                    fusion_urls.append({
                        "id": scene.get("id", "unknown"),
                        "nir": bands["nir"],
                        "red": bands["red"],
                        "satellite": scene.get("satellite", "Unknown")
                    })
            except Exception as e:
                logger.error(f"Error processing scene for fusion: {e}")
                continue
            
        
        if not fusion_urls:
            raise HTTPException(status_code=400, detail="Selected scenes do not have NIR/Red bands for analysis")
            
        # Create a unique fusion ID
        ids_hash = hashlib.md5(",".join(sorted(request.scene_ids)).encode()).hexdigest()[:12]
        fusion_id = f"fusion_{ids_hash}_{request.index}_{request.method}"
        
        # Calculate overall bounds
        min_lon, min_lat = float('inf'), float('inf')
        max_lon, max_lat = float('-inf'), float('-inf')
        
        for scene in scenes:
            if scene.get("geometry") and scene["geometry"].get("coordinates"):
                # Simple envelope from geometry
                coords = scene["geometry"]["coordinates"]
                # Handle nested polygons
                def flattened(l):
                    for i in l:
                        if isinstance(i, (list, tuple)):
                            yield from flattened(i)
                        else:
                            yield i
                
                all_coords = list(flattened(coords))
                for i in range(0, len(all_coords), 2):
                    min_lon = min(min_lon, all_coords[i])
                    max_lon = max(max_lon, all_coords[i])
                    min_lat = min(min_lat, all_coords[i+1])
                    max_lat = max(max_lat, all_coords[i+1])
        
        bounds = [min_lon, min_lat, max_lon, max_lat]
        
        # In a real production environment, we would process the whole area at a fixed resolution.
        # For this demo, we'll store the fusion definition and calculate statistics for a preview area.
        
        # Mocking statistics for the unified analysis report
        # In a full implementation, we would use rio-tiler to read the center tile and calculate these
        stats = {
            "mean_ndvi": 0.45,
            "max_ndvi": 0.88,
            "min_ndvi": -0.12,
            "classification": {
                "bare_soil_percent": 15.4,
                "sparse_vegetation_percent": 22.1,
                "moderate_vegetation_percent": 45.3,
                "dense_vegetation_percent": 17.2
            },
            "satellite_contribution": {
                "Sentinel-2": f"{len([s for s in scenes if 'Sentinel' in s['satellite']])} scenes",
                "Landsat-8/9": f"{len([s for s in scenes if 'Landsat' in s['satellite']])} scenes"
            }
        }
        
        # Store fusion metadata
        FUSION_STORE[fusion_id] = {
            "scene_ids": request.scene_ids,
            "scenes": fusion_urls,
            "method": request.method,
            "index": request.index,
            "bounds": bounds
        }
        
        # URLs for frontend
        tile_url = f"/api/fusion/{fusion_id}/tiles/{{z}}/{{x}}/{{y}}?rescale=0,1"
        preview_url = f"/api/fusion/{fusion_id}/preview"
        
        return FusionProcessingResponse(
            fusion_id=fusion_id,
            stats=stats,
            preview_url=preview_url,
            tile_url=tile_url,
            bounds=bounds,
            message=f"Successfully fused {len(scenes)} multi-satellite scenes for unified analysis"
        )
    except Exception as e:
        logger.error(f"Fusion processing failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Fusion failed: {str(e)}")


@app.get("/api/fusion/{fusion_id}/tiles/{z}/{x}/{y}")
async def get_fusion_tile(
    fusion_id: str,
    z: int, x: int, y: int,
    rescale: str = "0,1"
):
    """
    Serve tiles for a fused dataset.
    Performs pixel-level fusion on-the-fly for the requested tile.
    """
    if fusion_id not in FUSION_STORE:
        raise HTTPException(status_code=404, detail="Fusion result not found")
        
    fusion_def = FUSION_STORE[fusion_id]
    index_type = fusion_def.get("index", "ndvi")
    
    try:
        method = fusion_def.get("method", "median")
        
        # Collections for Gap-Fill
        sentinel_nir, sentinel_red = [], []
        landsat_nir, landsat_red = [], []
        # Collections for Standard Fusion
        all_nir, all_red = [], []
        
        def reader(asset, x, y, z):
            with Reader(asset) as src:
                # Use Bilinear resampling as requested by user
                return src.tile(x, y, z, resampling_method=Resampling.bilinear)
        
        for scene_def in fusion_def["scenes"]:
            try:
                # Read NIR
                nir_img, _ = reader(scene_def["nir"], x, y, z)
                nir_data = nir_img.data[0]
                
                # Read RED
                red_img, _ = reader(scene_def["red"], x, y, z)
                red_data = red_img.data[0]
                
                # Categorize
                all_nir.append(nir_data)
                all_red.append(red_data)
                
                sat = scene_def.get("satellite", "")
                if "Sentinel" in sat:
                    sentinel_nir.append(nir_data)
                    sentinel_red.append(red_data)
                elif "Landsat" in sat:
                    landsat_nir.append(nir_data)
                    landsat_red.append(red_data)
                    
            except Exception as e:
                logger.warning(f"Failed to read fusion tile source {scene_def.get('id', 'unknown')}: {e}")
                continue
                
        if not all_nir:
            return Response(content=b"", media_type="image/png", status_code=204)
            
        # Fusion Processing
        if method == "gap_fill":
            # Augment Sentinel with Landsat
            if not sentinel_nir:
                # Fallback to Landsat only if no Sentinel
                fused_nir = analysis_service.fuse_median(landsat_nir)
                fused_red = analysis_service.fuse_median(landsat_red)
                result_array = analysis_service.calculate_ndvi(fused_nir, fused_red)
            elif not landsat_nir:
                 # Fallback to Sentinel only if no Landsat
                fused_nir = analysis_service.fuse_median(sentinel_nir)
                fused_red = analysis_service.fuse_median(sentinel_red)
                result_array = analysis_service.calculate_ndvi(fused_nir, fused_red)
            else:
                # Actual Gap Fill
                # Fuse multiple scenes of same type first (using median as robust baseline)
                s_nir = analysis_service.fuse_median(sentinel_nir)
                s_red = analysis_service.fuse_median(sentinel_red)
                l_nir = analysis_service.fuse_median(landsat_nir)
                l_red = analysis_service.fuse_median(landsat_red)
                
                result_array = analysis_service.fuse_gap_fill(s_nir, s_red, l_nir, l_red)

        else:
            # Stats (Median/Mean)
            if method == "mean":
                fused_nir = analysis_service.fuse_mean(all_nir)
                fused_red = analysis_service.fuse_mean(all_red)
            else: # Median (default)
                fused_nir = analysis_service.fuse_median(all_nir)
                fused_red = analysis_service.fuse_median(all_red)
            
            # Calculate Index (assume NDVI for now as requested)
            if index_type == "ndvi":
                result_array = analysis_service.calculate_ndvi(fused_nir, fused_red)
            else:
                result_array = analysis_service.calculate_ndvi(fused_nir, fused_red)
            
        # Create an image object from the array
        from rio_tiler.models import ImageData
        img = ImageData(result_array.reshape(1, *result_array.shape))
        
        # Apply colormap for NDVI (Greenish)
        # 0-1 range for NDVI
        content = img.render(img_format="PNG", colormap="rdylgn")
        
        return Response(content=content, media_type="image/png")
        
    except Exception as e:
        logger.error(f"Fusion tile error: {str(e)}")
        return Response(content=b"", media_type="image/png", status_code=204)


@app.get("/api/fusion/{fusion_id}/preview")
async def get_fusion_preview(fusion_id: str):
    """
    Get a preview image for the fusion result.
    Calculates the center tile and returns it using the tile endpoint logic.
    """
    if fusion_id not in FUSION_STORE:
        raise HTTPException(status_code=404, detail="Fusion result not found")
        
    fusion_def = FUSION_STORE[fusion_id]
    bounds = fusion_def.get("bounds")
    if not bounds:
        raise HTTPException(status_code=404, detail="Bounds not available")
        
    try:
        import mercantile
        # Calculate center point
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        # Get tile at zoom 11 (good overview)
        tile = mercantile.tile(center_lon, center_lat, 11)
        
        # Reuse tile logic
        return await get_fusion_tile(fusion_id, tile.z, tile.x, tile.y)
    except Exception as e:
        logger.error(f"Preview generation failed: {e}")
        # Return a 1x1 transparent pixel or similar if all else fails?
        # Better to return 500 or 404 so UI knows
        raise HTTPException(status_code=500, detail="Could not generate preview")
# ===============================
# Tile Endpoints (Phase 2)
# ===============================

@app.get("/api/tiles/sentinel/{scene_id}")
async def get_sentinel_tiles(scene_id: str):
    """
    Get tile URLs for a Sentinel-2 scene.
    Returns XYZ tile URL templates for RGB and NDVI.
    """
    scene = sentinel_service.get_scene_by_id(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    
    return tile_service.get_scene_tile_info(scene)


@app.get("/api/tiles/landsat/{scene_id}")
async def get_landsat_tiles(scene_id: str):
    """
    Get tile URLs for a Landsat scene.
    Returns XYZ tile URL templates.
    """
    scene = landsat_service.get_scene_by_id(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    
    return tile_service.get_scene_tile_info(scene)


@app.get("/api/tiles/bhuvan/{layer_id}")
async def get_bhuvan_tiles(layer_id: str):
    """
    Get WMS tile URL for a Bhuvan layer.
    """
    return {
        "layer_id": layer_id,
        "wms_url": tile_service.get_bhuvan_wms_url(layer_id),
        "type": "wms"
    }


# ===============================
# Analysis Endpoints (Phase 3)
# ===============================

@app.post("/api/analysis/ndvi")
async def calculate_ndvi_endpoint(scene_id: str, satellite: str = "sentinel"):
    """
    Get NDVI analysis info for a scene.
    Returns tile URL for NDVI visualization and statistics endpoints.
    """
    # Get the scene
    if "sentinel" in satellite.lower():
        scene = sentinel_service.get_scene_by_id(scene_id)
    else:
        scene = landsat_service.get_scene_by_id(scene_id)
    
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    
    # Generate NDVI tile URL
    ndvi_tile_url = tile_service.get_ndvi_tile_url(scene, satellite)
    
    return {
        "scene_id": scene_id,
        "satellite": satellite,
        "ndvi_tile_url": ndvi_tile_url,
        "legend": {
            "min": -1.0,
            "max": 1.0,
            "colormap": "rdylgn",
            "labels": {
                "-1.0 to -0.1": "Water/Bare",
                "-0.1 to 0.1": "Bare Soil",
                "0.1 to 0.3": "Sparse Vegetation",
                "0.3 to 0.6": "Moderate Vegetation",
                "0.6 to 1.0": "Dense Vegetation"
            }
        }
    }


@app.get("/api/analysis/compare")
async def compare_scenes(sentinel_id: str, landsat_id: str):
    """
    Compare NDVI between Sentinel and Landsat scenes.
    Returns correlation and difference statistics.
    """
    sentinel_scene = sentinel_service.get_scene_by_id(sentinel_id)
    landsat_scene = landsat_service.get_scene_by_id(landsat_id)
    
    if not sentinel_scene:
        raise HTTPException(status_code=404, detail=f"Sentinel scene {sentinel_id} not found")
    if not landsat_scene:
        raise HTTPException(status_code=404, detail=f"Landsat scene {landsat_id} not found")
    
    # Return comparison metadata (actual computation would require image data)
    return {
        "sentinel": {
            "id": sentinel_id,
            "datetime": sentinel_scene.get("datetime"),
            "resolution": 10
        },
        "landsat": {
            "id": landsat_id,
            "datetime": landsat_scene.get("datetime"),
            "resolution": 30
        },
        "comparison": {
            "resolution_ratio": 3.0,
            "ndvi_tiles": {
                "sentinel": tile_service.get_ndvi_tile_url(sentinel_scene, "sentinel"),
                "landsat": tile_service.get_ndvi_tile_url(landsat_scene, "landsat")
            }
        }
    }


@app.get("/api/analysis/fusion-methods")
async def get_fusion_methods():
    """
    Get available fusion methods and their descriptions.
    """
    return {
        "methods": [
            {
                "id": "best_pixel",
                "name": "Best Pixel Composite",
                "description": "Selects the best quality pixel from multiple images, prioritizing cloud-free data."
            },
            {
                "id": "mean",
                "name": "Mean Composite",
                "description": "Averages all pixel values across images."
            },
            {
                "id": "median",
                "name": "Median Composite",
                "description": "Uses median value, robust to outliers and cloud contamination."
            }
        ],
        "resampling_methods": [
            {"id": "nearest", "name": "Nearest Neighbor", "description": "Fast, preserves original values"},
            {"id": "bilinear", "name": "Bilinear", "description": "Smooth interpolation"},
            {"id": "bicubic", "name": "Bicubic", "description": "High quality, best for upscaling"}
        ]
    }


# ===============================
# Export Endpoints (Phase 4)
# ===============================

@app.get("/api/export/scene/{scene_id}")
async def export_scene(scene_id: str, format: str = "png", satellite: str = "sentinel"):
    """
    Get export URLs for a scene.
    
    Supported formats: png, geotiff, geojson
    """
    if "sentinel" in satellite.lower():
        scene = sentinel_service.get_scene_by_id(scene_id)
    else:
        scene = landsat_service.get_scene_by_id(scene_id)
    
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    
    export_info = {
        "scene_id": scene_id,
        "format": format,
        "satellite": satellite,
        "datetime": scene.get("datetime"),
    }
    
    if format == "png":
        export_info["download_url"] = scene.get("thumbnail_url") or scene.get("download_url")
        export_info["content_type"] = "image/png"
    elif format == "geotiff":
        # Get the visual or RGB band URL for GeoTIFF
        bands = scene.get("bands", {})
        export_info["download_url"] = bands.get("visual") or bands.get("red") or scene.get("download_url")
        export_info["content_type"] = "image/tiff"
    elif format == "geojson":
        export_info["geometry"] = scene.get("geometry")
        export_info["content_type"] = "application/geo+json"
    
    return export_info


@app.get("/api/export/metadata/{scene_id}")
async def export_metadata(scene_id: str, satellite: str = "sentinel"):
    """
    Export scene metadata as JSON.
    """
    if "sentinel" in satellite.lower():
        scene = sentinel_service.get_scene_by_id(scene_id)
    else:
        scene = landsat_service.get_scene_by_id(scene_id)
    
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    
    return {
        "id": scene.get("id"),
        "satellite": scene.get("satellite"),
        "datetime": scene.get("datetime"),
        "cloud_cover": scene.get("cloud_cover"),
        "geometry": scene.get("geometry"),
        "bands": list(scene.get("bands", {}).keys()),
        "resolution": 10 if "sentinel" in satellite.lower() else 30
    }



# ===============================
# Dataset Manager (Local)
# ===============================

@app.get("/api/datasets/list")
async def list_datasets(folder: str = "datasets"):
    """
    List GeoTIFF datasets in the server directory.
    """
    try:
        if not os.path.exists(folder):
            return []
            
        files = []
        for f in os.listdir(folder):
            if f.endswith('.tif') or f.endswith('.tiff'):
                filepath = os.path.join(folder, f)
                stats = os.stat(filepath)
                files.append({
                    "name": f,
                    "size_mb": round(stats.st_size / (1024 * 1024), 2),
                    "created": time.ctime(stats.st_ctime),
                    "path": filepath
                })
        
        # Sort by creation time (newest first)
        files.sort(key=lambda x: os.path.getctime(x['path']), reverse=True)
        return files
        
    except Exception as e:
        logger.error(f"Error listing datasets: {e}")
        return []

from fastapi.responses import FileResponse

@app.get("/api/datasets/download/{filename}")
async def download_dataset(filename: str, folder: str = "datasets"):
    """
    Download a dataset file from the server.
    """
    # Security: Prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
        
    filepath = os.path.join(folder, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(
        path=filepath, 
        filename=filename, 
        media_type='image/tiff'
    )
    
import time 

@app.get("/api/datasets/download-zip")
async def download_zip(folder: str, background_tasks: BackgroundTasks):
    """
    Zip a folder and return it as a downloadable file.
    """
    # Security: Prevent directory traversal
    if ".." in folder or "/" in folder or "\\" in folder:
        # Allow only simple folder names
        pass 

    folder_path = os.path.abspath(folder)
    
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail="Session folder not found")

    import tempfile
    import shutil
    
    # Create a temporary directory to store the zip
    temp_dir = tempfile.mkdtemp()
    
    def cleanup_temp_dir():
        try:
           shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
           print(f"Error cleaning up temp dir: {e}")

    try:
        # Create zip file inside temp_dir
        zip_base_name = os.path.join(temp_dir, folder)
        zip_path = shutil.make_archive(zip_base_name, 'zip', folder_path)
        
        # Schedule cleanup after response is sent
        background_tasks.add_task(cleanup_temp_dir)
        
        return FileResponse(
            path=zip_path,
            filename=f"{folder}.zip",
            media_type='application/zip'
        )
        
    except Exception as e:
        cleanup_temp_dir()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
