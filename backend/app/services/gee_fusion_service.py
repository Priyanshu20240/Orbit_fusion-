"""
GEE Fusion Service (M5).

Post-M5 this service is a thin wrapper around the M4 fusion engine (services.fusion):
``build_fusion_map`` composes the masked/scaled composite + strategy + getMapId,
``generate_timelapse`` routes each frame through the shared registry path so
LST-°C / Landsat-offset / true-water-NDWI fixes hold on the GIF path too
(design C.2.7), and ``create_geo_window`` is a cheap AOI-bounds utility.

The pre-M5 numpy/PNG/COG/titiler path is gone.
"""
import ee
from typing import Dict, List, Tuple, Optional
import logging
import math

logger = logging.getLogger(__name__)

# Resolution constants (used by create_geo_window only)
SENTINEL_RESOLUTION = 10   # meters per pixel
LANDSAT_RESOLUTION = 30    # meters per pixel

# Default window size (pixels) for create_geo_window
DEFAULT_WINDOW_SIZE = 256


def _visualize_frame(img, platform, visualization):
    """Render one timelapse frame via the shared registry path (design C.2.7).

    Uses the same scaling + masking + STRATEGY_REGISTRY as the tile path, so the
    LST-°C / Landsat-offset / true-water-NDWI fixes hold on the GIF path too.
    """
    from app.services.fusion import get_strategy
    from app.services.fusion.mapid import visspec_to_vis
    from app.services.fusion.masking import mask_landsat, mask_s2
    from app.services.fusion.scaling import to_sensor_images

    if platform == 'landsat':
        images = to_sensor_images(landsat=mask_landsat(img))
    else:
        images = to_sensor_images(sentinel=mask_s2(img))
    vis_image, vis = get_strategy(visualization).build(images)
    return vis_image.visualize(**visspec_to_vis(vis))


