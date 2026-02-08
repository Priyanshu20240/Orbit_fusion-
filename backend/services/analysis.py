"""
Analysis Service - NDVI, Reprojection, Resampling, and Fusion
Core deep-tech algorithms for multi-satellite data fusion
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Service for satellite image analysis and fusion operations.
    Provides NDVI calculation, reprojection, resampling, and multi-source fusion.
    """
    
    def __init__(self):
        self.target_crs = "EPSG:4326"
        self.target_resolution = 10  # meters (Sentinel-2 native)
    
    # =============================
    # NDVI Calculation
    # =============================
    
    def calculate_ndvi(self, nir: np.ndarray, red: np.ndarray) -> np.ndarray:
        """
        Calculate Normalized Difference Vegetation Index (NDVI).
        
        NDVI = (NIR - Red) / (NIR + Red)
        
        Args:
            nir: Near-Infrared band array
            red: Red band array
            
        Returns:
            NDVI array with values from -1 to 1
        """
        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            ndvi = (nir.astype(float) - red.astype(float)) / (nir.astype(float) + red.astype(float))
            ndvi = np.nan_to_num(ndvi, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Clip to valid range
        ndvi = np.clip(ndvi, -1.0, 1.0)
        
        return ndvi
    
    def calculate_ndwi(self, green: np.ndarray, nir: np.ndarray) -> np.ndarray:
        """
        Calculate Normalized Difference Water Index (NDWI).
        
        NDWI = (Green - NIR) / (Green + NIR)
        
        Used to detect water bodies.
        """
        with np.errstate(divide='ignore', invalid='ignore'):
            ndwi = (green.astype(float) - nir.astype(float)) / (green.astype(float) + nir.astype(float))
            ndwi = np.nan_to_num(ndwi, nan=0.0, posinf=0.0, neginf=0.0)
        
        return np.clip(ndwi, -1.0, 1.0)
    
    def get_ndvi_statistics(self, ndvi: np.ndarray) -> Dict:
        """
        Calculate statistics for an NDVI array.
        """
        valid_mask = ~np.isnan(ndvi)
        valid_data = ndvi[valid_mask]
        
        if len(valid_data) == 0:
            return {"error": "No valid NDVI data"}
        
        # Classify vegetation
        bare_soil = np.sum((valid_data >= -0.1) & (valid_data < 0.1)) / len(valid_data) * 100
        sparse_veg = np.sum((valid_data >= 0.1) & (valid_data < 0.3)) / len(valid_data) * 100
        moderate_veg = np.sum((valid_data >= 0.3) & (valid_data < 0.6)) / len(valid_data) * 100
        dense_veg = np.sum(valid_data >= 0.6) / len(valid_data) * 100
        
        return {
            "min": float(np.min(valid_data)),
            "max": float(np.max(valid_data)),
            "mean": float(np.mean(valid_data)),
            "std": float(np.std(valid_data)),
            "median": float(np.median(valid_data)),
            "percentile_25": float(np.percentile(valid_data, 25)),
            "percentile_75": float(np.percentile(valid_data, 75)),
            "classification": {
                "bare_soil_percent": round(bare_soil, 2),
                "sparse_vegetation_percent": round(sparse_veg, 2),
                "moderate_vegetation_percent": round(moderate_veg, 2),
                "dense_vegetation_percent": round(dense_veg, 2)
            }
        }
    
    # =============================
    # Resampling
    # =============================
    
    def resample_array(
        self,
        array: np.ndarray,
        source_resolution: float,
        target_resolution: float,
        method: str = "bicubic"
    ) -> np.ndarray:
        """
        Resample an array from source to target resolution.
        
        Args:
            array: Input 2D array
            source_resolution: Source pixel size in meters
            target_resolution: Target pixel size in meters
            method: Interpolation method ('nearest', 'bilinear', 'bicubic')
            
        Returns:
            Resampled array
        """
        if source_resolution == target_resolution:
            return array
        
        scale_factor = source_resolution / target_resolution
        
        # Calculate new dimensions
        new_height = int(array.shape[0] * scale_factor)
        new_width = int(array.shape[1] * scale_factor)
        
        if method == "nearest":
            return self._resample_nearest(array, new_height, new_width)
        elif method == "bilinear":
            return self._resample_bilinear(array, new_height, new_width)
        elif method == "bicubic":
            return self._resample_bicubic(array, new_height, new_width)
        else:
            raise ValueError(f"Unknown resampling method: {method}")
    
    def _resample_nearest(self, array: np.ndarray, new_h: int, new_w: int) -> np.ndarray:
        """Nearest neighbor resampling."""
        h, w = array.shape[:2]
        y_indices = (np.arange(new_h) * h / new_h).astype(int)
        x_indices = (np.arange(new_w) * w / new_w).astype(int)
        return array[np.ix_(y_indices, x_indices)]
    
    def _resample_bilinear(self, array: np.ndarray, new_h: int, new_w: int) -> np.ndarray:
        """Bilinear interpolation resampling."""
        h, w = array.shape[:2]
        
        # Create coordinate grids
        y = np.linspace(0, h - 1, new_h)
        x = np.linspace(0, w - 1, new_w)
        
        result = np.zeros((new_h, new_w), dtype=array.dtype)
        
        for i, yi in enumerate(y):
            for j, xi in enumerate(x):
                y0, y1 = int(yi), min(int(yi) + 1, h - 1)
                x0, x1 = int(xi), min(int(xi) + 1, w - 1)
                
                fy = yi - y0
                fx = xi - x0
                
                result[i, j] = (
                    array[y0, x0] * (1 - fx) * (1 - fy) +
                    array[y0, x1] * fx * (1 - fy) +
                    array[y1, x0] * (1 - fx) * fy +
                    array[y1, x1] * fx * fy
                )
        
        return result
    
    def _resample_bicubic(self, array: np.ndarray, new_h: int, new_w: int) -> np.ndarray:
        """
        Bicubic interpolation resampling.
        Higher quality than bilinear, used for upscaling Landsat to Sentinel resolution.
        """
        # For simplicity, use bilinear as fallback
        # In production, would use scipy.ndimage.zoom or similar
        return self._resample_bilinear(array, new_h, new_w)
    
    # =============================
    # Fusion Algorithms
    # =============================
    
    def fuse_gap_fill(
        self,
        sentinel_nir: np.ndarray,
        sentinel_red: np.ndarray,
        landsat_nir: np.ndarray,
        landsat_red: np.ndarray
    ) -> np.ndarray:
        """
        Gap-Fill Fusion: Augment Sentinel-2 with Landsat 8/9.
        
        Logic:
        1. Calculate NDVI for Sentinel (Master).
        2. Calculate NDVI for Landsat (Gap-Filler).
        3. Fill NaN/Invalid Sentinel pixels with Landsat pixels.
        
        Ref: np.where(Sentinel_Valid, Sentinel_NDVI, Landsat_NDVI)
        """
        # Calculate individual indices
        sentinel_ndvi = self.calculate_ndvi(sentinel_nir, sentinel_red)
        landsat_ndvi = self.calculate_ndvi(landsat_nir, landsat_red)
        
        # Determine validity (NaN check)
        # Assuming NaN represents missing data (clouds/nodata masked as NaN)
        sentinel_valid = ~np.isnan(sentinel_ndvi)
        
        # Merge
        # If Sentinel is valid, use it. Else use Landsat.
        # Note: If valid Landsat is also NaN, result is NaN (correct).
        fused_ndvi = np.where(sentinel_valid, sentinel_ndvi, landsat_ndvi)
        
        return fused_ndvi

    
    def fuse_best_pixel(
        self,
        images: List[np.ndarray],
        quality_masks: List[np.ndarray] = None
    ) -> np.ndarray:
        """
        Best-pixel fusion: Select the best pixel from multiple images.
        
        Prioritizes cloud-free, high-quality pixels.
        
        Args:
            images: List of 2D arrays (must be same shape)
            quality_masks: Optional quality masks (0=bad, 1=good)
            
        Returns:
            Fused image array
        """
        if not images:
            raise ValueError("No images provided for fusion")
        
        if len(images) == 1:
            return images[0]
        
        # Ensure all images are same shape
        shape = images[0].shape
        for img in images[1:]:
            if img.shape != shape:
                raise ValueError("All images must have the same shape")
        
        # Stack images
        stack = np.stack(images, axis=0)
        
        if quality_masks:
            # Use quality masks to select best pixel
            mask_stack = np.stack(quality_masks, axis=0)
            # Find first good pixel in stack order
            result = np.zeros(shape, dtype=images[0].dtype)
            
            for i in range(shape[0]):
                for j in range(shape[1]):
                    for k, mask in enumerate(quality_masks):
                        if mask[i, j] > 0:
                            result[i, j] = images[k][i, j]
                            break
                    else:
                        # No good pixel found, use median
                        result[i, j] = np.median(stack[:, i, j])
            
            return result
        else:
            # Without quality masks, use median to reduce noise
            return np.median(stack, axis=0).astype(images[0].dtype)
    
    def fuse_mean(self, images: List[np.ndarray]) -> np.ndarray:
        """Simple mean fusion of multiple images."""
        if not images:
            raise ValueError("No images provided")
        stack = np.stack(images, axis=0)
        return np.mean(stack, axis=0).astype(images[0].dtype)
    
    def fuse_median(self, images: List[np.ndarray]) -> np.ndarray:
        """Median fusion - robust to outliers."""
        if not images:
            raise ValueError("No images provided")
        stack = np.stack(images, axis=0)
        return np.median(stack, axis=0).astype(images[0].dtype)
    
    # =============================
    # Comparison Analysis
    # =============================
    
    def compare_ndvi(
        self,
        ndvi_sentinel: np.ndarray,
        ndvi_landsat: np.ndarray
    ) -> Dict:
        """
        Compare NDVI values from Sentinel and Landsat for the same area.
        
        Returns correlation and difference statistics.
        """
        # Ensure same shape (resample if needed)
        if ndvi_sentinel.shape != ndvi_landsat.shape:
            # Resample Landsat to Sentinel resolution
            scale = ndvi_sentinel.shape[0] / ndvi_landsat.shape[0]
            ndvi_landsat = self.resample_array(
                ndvi_landsat,
                source_resolution=30,
                target_resolution=10
            )
        
        # Flatten for statistics
        s = ndvi_sentinel.flatten()
        l = ndvi_landsat.flatten()
        
        # Remove invalid values
        valid = ~(np.isnan(s) | np.isnan(l))
        s = s[valid]
        l = l[valid]
        
        if len(s) == 0:
            return {"error": "No valid overlapping data"}
        
        # Calculate difference
        diff = s - l
        
        # Correlation coefficient
        correlation = np.corrcoef(s, l)[0, 1]
        
        return {
            "correlation": float(correlation),
            "sentinel_mean": float(np.mean(s)),
            "landsat_mean": float(np.mean(l)),
            "mean_difference": float(np.mean(diff)),
            "std_difference": float(np.std(diff)),
            "rmse": float(np.sqrt(np.mean(diff**2))),
            "bias": float(np.mean(diff))
        }


# Singleton instance
analysis_service = AnalysisService()
