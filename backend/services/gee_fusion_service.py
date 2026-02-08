"""
GEE Fusion Service - Geographic Windowing for Sentinel-Landsat Fusion

This service implements the "Master-Slave" approach for proper multi-resolution fusion:
- Sentinel-2 (10m) is the MASTER (defines the reference resolution)
- Landsat-8/9 (30m) is the SLAVE (upsampled to match Sentinel)

The 1:3 Resolution Ratio:
- 1 Landsat pixel (30m) = 3x3 Sentinel pixels (10m)
- A 256x256 Sentinel window covers 2560m
- The same geographic area has only ~85x85 Landsat pixels
- On-the-fly resampling aligns both to 256x256

Fusion Output: 23 channels (12 Sentinel + 11 Landsat bands)
"""

import ee
import numpy as np
from PIL import Image
from scipy import ndimage
from typing import Dict, List, Tuple, Optional
import logging
import hashlib
import io
import os
from datetime import date
from pathlib import Path
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logger = logging.getLogger(__name__)

# Resolution constants
SENTINEL_RESOLUTION = 10   # meters per pixel
LANDSAT_RESOLUTION = 30    # meters per pixel
RESOLUTION_RATIO = LANDSAT_RESOLUTION // SENTINEL_RESOLUTION  # 3:1

# Default window size (pixels)
DEFAULT_WINDOW_SIZE = 256

# Band configurations
SENTINEL_BANDS = {
    'B2': 'blue',
    'B3': 'green', 
    'B4': 'red',
    'B5': 'red_edge_1',
    'B6': 'red_edge_2',
    'B7': 'red_edge_3',
    'B8': 'nir',
    'B8A': 'nir_narrow',
    'B11': 'swir16',
    'B12': 'swir22',
    'SCL': 'scene_class',
    'QA60': 'qa'
}