class GEEFusionService:
    """
    Google Earth Engine-based fusion service implementing geographic windowing.

    Uses Sentinel-2 as the master reference (10m resolution) and upsamples
    Landsat (30m) to match, ensuring proper geographic alignment.
    
    Performance optimizations:
    - LRU caching for fusion results
    - Parallel image downloads
    - Reduced GEE round-trips
    """
    
    def __init__(self):
        # Side-effect-free by design: NO network, NO GEE auth here. Earth Engine
        # is initialized exactly once at app startup
        # (lifespan -> services.gee_auth.init_earth_engine). Importing this module
        # (including the module-level singleton below) must never touch the network.
        pass

    def create_geo_window(
        self,
        center_lon: float,
        center_lat: float,
        window_size: int = DEFAULT_WINDOW_SIZE
    ) -> Tuple[float, float, float, float]:
        """
        Create geographic bounds for a window centered at given coordinates.
        
        Uses Sentinel resolution (10m) as the reference.
        
        Args:
            center_lon: Center longitude
            center_lat: Center latitude
            window_size: Window size in pixels (default 256)
            
        Returns:
            (west, south, east, north) bounds
        """
        # Calculate extent in meters
        extent_meters = window_size * SENTINEL_RESOLUTION  # 256 * 10 = 2560m
        
        # Approximate meters to degrees (at given latitude)
        # 1 degree latitude ≈ 111,320 meters
        # 1 degree longitude ≈ 111,320 * cos(latitude) meters
        import math
        meters_per_deg_lat = 111320
        meters_per_deg_lon = 111320 * math.cos(math.radians(center_lat))
        
        half_extent_lat = (extent_meters / 2) / meters_per_deg_lat
        half_extent_lon = (extent_meters / 2) / meters_per_deg_lon
        
        west = center_lon - half_extent_lon
        east = center_lon + half_extent_lon
        south = center_lat - half_extent_lat
        north = center_lat + half_extent_lat
        
        return (west, south, east, north)


    def build_fusion_map(self, req) -> Dict:
        """Compose the M4 fusion blocks into a getMapId tile-layer response.

        `req` is a models.schemas.FusionRequest. Returns a FusionMapResponse-
        shaped dict. Raises NoImageryError when the request matches zero scenes
        (→ HTTP 404 via the M7 handler); strategy errors (e.g. LST on
        Sentinel-only) propagate as ValueError (→ HTTP 400).

        Side effect: caches the (image, vis) pair and the minted mapid under
        ``fusion_id`` so ``/api/fusion/{fusion_id}/refresh-mapid`` can re-mint
        without recomputing the composite.
        """
        import hashlib
        from datetime import datetime, timedelta, timezone

        from app.config import get_settings
        from app.core import mapid_cache
        from app.services.fusion import get_strategy
        from app.services.fusion.composite import (
            composite, landsat_collection, s2_collection, scene_count,
        )
        from app.services.fusion.mapid import mint_mapid
        from app.services.fusion.registry import NoImageryError
        from app.services.fusion.scaling import to_sensor_images

        cfg = get_settings()
        west, south, east, north = req.bounds
        start, end = str(req.start_date), str(req.end_date)
        max_scenes = cfg.max_scenes_per_composite

        if req.geojson:
            geom = ee.Geometry(req.geojson.get('geometry', req.geojson))
        else:
            geom = ee.Geometry.Rectangle([west, south, east, north])

        sentinel_img = landsat_img = None
        n_s2 = n_l = 0
        if 'sentinel' in req.platforms:
            s2c = s2_collection(geom, start, end, req.cloud_cover, max_scenes)
            n_s2 = scene_count(s2c)
            if n_s2:
                sentinel_img = composite(s2c)
        if 'landsat' in req.platforms:
            lc = landsat_collection(geom, start, end, req.cloud_cover, max_scenes)
            n_l = scene_count(lc)
            if n_l:
                landsat_img = composite(lc)

        if n_s2 == 0 and n_l == 0:
            raise NoImageryError(
                f"No imagery for {req.visualization} over {req.bounds} "
                f"({start}..{end}, cloud<{req.cloud_cover}%)"
            )

        images = to_sensor_images(sentinel=sentinel_img, landsat=landsat_img)
        vis_image, vis = get_strategy(req.visualization).build(images)
        vis_image = vis_image.clip(geom)
        minted = mint_mapid(vis_image, vis, ttl=cfg.mapid_ttl_seconds)

        fusion_id = hashlib.md5(
            f"{req.bounds}|{start}|{end}|{req.visualization}|{sorted(req.platforms)}".encode()
        ).hexdigest()[:12]
        expires_at_epoch = mapid_cache.store_mapid(
            fusion_id,
            minted['tile_url_template'],
            minted.get('mapid'),
            ttl_seconds=cfg.mapid_ttl_seconds,
        )
        mapid_cache.store_fusion_image(fusion_id, vis_image, vis)
        expires_at = (
            datetime.fromtimestamp(expires_at_epoch, tz=timezone.utc).isoformat()
        )

        return {
            'fusion_id': fusion_id,
            'tile_url_template': minted['tile_url_template'],
            'bounds': [[south, west], [north, east]],
            'visualization': req.visualization,
            'scene_counts': {'sentinel': n_s2, 'landsat': n_l},
            'expires_at': expires_at,
            'max_native_zoom': 14,
            'mapid': minted.get('mapid'),
        }

    def refresh_fusion_mapid(self, fusion_id: str) -> Dict:
        """Re-mint a mapid for an already-cached fusion image (no recompute).

        Returns a dict shaped like build_fusion_map's response but with the
        fresh token. Raises ServiceError(no_imagery) when the id isn't in
        the image cache.
        """
        from datetime import datetime, timezone

        from app.config import get_settings
        from app.core import mapid_cache
        from app.core.errors import ServiceError
        from app.services.fusion.mapid import mint_mapid

        cached = mapid_cache.load_fusion_image(fusion_id)
        if cached is None:
            raise ServiceError(
                "no_imagery",
                f"No cached fusion for id {fusion_id!r}",
                extra={"fusion_id": fusion_id},
            )
        vis_image, vis = cached
        cfg = get_settings()
        minted = mint_mapid(vis_image, vis, ttl=cfg.mapid_ttl_seconds)
        expires_at_epoch = mapid_cache.store_mapid(
            fusion_id,
            minted['tile_url_template'],
            minted.get('mapid'),
            ttl_seconds=cfg.mapid_ttl_seconds,
        )
        expires_at = (
            datetime.fromtimestamp(expires_at_epoch, tz=timezone.utc).isoformat()
        )
        return {
            "fusion_id": fusion_id,
            "tile_url_template": minted["tile_url_template"],
            "mapid": minted.get("mapid"),
            "expires_at": expires_at,
            "max_native_zoom": 14,
        }

    def generate_timelapse(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: str,
        end_date: str,
        platform: str = 'sentinel',
        geojson: Dict = None,
        visualization: str = 'true_color'
    ) -> Dict:
        """
        Generate a Timelapse GIF for specific visualization.
        """
        # GEE is initialized once at app startup (lifespan -> init_earth_engine);
        # this service no longer authenticates on its own.
        
        try:
            logger.info(f"Generating Timelapse ({visualization})...")
            
            try:
                if geojson:
                    if 'geometry' in geojson:
                         geom_data = geojson['geometry']
                    else:
                         geom_data = geojson
                    geometry = ee.Geometry(geom_data)
                    logger.info("Using custom polygon for timelapse")
                else:
                    geometry = ee.Geometry.Rectangle(list(bounds))
            except Exception as e:
                logger.error(f"Invalid geometry for timelapse: {e}. Falling back to bounds.")
                geometry = ee.Geometry.Rectangle(list(bounds))
            
            # Render each frame through the SHARED registry path (same scaling,
            # masking and index fixes as the tile path - see design C.2.7; no
            # private ladder, no B10-on-Sentinel, no raw-band Landsat NDVI).
            if platform == 'landsat':
                base = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
                        .merge(ee.ImageCollection('LANDSAT/LC09/C02/T1_L2'))
                        .filterBounds(geometry)
                        .filterDate(start_date, end_date)
                        .filter(ee.Filter.lt('CLOUD_COVER', 30)))
                collection = base.map(lambda img: _visualize_frame(img, 'landsat', visualization))
            else:
                from app.services.fusion.masking import CSPLUS_BAND, CSPLUS_ID
                base = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                        .filterBounds(geometry)
                        .filterDate(start_date, end_date)
                        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
                        .linkCollection(ee.ImageCollection(CSPLUS_ID), [CSPLUS_BAND]))
                collection = base.map(lambda img: _visualize_frame(img, 'sentinel', visualization))
            
            count = collection.size().getInfo()
            if count == 0:
                logger.warning("No images found for timelapse.")
                return {'success': False, 'error': 'No images found for timelapse in this range.'}
            
            logger.info(f"Timelapse frames found: {count}")
            
            # Limit frames to prevent timeouts (max 50)
            # Limit frames to prevent timeouts (max 50)
            if count > 50:
                collection = collection.limit(50)
            
            # Use scale instead of fixed dimensions to preserve aspect ratio and quality
            # Switch back to EPSG:3857 so 'scale' (if used) is in meters, not degrees!
            # Using 'dimensions' as a single integer (e.g., 768) puts a limit on the max dimension 
            # while preserving aspect ratio. usage of `min` in dimensions is safer.
            
            # Use a robust configuration for web display
            video_args = {
                'dimensions': 768, # Max dimension 768px, preserves aspect ratio
                'region': geometry,
                'framesPerSecond': 4,
                'crs': 'EPSG:3857' # Web Mercator (meters)
            }
            
            try:
                thumb_url = collection.getVideoThumbURL(video_args)
                logger.info(f"Timelapse URL: {thumb_url}")
            except Exception as e:
                logger.warning(f"Timelapse generation failed, retrying with lower res. Error: {e}")
                fallback_args = {
                    'dimensions': 400,
                    'region': geometry,
                    'framesPerSecond': 4,
                    'crs': 'EPSG:3857'
                }
                thumb_url = collection.getVideoThumbURL(fallback_args)
            

            
            return {
                'success': True,
                'url': thumb_url,
                'count': count
            }
            
        except Exception as e:
            logger.error(f"Timelapse generation failed: {e}")
            raise e

gee_fusion_service = GEEFusionService()
