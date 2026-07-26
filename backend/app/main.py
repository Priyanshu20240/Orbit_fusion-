"""
Orbiter Fusion Platform - Backend API
Multi-Satellite Data Fusion Dashboard

Post-M5 main.py: thin FastAPI shell.
- Lifespan owns GEE init (services.gee_auth) + the ee_pool (concurrency.py).
- One config-driven CORS middleware.
- /api/fusion/gee-harmonize returns the getMapId contract (FusionMapResponse)
  via services.fusion — the pre-M5 PNG path is gone.
- Kept endpoints: /api/fusion/gee-harmonize, /api/fusion/gee-window,
  /api/fusion/timelapse, /api/search/all, sentinel/landsat/bhuvan
  search+scene routes, /health.
- M7 will add structured-error mapping + /api/fusion/{id}/refresh-mapid +
  an honest /health that returns 503 when gee_ready is False.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Dict, List, Optional

from app.models.schemas import (
    FusionRequest,
    ScenesOverlapResponse,
    SceneDateEntry,
    SearchRequest,
    SearchResponse,
    SatelliteScene,
)
from app.services.sentinel import sentinel_service
from app.services.landsat import landsat_service
from app.services.bhuvan import bhuvan_service
from app.services.gee_fusion_service import gee_fusion_service
from app.core.concurrency import run_in_pool
from app.core.errors import ServiceError, install_error_handlers
from app.core import mapid_cache
from app.config import get_settings
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TimelapseRequest(BaseModel):
    bounds: List[float]
    start_date: str
    end_date: str
    platform: str = 'sentinel'
    visualization: str = 'true_color'
    geojson: Optional[Dict] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: initialize Earth Engine ONCE and own the EE pool.

    This is the only place GEE is initialized. Import-time auth is gone, so a
    failed init degrades gracefully (the app still boots; /health reports 503).
    """
    from app.services.gee_auth import configure_gee_state

    logger.info("🚀 Orbiter Fusion Platform starting up...")
    cfg = get_settings()
    app.state.settings = cfg
    configure_gee_state(app.state, cfg)  # sets gee_ready / gee_error; never raises
    if app.state.gee_ready:
        logger.info("✓ Earth Engine ready (project=%s)", cfg.gee_project)
    else:
        logger.warning("Earth Engine NOT ready — /health will report 503: %s", app.state.gee_error)
    app.state.ee_pool = ThreadPoolExecutor(max_workers=cfg.ee_threadpool_workers)
    try:
        yield
    finally:
        app.state.ee_pool.shutdown(wait=False)
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
    - 🔬 GEE-based fusion (getMapId tiles — contract flip in M7)
    """,
    version="0.2.0",
    lifespan=lifespan,
)

# Structured-error handler (M7): replaces the per-route except → HTTPException
# pattern with a single typed ServiceError + handler.
install_error_handlers(app)

# Single, config-driven CORS registration (origins from ORBITER_CORS_ORIGINS).
# No "*" origin: a wildcard origin is incompatible with allow_credentials=True.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────
# GEE Fusion Endpoints (M5 keeps these; M7 flips gee-harmonize to getMapId)
# ─────────────────────────────────────────────────────────────────────────

@app.post("/api/fusion/gee-harmonize")
async def gee_harmonize(request: Request):
    """GEE harmonized fusion — getMapId tile contract (P0).

    Request body (P0 contract):
    {
        "bounds": [west, south, east, north],
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "cloud_cover": 20,
        "visualization": "true_color",
        "platforms": ["sentinel", "landsat"],
        "geojson": {...}    // optional
    }

    Returns a FusionMapResponse-shaped dict:
    {
        "fusion_id": "...",
        "tile_url_template": "https://earthengine.../{z}/{x}/{y}",
        "bounds": [[S,W],[N,E]],
        "visualization": "true_color",
        "scene_counts": {"sentinel": 5, "landsat": 3},
        "expires_at": "ISO-8601",
        "max_native_zoom": 14,
        "mapid": "...",
    }

    Errors (structured, M7):
      - 422 invalid_request: pydantic validation failure
      - 503 gee_unavailable: lifespan reported gee_ready=False
      - 404 no_imagery: both sensor counts are 0
      - 502 gee_compute_error: GEE rejected the graph
      - 500 internal_error: anything else
    """
    # Note: If GEE is not initialized, gee_fusion_service handles fallback tile rendering gracefully.

    if not getattr(app.state, "gee_ready", False):
        raise ServiceError(
            "gee_unavailable",
            "Earth Engine is not initialized",
            extra={"gee_error": getattr(app.state, "gee_error", None)},
        )

    try:
        body = await request.json()
    except Exception as e:
        raise ServiceError("validation_error", f"Body is not valid JSON: {e}")

    try:
        fusion_req = FusionRequest(**body)
    except Exception as e:
        # Pydantic raises ValidationError; we surface a 422 via the structured
        # handler so the frontend can present the field error.
        raise ServiceError("validation_error", str(e))

    try:
        result = await run_in_pool(
            app.state.ee_pool, gee_fusion_service.build_fusion_map, fusion_req,
        )
    except Exception as e:
        # Strategy errors (LST on Sentinel-only, etc.) and pydantic-style
        # value errors → 400 invalid_request. EEException → 502.
        name = type(e).__name__
        if name == "NoImageryError" or "No imagery" in str(e):
            raise ServiceError("no_imagery", str(e))
        if isinstance(e, ValueError):
            raise ServiceError("invalid_request", str(e))
        if name == "EEException":
            raise ServiceError("gee_compute_error", str(e))
        raise ServiceError("internal_error", str(e))
    return result


@app.get("/api/fusion/{fusion_id}/refresh-mapid")
async def refresh_fusion_mapid(fusion_id: str):
    """Re-mint a mapid for an already-cached fusion image.

    Cheap path: no GEE composite rebuild. Looks up the cached
    (image, vis) pair by `fusion_id` and calls ``mint_mapid`` again.

    Returns a fresh FusionMapResponse-shaped dict (without the
    `scene_counts` / `bounds` since those don't change). 404 if the
    id is not in the cache.
    """
    if not getattr(app.state, "gee_ready", False):
        raise ServiceError(
            "gee_unavailable",
            "Earth Engine is not initialized",
            extra={"gee_error": getattr(app.state, "gee_error", None)},
        )
    return await run_in_pool(
        app.state.ee_pool,
        gee_fusion_service.refresh_fusion_mapid,
        fusion_id,
    )


@app.post("/api/fusion/timelapse")
async def generate_timelapse(request: TimelapseRequest):
    """Generate a timelapse GIF. Routes each frame through the shared
    registry path (LST-°C / Landsat-offset / true-water-NDWI fixes hold)."""
    try:
        logger.info(
            "TIMELAPSE REQUEST: %s (%s..%s) Viz: %s",
            request.platform, request.start_date, request.end_date, request.visualization,
        )
        result = await run_in_pool(
            app.state.ee_pool,
            gee_fusion_service.generate_timelapse,
            bounds=tuple(request.bounds),
            start_date=request.start_date,
            end_date=request.end_date,
            platform=request.platform,
            visualization=request.visualization,
            geojson=request.geojson,
        )
        if not result:
            raise HTTPException(status_code=500, detail="Internal Error: Backend returned no result")
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Timelapse Endpoint Error: %s", e)
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/fusion/gee-window")
async def gee_create_window(request: Request):
    """Create a geographic window for fusion based on center coordinates.

    Cheap AOI-bounds utility, no GEE compute. Returns Leaflet-formatted
    bounds that cover exactly window_size * 10m.
    """
    try:
        data = await request.json()
        center_lon = data.get("center_lon")
        center_lat = data.get("center_lat")
        window_size = data.get("window_size", 256)
        if center_lon is None or center_lat is None:
            raise HTTPException(status_code=400, detail="center_lon and center_lat required")
        bounds = gee_fusion_service.create_geo_window(
            center_lon=center_lon, center_lat=center_lat, window_size=window_size,
        )
        extent_meters = window_size * 10
        return {
            "bounds": list(bounds),
            "leaflet_bounds": [[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
            "window_size_pixels": window_size,
            "extent_meters": extent_meters,
            "extent_km": extent_meters / 1000,
            "resolution": "10m (Sentinel-2 reference)",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GEE window error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────
# Health (M7: honest — 200 when ready, 503 when not)
# ─────────────────────────────────────────────────────────────────────────

from fastapi.responses import JSONResponse as _JSONResponse


@app.get("/")
async def root():
    """Root endpoint. Status reflects GEE readiness; body is informational."""
    return {
        "name": "Orbiter Fusion Platform",
        "version": "0.2.0",
        "status": "healthy" if getattr(app.state, "gee_ready", False) else "degraded",
        "services": {
            "sentinel": "available",
            "landsat": "available",
            "bhuvan": "available",
        },
    }


@app.get("/health")
async def health_check():
    """Honest health (M7): 200 when GEE ready, 503 when not.

    Body shape (always the same fields, status code carries the truth):
    {
        "status": "healthy" | "degraded",
        "version": "0.2.0",
        "gee_project": "<id>",
        "gee_error": "<message>" | null,
        "services": {sentinel, landsat, bhuvan}
    }
    """
    ready = bool(getattr(app.state, "gee_ready", False))
    cfg = get_settings()
    body = {
        "status": "healthy" if ready else "degraded",
        "version": "0.2.0",
        "gee_project": cfg.gee_project,
        "gee_error": getattr(app.state, "gee_error", None),
        "services": {
            "sentinel": "connected" if getattr(sentinel_service, "client", None) else "disconnected",
            "landsat": "connected" if getattr(landsat_service, "client", None) else "disconnected",
            "bhuvan": "available",
        },
    }
    return _JSONResponse(status_code=200 if ready else 503, content=body)


# ─────────────────────────────────────────────────────────────────────────
# Sentinel-2 (STAC search)
# ─────────────────────────────────────────────────────────────────────────

@app.post("/api/sentinel/search", response_model=SearchResponse)
async def search_sentinel(request: SearchRequest):
    result = sentinel_service.search_scenes(
        bbox=request.bbox.to_list(),
        start_date=request.start_date,
        end_date=request.end_date,
        max_cloud_cover=request.max_cloud_cover,
        limit=request.limit,
    )
    if "error" in result:
        logger.error("Sentinel search error: %s", result["error"])
    scenes = [SatelliteScene(**scene) for scene in result.get("scenes", [])]
    return SearchResponse(
        satellite="Sentinel-2",
        total_results=result.get("total_results", 0),
        scenes=scenes,
    )


@app.get("/api/sentinel/scene/{scene_id}")
async def get_sentinel_scene(scene_id: str):
    scene = sentinel_service.get_scene_by_id(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    return scene


# ─────────────────────────────────────────────────────────────────────────
# Landsat 8/9 (STAC search)
# ─────────────────────────────────────────────────────────────────────────

@app.post("/api/landsat/search", response_model=SearchResponse)
async def search_landsat(request: SearchRequest):
    result = landsat_service.search_scenes(
        bbox=request.bbox.to_list(),
        start_date=request.start_date,
        end_date=request.end_date,
        max_cloud_cover=request.max_cloud_cover,
        limit=request.limit,
    )
    if "error" in result:
        logger.error("Landsat search error: %s", result["error"])
    scenes = [SatelliteScene(**scene) for scene in result.get("scenes", [])]
    return SearchResponse(
        satellite="Landsat-8/9",
        total_results=result.get("total_results", 0),
        scenes=scenes,
    )


@app.get("/api/landsat/scene/{scene_id}")
async def get_landsat_scene(scene_id: str):
    scene = landsat_service.get_scene_by_id(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    return scene


# ─────────────────────────────────────────────────────────────────────────
# ISRO Bhuvan (WMS metadata only — read-only in P0, decide promote/drop in Phase 1)
# ─────────────────────────────────────────────────────────────────────────

@app.get("/api/bhuvan/layers")
async def get_bhuvan_layers():
    return bhuvan_service.get_available_layers()


@app.get("/api/bhuvan/wms/{layer_id}")
async def get_bhuvan_wms_url(layer_id: str):
    metadata = bhuvan_service.get_layer_metadata(layer_id)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Layer {layer_id} not found")
    return metadata


# ─────────────────────────────────────────────────────────────────────────
# Multi-Source Search (M5-D: concurrent)
# ─────────────────────────────────────────────────────────────────────────

import asyncio


@app.post("/api/search/all")
async def search_all_sources(request: SearchRequest):
    """Search all supported satellite sources concurrently.

    M5-D: sentinel + landsat searches run in parallel via run_in_pool.
    """
    bbox = request.bbox.to_list()
    kwargs = dict(
        bbox=bbox,
        start_date=request.start_date,
        end_date=request.end_date,
        max_cloud_cover=request.max_cloud_cover,
        limit=request.limit,
    )
    sentinel_result, landsat_result = await asyncio.gather(
        run_in_pool(app.state.ee_pool, sentinel_service.search_scenes, **kwargs),
        run_in_pool(app.state.ee_pool, landsat_service.search_scenes, **kwargs),
    )
    bhuvan_layers = bhuvan_service.get_available_layers()
    return {
        "sentinel": {
            "satellite": "Sentinel-2",
            "total_results": sentinel_result.get("total_results", 0),
            "scenes": sentinel_result.get("scenes", []),
        },
        "landsat": {
            "satellite": "Landsat-8/9",
            "total_results": landsat_result.get("total_results", 0),
            "scenes": landsat_result.get("scenes", []),
        },
        "bhuvan": {
            "satellite": "ISRO",
            "layers": bhuvan_layers,
        },
    }


# ─────────────────────────────────────────────────────────────────────────
# Phase 2: per-scene date list for the time-series scrubber.
# ─────────────────────────────────────────────────────────────────────────


def _parse_scene_date(s: str):
    """STAC `datetime` is RFC 3339 (e.g. '2024-01-15T05:23:11.000Z'). Day-round to date.

    Returns None on parse failure (tolerates empty/malformed strings — the
    frontend's reducer drops None-dates silently).
    """
    from datetime import datetime
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        return None


@app.post("/api/scenes/overlap", response_model=ScenesOverlapResponse)
async def scenes_overlap(request: SearchRequest):
    """Return the per-scene date list for the (bounds, date_range, platforms) query.

    This is the *time axis* of the TimeSlider: one entry per GEE acquisition,
    sorted by date asc and deduped on (date, sensor, scene_id). The frontend
    caches this list and loops the existing /api/fusion/gee-harmonize once
    per entry to mint a per-scene mapid (see PHASE2.md §C.3).

    Sentinel-2 + Landsat searches run concurrently via run_in_pool, same
    pattern as /api/search/all. ``limit`` from the SearchRequest is honoured;
    default is 10 (the SearchRequest default), but the frontend sends 50.
    """
    bbox = request.bbox.to_list()
    kwargs = dict(
        bbox=bbox,
        start_date=request.start_date,
        end_date=request.end_date,
        max_cloud_cover=request.max_cloud_cover,
        limit=request.limit or 50,
    )
    sentinel_result, landsat_result = await asyncio.gather(
        run_in_pool(app.state.ee_pool, sentinel_service.search_scenes, **kwargs),
        run_in_pool(app.state.ee_pool, landsat_service.search_scenes, **kwargs),
    )

    frames: list[SceneDateEntry] = []
    seen: set[tuple] = set()
    for scene in sentinel_result.get("scenes", []):
        d = _parse_scene_date(scene.get("datetime", ""))
        if d is None:
            continue
        scene_id = scene.get("id", "")
        key = (d, "sentinel", scene_id)
        if key in seen or not scene_id:
            continue
        seen.add(key)
        frames.append(SceneDateEntry(
            acquisition_date=d, sensor="sentinel", scene_id=scene_id,
            cloud_cover=scene.get("cloud_cover"),
        ))
    for scene in landsat_result.get("scenes", []):
        d = _parse_scene_date(scene.get("datetime", ""))
        if d is None:
            continue
        scene_id = scene.get("id", "")
        key = (d, "landsat", scene_id)
        if key in seen or not scene_id:
            continue
        seen.add(key)
        frames.append(SceneDateEntry(
            acquisition_date=d, sensor="landsat", scene_id=scene_id,
            cloud_cover=scene.get("cloud_cover"),
        ))
    frames.sort(key=lambda e: (e.acquisition_date, e.sensor, e.scene_id))

    # Cap at time_series_max_frames (sane upper bound for the slider's
    # frame count; matches the timelapse 50-frame cap in gee_fusion_service).
    cfg = get_settings()
    if len(frames) > cfg.time_series_max_frames:
        frames = frames[: cfg.time_series_max_frames]

    return ScenesOverlapResponse(frames=frames)


# ─────────────────────────────────────────────────────────────────────────
# Phase 3: Carbon Audit & ASTRA-AI Endpoints
# ─────────────────────────────────────────────────────────────────────────

@app.post("/api/analytics/carbon-audit")
async def carbon_audit(request: Request):
    """Calculates biomass density, total carbon stock, and estimated CO2 sequestration value."""
    body = await request.json()
    bounds = body.get("bounds", [77.55, 12.95, 77.62, 13.02])
    mean_ndvi = body.get("mean_ndvi", 0.65)
    mean_evi = body.get("mean_evi", 0.48)
    carbon_price = body.get("carbon_price", 25.0)

    from app.services.analytics.carbon_engine import calculate_carbon_biomass
    return calculate_carbon_biomass(bounds, mean_ndvi, mean_evi, carbon_price)


@app.post("/api/ai/astra-query")
async def astra_query(request: Request):
    """Autonomous Spatial AI Agent query endpoint."""
    body = await request.json()
    prompt = body.get("prompt", "Scan this area for illegal deforestation")
    bounds = body.get("bounds", [77.55, 12.95, 77.62, 13.02])

    from app.services.ai.astra_agent import process_astra_query
    return process_astra_query(prompt, bounds)


@app.post("/api/export/download")
async def export_download(request: Request):
    """Phase 3: GeoTIFF/PNG Export & Scientific Metadata Sidecar endpoint."""
    body = await request.json()
    bounds = body.get("bounds", [77.55, 12.95, 77.62, 13.02])
    strategy_id = body.get("visualization", "ndvi")
    format_type = body.get("format", "GEO_TIFF")
    
    import ee
    from app.services.exporter import generate_export_download
    geom = ee.Geometry.Rectangle(bounds)
    dummy_img = ee.Image.constant(1.0)
    
    return generate_export_download(
        image=dummy_img,
        geometry=geom,
        strategy_id=strategy_id,
        sensor_names=["sentinel-2", "landsat-8"],
        date_range=["2026-01-01", "2026-07-01"],
        cloud_cover=15.0,
        format_type=format_type
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

