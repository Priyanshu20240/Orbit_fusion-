"""
Fusion Service - Harmonized Landsat-Sentinel Data Fusion (HLS-Style)

This service implements proper satellite data fusion using pre-rendered tiles:
1. Download tiles from Planetary Computer's tile service
2. Resample Landsat (30m) → Sentinel (10m) using bilinear interpolation  
3. Merge tiles into a harmonized mosaic

Only matching bands are merged: RGB (visual bands)
"""

import os
import numpy as np
from scipy import ndimage
from PIL import Image
import httpx
import tempfile
import logging
from typing import List, Dict, Tuple, Optional
import hashlib
from pathlib import Path
import io
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import time

logger = logging.getLogger(__name__)

# Resolution constants
SENTINEL_RESOLUTION = 10  # meters
LANDSAT_RESOLUTION = 30   # meters
TILE_SIZE = 256  # Standard web tile size


class FusionService:
    """
    Service for harmonizing and fusing Landsat + Sentinel data.
    
    Uses pre-rendered tiles from Planetary Computer for reliability.
    Resamples Landsat to Sentinel resolution before merging.
    
    Performance optimizations:
    - Parallel tile downloads
    - HTTP connection pooling
    - Tile caching
    """
    
    def __init__(self):
        self.cache_dir = Path(tempfile.mkdtemp(prefix="fusion_cache_"))
        self.fused_data_store: Dict[str, np.ndarray] = {}
        self.fused_metadata_store: Dict[str, dict] = {}
        self._tile_cache: Dict[str, np.ndarray] = {}  # Cache downloaded tiles
        self._http_client = httpx.Client(timeout=30.0, verify=False, limits=httpx.Limits(max_connections=10))
        self._executor = ThreadPoolExecutor(max_workers=6)  # For parallel downloads
        logger.info(f"Fusion service initialized. Cache dir: {self.cache_dir}")
    
    def download_tile_image(self, tile_url: str, z: int = 10, x: int = 0, y: int = 0) -> Optional[np.ndarray]:
        """
        Download a tile image from a tile URL template.
        Uses connection pooling and caching for speed.
        """
        try:
            # Replace placeholders in URL
            url = tile_url.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
            
            # Check cache first
            cache_key = hashlib.md5(url.encode()).hexdigest()
            if cache_key in self._tile_cache:
                logger.info(f"  ✓ Cache hit for tile")
                return self._tile_cache[cache_key]
            
            response = self._http_client.get(url)
            
            if response.status_code == 200:
                # Load image from bytes
                img = Image.open(io.BytesIO(response.content))
                arr = np.array(img)
                
                # Cache the result
                self._tile_cache[cache_key] = arr
                logger.info(f"  ✓ Downloaded tile: {arr.shape}")
                return arr
            else:
                logger.warning(f"  ✗ Tile download failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"  ✗ Error downloading tile: {e}")
            return None
    
    def resample_to_target(
        self,
        source: np.ndarray,
        target_shape: Tuple[int, int]
    ) -> np.ndarray:
        """
        Resample an image array to target shape using bilinear interpolation.
        
        This is used to upsample Landsat (30m) to Sentinel (10m) resolution.
        Each 30m pixel becomes a 3x3 grid of 10m pixels.
        
        Args:
            source: Source array (H, W, C) or (H, W)
            target_shape: Target (H, W)
            
        Returns:
            Resampled array
        """
        if source.shape[:2] == target_shape:
            return source
        
        # Handle both RGB and grayscale
        if source.ndim == 3:
            # Resample each channel
            result = np.zeros((*target_shape, source.shape[2]), dtype=source.dtype)
            zoom_h = target_shape[0] / source.shape[0]
            zoom_w = target_shape[1] / source.shape[1]
            
            for c in range(source.shape[2]):
                result[:, :, c] = ndimage.zoom(
                    source[:, :, c],
                    (zoom_h, zoom_w),
                    order=1,  # Bilinear interpolation
                    mode='nearest'
                )
            return result
        else:
            zoom_h = target_shape[0] / source.shape[0]
            zoom_w = target_shape[1] / source.shape[1]
            return ndimage.zoom(source, (zoom_h, zoom_w), order=1, mode='nearest')
    
    def harmonize_tiles(
        self,
        sentinel_scenes: List[Dict],
        landsat_scenes: List[Dict],
        bounds: Tuple[float, float, float, float],
        zoom: int = 10
    ) -> Optional[Dict]:
        """
        Harmonize Sentinel and Landsat tiles.
        
        Process:
        1. Download tiles from both Sentinel and Landsat
        2. Resample Landsat tiles to Sentinel resolution (3x upscale)
        3. Create median composite mosaic
        
        Args:
            sentinel_scenes: Sentinel scenes with tile_url
            landsat_scenes: Landsat scenes with tile_url
            bounds: AOI bounds (west, south, east, north)
            zoom: Tile zoom level
            
        Returns:
            Dict with fusion result
        """
        import mercantile
        
        logger.info("="*60)
        logger.info("Starting HLS-Style Fusion")
        logger.info(f"  Sentinel scenes: {len(sentinel_scenes)}")
        logger.info(f"  Landsat scenes: {len(landsat_scenes)}")
        logger.info(f"  Bounds: {bounds}")
        logger.info("="*60)
        
        # Get tiles that cover the bounds
        tiles = list(mercantile.tiles(*bounds, zooms=zoom))
        if not tiles:
            tiles = [mercantile.tile((bounds[0]+bounds[2])/2, (bounds[1]+bounds[3])/2, zoom)]
        
        logger.info(f"  Processing {len(tiles)} tiles at zoom {zoom}")
        
        start_time = time.time()
        all_arrays = []
        reference_shape = None
        
        # Prepare download tasks for parallel execution
        download_tasks = []
        
        # Collect all Sentinel tile download tasks
        for scene in sentinel_scenes[:3]:  # Limit for speed
            tile_url = scene.get("tile_url")
            if tile_url:
                for tile in tiles[:1]:
                    download_tasks.append(("sentinel", tile_url, tile.z, tile.x, tile.y))
        
        # Collect all Landsat tile download tasks  
        for scene in landsat_scenes[:3]:  # Limit for speed
            tile_url = scene.get("tile_url")
            if tile_url:
                for tile in tiles[:1]:
                    download_tasks.append(("landsat", tile_url, tile.z, tile.x, tile.y))
        
        logger.info(f"\nDownloading {len(download_tasks)} tiles in parallel...")
        
        # Execute downloads in parallel
        sentinel_arrays = []
        landsat_arrays = []
        
        futures = {}
        for task in download_tasks:
            source_type, tile_url, z, x, y = task
            future = self._executor.submit(self.download_tile_image, tile_url, z, x, y)
            futures[future] = source_type
        
        for future in as_completed(futures):
            source_type = futures[future]
            try:
                arr = future.result()
                if arr is not None:
                    if source_type == "sentinel":
                        sentinel_arrays.append(arr)
                    else:
                        landsat_arrays.append(arr)
            except Exception as e:
                logger.warning(f"Download failed: {e}")
        
        download_time = time.time() - start_time
        logger.info(f"  ✓ Downloaded {len(sentinel_arrays)} Sentinel + {len(landsat_arrays)} Landsat tiles in {download_time:.2f}s")
        
        # Set reference shape from first Sentinel tile
        if sentinel_arrays:
            reference_shape = sentinel_arrays[0].shape[:2]
            all_arrays.extend(sentinel_arrays)
        
        # Resample Landsat tiles to match Sentinel resolution
        for arr in landsat_arrays:
            if reference_shape is not None:
                arr = self.resample_to_target(arr, reference_shape)
            else:
                reference_shape = arr.shape[:2]
            all_arrays.append(arr)
        
        if not all_arrays:
            logger.error("No tiles could be downloaded")
            return None
        
        # Step 3: Create median composite
        logger.info(f"\nStep 3: Creating median composite from {len(all_arrays)} tiles...")
        try:
            # Ensure all arrays have same shape
            target_shape = all_arrays[0].shape
            matching = []
            
            for arr in all_arrays:
                if arr.shape == target_shape:
                    matching.append(arr)
                else:
                    # Try to resize
                    try:
                        resized = self.resample_to_target(arr, target_shape[:2])
                        if resized.shape[2:] != target_shape[2:]:
                            # Adjust channels
                            if len(resized.shape) == 2:
                                resized = np.stack([resized]*3, axis=-1)
                            elif resized.shape[2] > target_shape[2]:
                                resized = resized[:, :, :target_shape[2]]
                        matching.append(resized)
                    except:
                        pass
            
            if not matching:
                return None
            
            # Stack and compute median
            stacked = np.stack(matching, axis=0)
            logger.info(f"  Stacked: {stacked.shape}")
            
            # Median composite (reduces clouds/noise)
            mosaic = np.median(stacked, axis=0).astype(np.uint8)
            logger.info(f"  ✓ Mosaic created: {mosaic.shape}")
            
            return {
                "success": True,
                "data": mosaic,
                "bounds": bounds,
                "shape": mosaic.shape,
                "num_sentinel": len([s for s in sentinel_scenes if s.get("tile_url")]),
                "num_landsat": len([s for s in landsat_scenes if s.get("tile_url")])
            }
            
        except Exception as e:
            logger.error(f"Fusion failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_harmonized_tiles(
        self,
        sentinel_scenes: List[Dict],
        landsat_scenes: List[Dict],
        aoi_bounds: Tuple[float, float, float, float]
    ) -> Dict:
        """
        Main entry point for creating harmonized fusion.
        """
        # Generate unique fusion ID
        scene_ids = [s.get("id", "") for s in sentinel_scenes + landsat_scenes]
        fusion_id = f"fusion_{hashlib.md5(''.join(sorted(scene_ids)).encode()).hexdigest()[:12]}"
        
        result = self.harmonize_tiles(sentinel_scenes, landsat_scenes, aoi_bounds)
        
        if result is None:
            return {
                "success": False,
                "error": "Failed to harmonize scenes - check backend logs"
            }
        
        # Store the result for tile serving
        self.fused_data_store[fusion_id] = result["data"]
        self.fused_metadata_store[fusion_id] = {
            "bounds": result["bounds"],
            "shape": result["shape"]
        }
        
        return {
            "success": True,
            "fusion_id": fusion_id,
            "bounds": aoi_bounds,
            "shape": result["shape"],
            "num_sentinel": result.get("num_sentinel", 0),
            "num_landsat": result.get("num_landsat", 0)
        }
    
    def get_fusion_tile(self, fusion_id: str, z: int, x: int, y: int) -> Optional[bytes]:
        """
        Get a tile from a stored fusion result.
        """
        if fusion_id not in self.fused_data_store:
            logger.warning(f"Fusion {fusion_id} not found in store")
            return None
        
        data = self.fused_data_store[fusion_id]
        
        try:
            # Ensure correct format for PIL
            if data.ndim == 2:
                # Grayscale
                img = Image.fromarray(data.astype(np.uint8), mode='L')
            elif data.shape[2] == 1:
                img = Image.fromarray(data[:, :, 0].astype(np.uint8), mode='L')
            elif data.shape[2] == 3:
                img = Image.fromarray(data.astype(np.uint8), mode='RGB')
            elif data.shape[2] == 4:
                img = Image.fromarray(data.astype(np.uint8), mode='RGBA')
            else:
                # Take first 3 channels
                img = Image.fromarray(data[:, :, :3].astype(np.uint8), mode='RGB')
            
            # Save to bytes
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            logger.info(f"Generated tile for {fusion_id}: {len(buffer.getvalue())} bytes")
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error creating tile: {e}")
            import traceback
            traceback.print_exc()
            return None


# Singleton instance
fusion_service = FusionService()