LANDSAT_BANDS = {
    'SR_B2': 'blue',
    'SR_B3': 'green',
    'SR_B4': 'red',
    'SR_B5': 'nir',
    'SR_B6': 'swir16',
    'SR_B7': 'swir22',
    'ST_B10': 'thermal',
    'QA_PIXEL': 'qa_pixel',
    'QA_RADSAT': 'qa_radsat'
}


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
    
    def __init__(self, output_dir: str = None):
        self.initialized = False
        self.output_dir = Path(output_dir) if output_dir else Path("./static/fusion")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fused_results: Dict[str, dict] = {}
        self._fusion_cache: Dict[str, dict] = {}  # Cache for fusion results
        self._cache_ttl = 3600  # 1 hour TTL
        self._executor = ThreadPoolExecutor(max_workers=4)  # For parallel downloads
        
        # Auto-initialize on creation
        self._try_auto_init()
    
    def _try_auto_init(self):
        """Try to auto-initialize GEE on startup."""
        try:
            # Use project ID for authentication
            ee.Initialize(
                project='compact-arc-482620-r8',
                opt_url='https://earthengine-highvolume.googleapis.com'
            )
            self.initialized = True
            logger.info("✓ GEE auto-initialized with project compact-arc-482620-r8")
        except Exception as e:
            logger.warning(f"GEE auto-init failed (will retry on demand): {e}")
        
    def initialize_gee(self, project_id: str = None) -> bool:
        """
        Initialize Google Earth Engine.
        
        Args:
            project_id: GEE project ID (required for newer auth methods)
            
        Returns:
            True if initialization successful
        """
        if self.initialized:
            return True
            
        try:
            # Try different initialization methods
            if project_id:
                ee.Initialize(project=project_id)
            else:
                # Try high-volume endpoint first
                try:
                    ee.Initialize(opt_url='https://earthengine-highvolume.googleapis.com')
                except:
                    # Fall back to default
                    ee.Initialize()
            
            self.initialized = True
            logger.info("✓ Google Earth Engine initialized successfully")
            return True
            
        except ee.EEException as e:
            error_msg = str(e)
            logger.error(f"GEE initialization failed: {error_msg}")
            
            if "credentials" in error_msg.lower() or "authenticate" in error_msg.lower():
                logger.info("Run 'earthengine authenticate' to set up credentials")
            elif "project" in error_msg.lower():
                logger.info("You may need to specify a GEE project ID")
                
            return False
        except Exception as e:
            logger.error(f"GEE initialization error: {e}")
            return False
    
    def get_sentinel_image(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: str,
        end_date: str,
        cloud_cover: float = 20.0,
        composite_method: str = 'median',
        geometry: ee.Geometry = None
    ) -> Optional[ee.Image]:
        """
        Get Sentinel-2 L2A image from GEE for the specified region.
        """
        if not self.initialized:
            logger.error("GEE not initialized")
            return None
            
        try:
            # Create geometry from bounds if not provided
            if geometry is None:
                geometry = ee.Geometry.Rectangle(list(bounds))
            
            # Query Sentinel-2 L2A collection
            collection = (
                ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filterBounds(geometry)
                .filterDate(start_date, end_date)
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_cover))
                .sort('CLOUDY_PIXEL_PERCENTAGE')
                # .limit(25) # REMOVED: User requested full processing
            )
            
            # Check if collection has images (single getInfo call)
            # count = collection.size().getInfo() # Optimization: Skip count for speed if unsure
            # logger.info(f"Found {count} Sentinel-2 scenes")
            
            # Compositing Method
            if composite_method == 'mean':
                image = collection.mean().clip(geometry)
            elif composite_method == 'mosaic':
                # Quality Mosaic using NDVI
                def addNDVI(img):
                        return img.addBands(img.normalizedDifference(['B8', 'B4']).rename('NDVI'))
                
                collection = collection.map(addNDVI)
                image = collection.qualityMosaic('NDVI').clip(geometry)
            else:
                # Default: Median
                image = collection.median().clip(geometry)
            
            # Use predefined bands
            bands = ['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12']
            
            return image.select(bands)
            
        except Exception as e:
            logger.error(f"Error fetching Sentinel-2: {e}")
            return None
    
    def get_landsat_image(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: str,
        end_date: str,
        cloud_cover: float = 20.0,
        composite_method: str = 'median',
        geometry: ee.Geometry = None
    ) -> Optional[ee.Image]:
        """
        Get Landsat 8/9 image from GEE for the specified region.
        """
        if not self.initialized:
            logger.error("GEE not initialized")
            return None
            
        try:
            if geometry is None:
                geometry = ee.Geometry.Rectangle(list(bounds))
            
            # Query Landsat 8 & 9 Collection 2 Level 2
            l8 = (
                ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
                .filterBounds(geometry)
                .filterDate(start_date, end_date)
                .filter(ee.Filter.lt('CLOUD_COVER', cloud_cover))
            )
            
            l9 = (
                ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
                .filterBounds(geometry)
                .filterDate(start_date, end_date)
                .filter(ee.Filter.lt('CLOUD_COVER', cloud_cover))
            )
            
            # Merge collections
            collection = l8.merge(l9).sort('CLOUD_COVER') # .limit(25) removed per user request
            
            # Check if collection has images
            # count = collection.size().getInfo()
            # logger.info(f"Found {count} Landsat scenes")
            
            # Compositing Method
            if composite_method == 'mean':
                image = collection.mean().clip(geometry)
            elif composite_method == 'mosaic':
                # Quality Mosaic (NDVI) requires calculating NDVI first
                def addNDVI(img):
                    return img.addBands(img.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI'))
                
                collection = collection.map(addNDVI)
                image = collection.qualityMosaic('NDVI').clip(geometry)
            else:
                # Default: Median
                image = collection.median().clip(geometry)
            
            # Use predefined bands instead of querying - faster
            bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'ST_B10']
            
            return image.select(bands)
            
        except Exception as e:
            logger.error(f"Error fetching Landsat: {e}")
            return None
    


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
    
    def resample_to_target(
        self,
        source: np.ndarray,
        target_shape: Tuple[int, int],
        method: str = 'bilinear'
    ) -> np.ndarray:
        """
        Resample array to target shape.
        
        Used to upsample Landsat (30m) to Sentinel (10m) resolution.
        Each 30m pixel becomes a 3x3 grid of 10m pixels.
        
        Args:
            source: Source array (C, H, W) or (H, W)
            target_shape: Target (H, W)
            method: 'bilinear' (smooth) or 'nearest' (preserve values)
            
        Returns:
            Resampled array
        """
        if source.shape[-2:] == target_shape:
            return source
        
        order = 1 if method == 'bilinear' else 0
        
        if source.ndim == 3:
            # Multi-band: (C, H, W)
            result = np.zeros((source.shape[0], *target_shape), dtype=source.dtype)
            zoom_h = target_shape[0] / source.shape[1]
            zoom_w = target_shape[1] / source.shape[2]
            
            for c in range(source.shape[0]):
                result[c] = ndimage.zoom(
                    source[c], (zoom_h, zoom_w), 
                    order=order, mode='nearest'
                )
            return result
        else:
            # Single band: (H, W)
            zoom_h = target_shape[0] / source.shape[0]
            zoom_w = target_shape[1] / source.shape[1]
            return ndimage.zoom(source, (zoom_h, zoom_w), order=order, mode='nearest')
    
    def fetch_as_array(
        self,
        image: ee.Image,
        bounds: Tuple[float, float, float, float],
        scale: int,
        target_size: int = DEFAULT_WINDOW_SIZE
    ) -> Optional[np.ndarray]:
        """
        Fetch GEE image as numpy array.
        
        Args:
            image: ee.Image to fetch
            bounds: Geographic bounds
            scale: Resolution in meters
            target_size: Target array size (e.g., 256)
            
        Returns:
            Numpy array (bands, height, width) or None
        """
        try:
            geometry = ee.Geometry.Rectangle(list(bounds))
            
            # Calculate approximate dimensions in pixels at requested scale (Using Python math to avoid extra GEE calls)
            west, south, east, north = bounds
            avg_lat = (south + north) / 2.0
            
            # Approximate degrees to meters conversion
            # 1 deg lat ~= 111km
            # 1 deg lon ~= 111km * cos(lat)
            lat_m_per_deg = 111000
            lon_m_per_deg = 111000 * np.cos(np.radians(avg_lat))
            
            width_m = (east - west) * lon_m_per_deg
            height_m = (north - south) * lat_m_per_deg
            
            w_pixels = width_m / scale
            h_pixels = height_m / scale
            
            # Safe limit for sampleRectangle (approx 512x512 = 262k pixels)
            safe_limit = 512
            
            if w_pixels > safe_limit or h_pixels > safe_limit:
                # Calculate new scale to fit in safe_limit
                scale_w = width_m / safe_limit
                scale_h = height_m / safe_limit
                new_scale = max(scale_w, scale_h, scale)
                # Ensure we don't go below original scale
                scale = max(new_scale, scale)
                logger.warning(f"AOI too large ({int(w_pixels)}x{int(h_pixels)} px). Adjusting scale to {scale:.2f}m")

            # CRITICAL: Reproject to EPSG:3857 (meters) to ensure we sample at correct resolution
            image = image.reproject(crs='EPSG:3857', scale=scale)
            
            band_names = image.bandNames().getInfo()
            
            # Sample the image to get pixel values
            data = image.sampleRectangle(
                region=geometry,
                defaultValue=0
            ).getInfo()
            
            if not data or 'properties' not in data:
                logger.warning("No data returned from GEE")
                return None
            
            # Extract arrays for each band
            arrays = []
            for band in band_names:
                if band in data['properties']:
                    arr = np.array(data['properties'][band])
                    arrays.append(arr)
            
            if not arrays:
                return None
            
            # Stack into (bands, H, W)
            stacked = np.stack(arrays, axis=0)
            
            # Resample to target size if needed
            if stacked.shape[1] != target_size or stacked.shape[2] != target_size:
                stacked = self.resample_to_target(stacked, (target_size, target_size))
            
            return stacked
            
        except Exception as e:
            logger.error(f"Error fetching array: {e}")
            return None
    
    def fuse_sensors(
        self,
        sentinel_array: np.ndarray,
        landsat_array: np.ndarray,
        window_size: int = DEFAULT_WINDOW_SIZE
    ) -> np.ndarray:
        """
        Fuse Sentinel and Landsat arrays into a single tensor.
        
        Both arrays are first aligned to (bands, window_size, window_size).
        Landsat is upsampled from ~85x85 to 256x256.
        
        Args:
            sentinel_array: Sentinel data (S2_bands, H, W) at 10m
            landsat_array: Landsat data (L8_bands, H, W) at 30m
            window_size: Target size (default 256)
            
        Returns:
            Fused array (S2_bands + L8_bands, H, W)
        """
        target_shape = (window_size, window_size)
        
        # Ensure Sentinel is at target resolution
        if sentinel_array.shape[1:] != target_shape:
            sentinel_array = self.resample_to_target(sentinel_array, target_shape)
        
        # Upsample Landsat to match Sentinel
        if landsat_array.shape[1:] != target_shape:
            logger.info(f"Upsampling Landsat from {landsat_array.shape[1:]} to {target_shape}")
            landsat_array = self.resample_to_target(landsat_array, target_shape)
        
        # Concatenate along band axis
        fused = np.concatenate([sentinel_array, landsat_array], axis=0)
        
        logger.info(f"Fused tensor shape: {fused.shape}")
        return fused
    
    def normalize_to_8bit(self, data: np.ndarray, percentile_clip: Tuple[int, int] = (2, 98)) -> np.ndarray:
        """
        Normalize data to 8-bit (0-255) for web display.
        
        Satellite data is typically 16-bit (0-65535) or float.
        We use percentile clipping for better contrast.
        
        Args:
            data: Input array (any dtype)
            percentile_clip: Percentile range for clipping
            
        Returns:
            8-bit uint8 array (0-255)
        """
        # Handle per-channel normalization if 3D
        if data.ndim == 3:
            result = np.zeros_like(data, dtype=np.uint8)
            for i in range(data.shape[0]):
                result[i] = self._normalize_band(data[i], percentile_clip)
            return result
        else:
            return self._normalize_band(data, percentile_clip)
    
    def _normalize_band(self, band: np.ndarray, percentile_clip: Tuple[int, int]) -> np.ndarray:
        """Normalize a single band to 8-bit."""
        # Calculate percentile bounds
        p_low, p_high = np.percentile(band[band > 0], percentile_clip) if np.any(band > 0) else (0, 1)
        
        # Clip and scale
        clipped = np.clip(band, p_low, p_high)
        if p_high > p_low:
            normalized = (clipped - p_low) / (p_high - p_low)
        else:
            normalized = np.zeros_like(clipped)
        
        return (normalized * 255).astype(np.uint8)
    
    def save_for_web(
        self,
        fused_tensor: np.ndarray,
        bounds: Tuple[float, float, float, float],
        visualization: str = 'true_color',
        fusion_id: str = None,
        pre_processed: bool = False
    ) -> Dict:
        """
        Convert fused tensor to web-displayable PNG.
        
        Args:
            pre_processed: If True, assumes input is already RGB (3,H,W) and 0-255 uint8.
        """
        # Generate fusion ID
        if not fusion_id:
            # Include visualization in hash to prevent browser caching checks on different modes
            unique_str = f"{bounds}_{visualization}"
            fusion_id = f"fusion_{hashlib.md5(unique_str.encode()).hexdigest()[:12]}"
        
        if pre_processed:
            # Input is already RGB uint8
            rgb_8bit = fused_tensor
        else:
            # Select bands for visualization
            if visualization == 'true_color':
                # RGB from Sentinel (B4=Red, B3=Green, B2=Blue)
                # Assuming order: B2, B3, B4, ... => indices 2, 1, 0
                rgb_indices = [2, 1, 0]  # Red, Green, Blue
            elif visualization == 'false_color_nir':
                # NIR, Red, Green for vegetation emphasis
                rgb_indices = [6, 2, 1]  # B8 (NIR), B4 (Red), B3 (Green)
            elif visualization == 'false_color_swir':
                # SWIR, NIR, Red for geology/burn areas
                rgb_indices = [8, 6, 2]  # B11, B8, B4
            elif visualization == 'sci':
                # Scientific / Agriculture (SWIR, NIR, Blue)
                # Highlights healthy vegetation in bright green, soils in distinctive colors
                rgb_indices = [9, 7, 0]  # B12, B8A, B2
            else:
                # Default to first 3 bands
                rgb_indices = [0, 1, 2]
            
            # Ensure indices are valid
            max_idx = fused_tensor.shape[0] - 1
            rgb_indices = [min(i, max_idx) for i in rgb_indices]
            
            # Extract RGB bands
            rgb = fused_tensor[rgb_indices, :, :]  # (3, H, W)
            
            # Normalize to 8-bit
            if visualization == 'true_color':
                # Use fixed scaling for True Color (0-3000 mapping to 0-255)
                # This prevents noise amplification in homogeneous areas (e.g., water)
                rgb_8bit = np.clip(rgb / 3000 * 255, 0, 255).astype(np.uint8)
            else:
                # Use percentile clipping for other visualizations (NIR, SWIR)
                rgb_8bit = self.normalize_to_8bit(rgb)
        
        # Transpose for PIL: (3, H, W) -> (H, W, 3)
        img_array = np.transpose(rgb_8bit, (1, 2, 0))
        
        # Create and save PNG
        img = Image.fromarray(img_array, mode='RGB')
        output_path = self.output_dir / f"{fusion_id}.png"
        img.save(output_path)
        
        logger.info(f"Saved fusion image: {output_path}")
        
        # Convert bounds to Leaflet format [[south, west], [north, east]]
        west, south, east, north = bounds
        leaflet_bounds = [[south, west], [north, east]]
        
        # Store result
        self.fused_results[fusion_id] = {
            'tensor': fused_tensor,
            'bounds': bounds,
            'leaflet_bounds': leaflet_bounds,
            'image_path': str(output_path),
            'shape': fused_tensor.shape
        }
        
        return {
            'success': True,
            'fusion_id': fusion_id,
            'imageUrl': f"/static/fusion/{fusion_id}.png",
            'bounds': leaflet_bounds,
            'shape': list(fused_tensor.shape),
            'visualization': visualization
        }
    
    def fuse_collections_server_side(
        self,
        sentinel_image: Optional[ee.Image],
        landsat_image: Optional[ee.Image],
        visualization: str = 'true_color'
    ) -> ee.Image:
        """
        Perform fusion logic server-side using GEE operations.
        
        Args:
            sentinel_image: 10m Sentinel-2 Image (Optional)
            landsat_image: 30m Landsat Image (Optional)
            visualization: Visualization mode
            
        Returns:
            Fused ee.Image meant for display (RGB 8-bit)
        """
        if not sentinel_image and not landsat_image:
             raise ValueError("At least one image collection (Sentinel or Landsat) is required.")

        # --- LANDSAT ONLY MODE ---
        if not sentinel_image and landsat_image:
            l8 = landsat_image.multiply(0.0000275).add(-0.2).clamp(0, 1)

            if visualization == 'true_color':
                 return l8.select(['SR_B4', 'SR_B3', 'SR_B2']).visualize(min=0, max=0.3, gamma=1.4)
            elif visualization == 'ndvi':
                ndvi = l8.normalizedDifference(['SR_B5', 'SR_B4'])
                return ndvi.visualize(min=-0.2, max=0.8, palette=['brown', 'yellow', 'green'])
            elif visualization == 'false_color_swir':
                 return l8.select(['SR_B7', 'SR_B5', 'SR_B4']).visualize(min=0, max=0.3, gamma=1.4)
            elif visualization == 'false_color_nir':
                 return l8.select(['SR_B5', 'SR_B4', 'SR_B3']).visualize(min=0, max=0.4, gamma=1.2)
            elif visualization == 'sci':
                 # Scientific / Agriculture (SWIR2, NIR, Blue)
                 return l8.select(['SR_B7', 'SR_B5', 'SR_B2']).visualize(min=0, max=0.4, gamma=1.2)
            elif visualization == 'ndbi':
                ndbi = l8.normalizedDifference(['SR_B6', 'SR_B5'])
                return ndbi.visualize(min=-0.3, max=0.5, palette=['blue', 'gray', 'white'])
            elif visualization == 'ndwi':
                ndwi = l8.normalizedDifference(['SR_B5', 'SR_B6'])
                return ndwi.visualize(min=-1, max=1, palette=['brown', 'yellow', 'cyan', 'blue'])
            elif visualization == 'lst':
                thermal = l8.select('ST_B10')
                return thermal.visualize(min=273, max=323, palette=['blue', 'cyan', 'green', 'yellow', 'red'])
            
            return l8.select(['SR_B4', 'SR_B3', 'SR_B2']).visualize(min=0, max=0.3)

        # 1. Scale Sentinel (0-10000 -> 0-1)
        # Sentinel is slightly different scale than Landsat
        s2 = sentinel_image.multiply(0.0001)

        if not landsat_image:
            # Sentinel Only Logic
            if visualization == 'true_color':
                return s2.select(['B4', 'B3', 'B2']).visualize(min=0, max=0.3, gamma=1.4)
            elif visualization == 'ndvi':
                # FIX 5: Explicit reprojection removed to prevent timeout on large areas
                ndvi = s2.normalizedDifference(['B8', 'B4']).unmask(0)
                return ndvi.visualize(min=-0.2, max=0.8, palette=['brown', 'yellow', 'green'])
            elif visualization == 'false_color_swir':
                return s2.select(['B12', 'B8', 'B4']).visualize(min=0, max=0.3, gamma=1.4)
            elif visualization == 'false_color_nir':
                return s2.select(['B8', 'B4', 'B3']).visualize(min=0, max=0.4, gamma=1.2)
            elif visualization == 'sci':
                # Scientific / Agriculture (SWIR2, NIR, Blue)
                return s2.select(['B12', 'B8A', 'B2']).visualize(min=0, max=0.4, gamma=1.2)
            elif visualization == 'ndbi':
                ndbi = s2.normalizedDifference(['B11', 'B8'])
                return ndbi.visualize(min=-0.3, max=0.5, palette=['blue', 'gray', 'white'])
            elif visualization == 'ndwi':
                ndwi = s2.normalizedDifference(['B8', 'B11'])
                return ndwi.visualize(min=-1, max=1, palette=['brown', 'yellow', 'cyan', 'blue'])
            elif visualization == 'lst':
                thermal = s2.select('B10')
                return thermal.visualize(min=273, max=323, palette=['blue', 'cyan', 'green', 'yellow', 'red'])
            return s2.visualize(min=0, max=0.3) # Fallback

        # 2. Scale & Reproject Landsat
        # Landsat (30m) needs to match Sentinel (10m)
        s2_proj = sentinel_image.select('B4').projection()
        
        # Landsat Scaling: 0.0000275 + -0.2
        l8 = landsat_image.multiply(0.0000275).add(-0.2).clamp(0, 1)
            # .reproject(crs=s2_proj, scale=10) # REMOVED: Caused "Reprojection output too large" for large AOIs. 
            # Letting GEE handle reprojection lazily is safer for thumbnails.

        # 3. Fusion Logic
        if visualization == 'true_color':
            logger.info("Server-Side Fusion: True Color (HSV Mix)")
            # HSV Fusion Strategy
            # Use L8 for Color (Hue, Saturation) and S2 for Detail (Value/Intensity)
            
            # Create RGB composites
            s2_rgb = s2.select(['B4', 'B3', 'B2'])
            l8_rgb = l8.select(['SR_B4', 'SR_B3', 'SR_B2'])
            
            # Normalize before HSV (Critical for color match)
            s2_rgb = s2_rgb.unitScale(0, 0.3)
            l8_rgb = l8_rgb.unitScale(0, 0.3)
            
            # Convert to HSV
            s2_hsv = s2_rgb.rgbToHsv()
            l8_hsv = l8_rgb.rgbToHsv()
            
            # FUSE: L8 Hue, L8 Saturation, S2 Value
            # hue = l8_hsv.select('hue')
            # sat = l8_hsv.select('saturation')
            # val = s2_hsv.select('value')
            
            # Simpler Fusion: Average
            fused_rgb = s2_rgb.add(l8_rgb).divide(2)
            
            # Return visualized image (0-255 automatically handled by getThumbURL if not explicit, but explicit is safer)
            return fused_rgb.visualize(min=0, max=1, gamma=1.4)

        elif visualization == 'ndvi':
            # NDVI Fusion
            # S2: (B8-B4)/(B8+B4)
            s2_ndvi = s2.normalizedDifference(['B8', 'B4'])
            
            # L8: (B5-B4)/(B5+B4)
            l8_ndvi = l8.normalizedDifference(['SR_B5', 'SR_B4'])
            
            # Average
            fused_ndvi = s2_ndvi.add(l8_ndvi).divide(2)
            
            # FIX 5: Reproject removed to prevent timeout
            fused_ndvi = fused_ndvi.unmask(0)
            
            return fused_ndvi.visualize(min=-0.2, max=0.8, palette=['brown', 'yellow', 'green'])

        elif visualization == 'false_color_nir':
            # NIR False Color (NIR, Red, Green)
            s2_fc = s2.select(['B8', 'B4', 'B3'])
            l8_fc = l8.select(['SR_B5', 'SR_B4', 'SR_B3'])
            
            # Fuse
            fused = s2_fc.add(l8_fc).divide(2)
            return fused.visualize(min=0, max=0.4, gamma=1.2)

        elif visualization == 'false_color_swir':
            # SWIR False Color (SWIR2, NIR, Red)
            s2_swir = s2.select(['B12', 'B8', 'B4'])
            l8_swir = l8.select(['SR_B7', 'SR_B5', 'SR_B4'])
            
            fused = s2_swir.add(l8_swir).divide(2)
            return fused.visualize(min=0, max=0.4, gamma=1.2)

        elif visualization == 'sci':
            # Scientific / Agriculture (SWIR2, NIR, Blue)
            # S2: B12, B8A, B2
            s2_sci = s2.select(['B12', 'B8A', 'B2'])
            # L8: B7, B5, B2
            l8_sci = l8.select(['SR_B7', 'SR_B5', 'SR_B2'])
            
            # Fuse
            fused = s2_sci.add(l8_sci).divide(2)
            return fused.visualize(min=0, max=0.4, gamma=1.2)

        elif visualization == 'true_color_swir':
            # True Color SWIR (Natural SWIR)
            # Mixes True Color (RGB) with SWIR features for enhanced visualization
            
            # 1. True Color Components
            s2_tc = s2.select(['B4', 'B3', 'B2'])
            l8_tc = l8.select(['SR_B4', 'SR_B3', 'SR_B2'])
            fused_tc = s2_tc.add(l8_tc).divide(2)
            
            # 2. SWIR Components (SWIR2, SWIR1, Red)
            s2_swir = s2.select(['B12', 'B11', 'B4'])
            l8_swir = l8.select(['SR_B7', 'SR_B6', 'SR_B4'])
            fused_swir = s2_swir.add(l8_swir).divide(2)
            
            # 3. Blend (50% TC, 50% SWIR)
            fused = fused_tc.add(fused_swir).divide(2)
            
            return fused.visualize(min=0, max=0.35, gamma=1.3)

        elif visualization == 'combined':
             # The complex "Combined" view
             # L8 SWIR + S2 Visible
             return s2.select(['B4','B3','B2']).visualize(min=0, max=0.3) # Placeholder for complex logic

        elif visualization == 'ndbi':
            # Built-up Index Fusion
            s2_ndbi = s2.normalizedDifference(['B11', 'B8'])
            l8_ndbi = l8.normalizedDifference(['SR_B6', 'SR_B5'])
            fused_ndbi = s2_ndbi.add(l8_ndbi).divide(2)
            return fused_ndbi.visualize(min=-0.3, max=0.5, palette=['blue', 'gray', 'white'])

        elif visualization == 'ndwi':
            # Water Index Fusion
            s2_ndwi = s2.normalizedDifference(['B8', 'B11'])
            l8_ndwi = l8.normalizedDifference(['SR_B5', 'SR_B6'])
            fused_ndwi = s2_ndwi.add(l8_ndwi).divide(2)
            return fused_ndwi.visualize(min=-1, max=1, palette=['brown', 'yellow', 'cyan', 'blue'])

        elif visualization == 'lst':
            # Land Surface Temperature Fusion
            s2_thermal = s2.select('B10')
            l8_thermal = l8.select('ST_B10')
            fused_thermal = s2_thermal.add(l8_thermal).divide(2)
            return fused_thermal.visualize(min=273, max=323, palette=['blue', 'cyan', 'green', 'yellow', 'red'])

        # Fallback
        return s2.select(['B4', 'B3', 'B2']).visualize(min=0, max=0.3)
    
    def create_harmonized_fusion(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: str,
        end_date: str,
        cloud_cover: float = 20.0,
        window_size: int = DEFAULT_WINDOW_SIZE,
        visualization: str = 'true_color',
        composite_method: str = 'median',
        platforms: List[str] = ['sentinel', 'landsat'],
        geojson: Dict = None,
        create_dataset: bool = False,
        destination_folder: str = "datasets"
    ) -> Dict:
        """
        Main entry point: Create complete harmonized fusion (Server-Side).
        """
        if not self.initialized:
            if not self.initialize_gee():
                return {'success': False, 'error': 'GEE initialization failed'}
        
        logger.info(f"Fusion Request (Server-Side) - Platforms: {platforms}, Has GeoJSON: {bool(geojson)}")
        
        # Generate cache key (v4 - Force refresh for Visualization fixes)
        cache_key = hashlib.md5(f"{bounds}_{start_date}_{end_date}_{cloud_cover}_{visualization}_{composite_method}_{platforms}_{bool(geojson)}_v4".encode()).hexdigest()
        
        # Check cache
        if cache_key in self._fusion_cache:
            cached = self._fusion_cache[cache_key]
            if time.time() - cached.get('timestamp', 0) < self._cache_ttl:
                logger.info(f"✓ Returning cached fusion result (key: {cache_key[:8]}...)")
                return cached['result']
        
        start_time = time.time()

        # Determine Geometry
        try:
            if geojson:
                if 'geometry' in geojson:
                     geom_data = geojson['geometry']
                else:
                     geom_data = geojson
                geometry = ee.Geometry(geom_data)
            else:
                geometry = ee.Geometry.Rectangle(list(bounds))
        except Exception as e:
            logger.error(f"Invalid geometry: {e}")
            return {'success': False, 'error': f'Invalid geometry: {str(e)}'}

        # Step 1: Fetch Sentinel-2 (Master)
        sentinel_image = None
        if 'sentinel' in platforms:
            sentinel_image = self.get_sentinel_image(bounds, start_date, end_date, cloud_cover, composite_method, geometry=geometry)
            if not sentinel_image:
                 logger.warning("Sentinel-2 image requested but not found.")
        
        # Step 2: Fetch Landsat (Slave)
        landsat_image = None
        if 'landsat' in platforms:
            landsat_image = self.get_landsat_image(bounds, start_date, end_date, cloud_cover, composite_method, geometry=geometry)
            if not landsat_image:
                 logger.warning("Landsat image requested but not found.")
        
        if sentinel_image is None and landsat_image is None:
             return {'success': False, 'error': 'No imagery found for selected platforms'}
             
        # Map frontend "sci" to "false_color_nir" or "combined" if needed, or handle explicitly
        # if visualization == 'sci':
           # visualization = 'false_color_swir' # Map Scientific to SWIR for now as it's high contrast

        # Step 3: Server-Side Fusion
        try:
            t0 = time.time()
            logger.info(f"Generated Fusion Graph for Visualization: {visualization}")
            fused_image = self.fuse_collections_server_side(sentinel_image, landsat_image, visualization)
            logger.info(f"Fusion Graph Built in {time.time() - t0:.2f}s")
            
            # Clip to Geometry
            fused_image = fused_image.clip(geometry)
            


            # Step 4: Handle Dataset Creation (GeoTIFF)
            dataset_result_path = None
            if create_dataset:
                logger.info("Generating GeoTIFF Dataset URL...")
                # Automatic Retry Logic for Large Areas
                scales_to_try = [10, 30, 100, 250, 500]
                
                for scale in scales_to_try:
                    try:
                        logger.info(f"Attempting GeoTIFF export with scale={scale}m...")
                        
                        # Dataset Params
                        dataset_params = {
                            'name': f"Orbiter_Fusion_{visualization}_{start_date}_{end_date}_{scale}m",
                            'scale': scale,
                            'region': geometry,
                            'crs': 'EPSG:4326',
                            'format': 'GEO_TIFF'
                        }
                        
                        # Get signed download URL from GEE
                        dataset_url = fused_image.getDownloadURL(dataset_params)
                        logger.info(f"Got GEE Dataset URL: {dataset_url}")
                        
                        # Server-side Download
                        output_dir = destination_folder if destination_folder else "datasets"
                        os.makedirs(output_dir, exist_ok=True)
                        
                        filename = f"Orbiter_dataset_{visualization}_{start_date}_{end_date}_{scale}m_{int(time.time())}.tif"
                        filepath = os.path.join(output_dir, filename)
                        
                        logger.info(f"Downloading to server: {filepath}...")
                        import urllib.request
                        urllib.request.urlretrieve(dataset_url, filepath)
                        
                        dataset_result_path = os.path.abspath(filepath)
                        logger.info(f"Dataset saved locally to {dataset_result_path}")
                        
                        # If successful, break the loop
                        break
                        
                    except Exception as e:
                         err_msg = str(e)
                         logger.warning(f"Failed to export at {scale}m: {err_msg}")
                         
                         # Check if error is related to size limits
                         if "Total request size" in err_msg and "must be less than" in err_msg:
                             logger.info("Export too large, retrying with lower resolution...")
                             continue # Try next scale
                         else:
                             # If other error, stop trying
                             dataset_result_path = f"Error: {err_msg}"
                             break
                
                if not dataset_result_path:
                    dataset_result_path = "Error: Region too large for all attempts."

            # Step 4: Get Thumbnail URL
            t1 = time.time()
            import urllib.request
            
            # Dimensions Logic
            # Using a single integer '1024' lets GEE handle aspect ratio automatically.
            dims = 501 # Optimized to 501px per user request  

            logger.info(f"Requesting GEE Thumbnail (Dims: {dims})...")
            
            # Params
            thumb_params = {
                'dimensions': dims,
                'format': 'png',
                'crs': 'EPSG:4326' # Match Leaflet's expected Lat/Lon bounds
            }
            
            # Use polygon geometry if available
            if geojson:
                thumb_params['region'] = geometry
            else:
                # IMPORTANT: Must invoke .getInfo() or similar to get coords if passing as list to some GEE methods,
                # but for getThumbURL, 'region' can be a GeoJSON dictionary or an ee.Geometry.
                # Passing the ee.Geometry object is safest.
                thumb_params['region'] = geometry

            logger.info(f"Thumbnail Params: {thumb_params}")

            # Generate URL
            try:
                url = fused_image.getThumbURL(thumb_params)
                logger.info(f"Got GEE URL: {url}")
            except ee.EEException as e:
                logger.error(f"GEE getThumbURL failed: {e}")
                # Log detailed error for debugging
                return {'success': False, 'error': f"GEE Error: {str(e)}"}

            # Step 5: Download (Re-enabled for stability)
            t2 = time.time()
            fusion_id = f"fusion_{cache_key[:12]}"
            output_path = self.output_dir / f"{fusion_id}.png"
            
            import httpx
            try:
                # Use httpx with timeout to prevent hanging
                # follow_redirects=True is safer
                with httpx.Client(timeout=90.0, follow_redirects=True) as client:
                    response = client.get(url)
                    if response.status_code != 200:
                        logger.error(f"GEE Thumbnail Failed: {response.status_code} - {response.text}")
                        return {'success': False, 'error': f"GEE Error ({response.status_code}): {response.text}"}
                    
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                        
                logger.info(f"Downloaded in {time.time() - t2:.2f}s to: {output_path}")
            except Exception as e:
                logger.error(f"Download failed from URL {url}: {e}")
                return {'success': False, 'error': f"Download failed: {str(e)}"}

            # Return Result
            west, south, east, north = bounds
            leaflet_bounds = [[south, west], [north, east]]
            
            result = {
                'success': True,
                'fusion_id': fusion_id,
                'imageUrl': f"/static/fusion/{fusion_id}.png", # Local Proxy URL
                'bounds': leaflet_bounds,
                'shape': dims,
                'visualization': visualization,
                'dataset_path': dataset_result_path
            }
            
            # Cache
            self._fusion_cache[cache_key] = {
                'timestamp': time.time(),
                'result': result
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in fusion process: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {'success': False, 'error': f"Internal Error: {str(e)}"}

        
        # Add metadata
        
        logger.info("\n" + "=" * 60)
        logger.info(f"✓ Fusion complete: {result['fusion_id']}")
        logger.info(f"  Total bands: {result['total_bands']}")
        logger.info(f"  Image URL: {result['imageUrl']}")
        logger.info("=" * 60)
        
        return result
    
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
        if not self.initialized:
            if not self.initialize_gee():
                return {'success': False, 'error': 'GEE initialization failed'}
        
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
            
            # Helper to prepare image based on visualization
            def prepare_image(img, sensor='sentinel'):
                if sensor == 'sentinel':
                    # Sentinel-2
                    if visualization == 'true_color':
                        return img.multiply(0.0001).clamp(0, 1).visualize(min=0, max=0.3, bands=['B4', 'B3', 'B2'], gamma=1.4)
                    elif visualization == 'ndvi':
                        ndvi = img.normalizedDifference(['B8', 'B4'])
                        return ndvi.visualize(min=-0.2, max=0.8, palette=['brown', 'yellow', 'green'])
                    elif visualization == 'false_color_swir':
                        return img.multiply(0.0001).clamp(0, 1).visualize(min=0, max=0.3, bands=['B12', 'B8', 'B4'], gamma=1.4)
                    elif visualization == 'false_color_nir':
                        return img.multiply(0.0001).clamp(0, 1).visualize(min=0, max=0.4, bands=['B8', 'B4', 'B3'], gamma=1.2)
                    elif visualization == 'ndvi_change':
                        # NDVI Change (temporal difference shown with diverging palette)
                        ndvi = img.normalizedDifference(['B8', 'B4'])
                        return ndvi.visualize(min=-0.5, max=0.5, palette=['blue', 'white', 'red'])
                    elif visualization == 'ndbi':
                        # Normalized Difference Built-up Index
                        # NDBI = (SWIR - NIR) / (SWIR + NIR)
                        ndbi = img.normalizedDifference(['B11', 'B8'])
                        return ndbi.visualize(min=-0.3, max=0.5, palette=['blue', 'gray', 'white'])
                    elif visualization == 'ndwi':
                        # Normalized Difference Water Index
                        # NDWI = (NIR - SWIR) / (NIR + SWIR)
                        ndwi = img.normalizedDifference(['B8', 'B11'])
                        return ndwi.visualize(min=-1, max=1, palette=['brown', 'yellow', 'cyan', 'blue'])
                    elif visualization == 'lst':
                        # Land Surface Temperature (simplified approach)
                        # Using thermal band for visualization
                        thermal = img.select('B10')
                        return thermal.visualize(min=273, max=323, palette=['blue', 'cyan', 'green', 'yellow', 'red'])
                    else:
                        return img.multiply(0.0001).clamp(0, 1).visualize(min=0, max=0.3, bands=['B4', 'B3', 'B2'], gamma=1.4)
                else:
                    # Landsat (Scaling: 0.0000275 + -0.2)
                    scaled = img.multiply(0.0000275).add(-0.2).clamp(0, 1)
                    if visualization == 'true_color':
                        return scaled.visualize(min=0, max=0.3, bands=['SR_B4', 'SR_B3', 'SR_B2'], gamma=1.4)
                    elif visualization == 'ndvi':
                        ndvi = img.normalizedDifference(['SR_B5', 'SR_B4']) # Note: using raw bands for ratio is safer mostly, but scaled is ok
                        return ndvi.visualize(min=-0.2, max=0.8, palette=['brown', 'yellow', 'green'])
                    elif visualization == 'false_color_swir':
                        return scaled.visualize(min=0, max=0.3, bands=['SR_B7', 'SR_B5', 'SR_B4'], gamma=1.4)
                    elif visualization == 'false_color_nir':
                         return scaled.visualize(min=0, max=0.4, bands=['SR_B5', 'SR_B4', 'SR_B3'], gamma=1.2)
                    elif visualization == 'ndvi_change':
                        # NDVI Change for Landsat
                        ndvi = img.normalizedDifference(['SR_B5', 'SR_B4'])
                        return ndvi.visualize(min=-0.5, max=0.5, palette=['blue', 'white', 'red'])
                    elif visualization == 'ndbi':
                        # Normalized Difference Built-up Index for Landsat
                        # NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)
                        ndbi = img.normalizedDifference(['SR_B6', 'SR_B5'])
                        return ndbi.visualize(min=-0.3, max=0.5, palette=['blue', 'gray', 'white'])
                    elif visualization == 'ndwi':
                        # Normalized Difference Water Index for Landsat
                        # NDWI = (NIR - SWIR1) / (NIR + SWIR1)
                        ndwi = img.normalizedDifference(['SR_B5', 'SR_B6'])
                        return ndwi.visualize(min=-1, max=1, palette=['brown', 'yellow', 'cyan', 'blue'])
                    elif visualization == 'lst':
                        # Land Surface Temperature for Landsat
                        # Using thermal band for visualization
                        thermal = img.select('ST_B10')
                        return thermal.visualize(min=273, max=323, palette=['blue', 'cyan', 'green', 'yellow', 'red'])
                    else:
                        return scaled.visualize(min=0, max=0.3, bands=['SR_B4', 'SR_B3', 'SR_B2'], gamma=1.4)

            # Select Collection
            if platform == 'landsat':
                collection = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') \
                    .merge(ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')) \
                    .filterBounds(geometry) \
                    .filterDate(start_date, end_date) \
                    .filter(ee.Filter.lt('CLOUD_COVER', 30))
                
                collection = collection.map(lambda img: prepare_image(img, 'landsat'))
            else:
                # Sentinel-2
                collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                    .filterBounds(geometry) \
                    .filterDate(start_date, end_date) \
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
                
                collection = collection.map(lambda img: prepare_image(img, 'sentinel'))
            
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
            return {'success': False, 'error': str(e)}

    def compute_ndvi(self, fused_tensor: np.ndarray, nir_idx: int = 6, red_idx: int = 2) -> np.ndarray:
        """
        Compute NDVI from fused tensor.
        
        NDVI = (NIR - Red) / (NIR + Red)
        
        Args:
            fused_tensor: (bands, H, W)
            nir_idx: Index of NIR band (default: B8 = index 6)
            red_idx: Index of Red band (default: B4 = index 2)
            
        Returns:
            NDVI array (H, W) with values -1 to 1
        """
        nir = fused_tensor[nir_idx].astype(float)
        red = fused_tensor[red_idx].astype(float)
        
        # Avoid division by zero
        denominator = nir + red
        ndvi = np.where(denominator != 0, (nir - red) / denominator, 0)
        
        return ndvi
    
    def compute_ndwi(self, fused_tensor: np.ndarray, green_idx: int = 1, nir_idx: int = 6) -> np.ndarray:
        """
        Compute NDWI (Normalized Difference Water Index).
        
        NDWI = (Green - NIR) / (Green + NIR)
        
        Args:
            fused_tensor: (bands, H, W)
            green_idx: Index of Green band
            nir_idx: Index of NIR band
            
        Returns:
            NDWI array (H, W)
        """
        green = fused_tensor[green_idx].astype(float)
        nir = fused_tensor[nir_idx].astype(float)
        
        denominator = green + nir
        ndwi = np.where(denominator != 0, (green - nir) / denominator, 0)
        
        return ndwi


# Singleton instance
gee_fusion_service = GEEFusionService()
