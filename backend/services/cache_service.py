"""
Cache Service - Persistent disk-based caching for fusion results

This service implements:
- Disk-based caching for generated images
- Progressive loading (thumbnail + full resolution)
- Image compression with WEBP format
- Cache metadata management
- Automatic cache cleanup
"""

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
import time
from PIL import Image
import io
import os

logger = logging.getLogger(__name__)


class CacheService:
    """
    Persistent disk cache for fusion results and tiles.
    
    Cache structure:
    - cache_dir/
        - metadata.json (cache index)
        - full/     (full resolution images)
        - thumb/    (thumbnails/progressive images)
    """
    
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.full_dir = self.cache_dir / "full"
        self.thumb_dir = self.cache_dir / "thumb"
        self.preview_dir = self.cache_dir / "preview"  # Low-res preview
        
        self.full_dir.mkdir(exist_ok=True)
        self.thumb_dir.mkdir(exist_ok=True)
        self.preview_dir.mkdir(exist_ok=True)
        
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata: Dict = self._load_metadata()
        self.lock = threading.Lock()
        
    def _load_metadata(self) -> Dict:
        """Load cache metadata from disk."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading metadata: {e}")
                return {}
        return {}
    
    def _save_metadata(self):
        """Save cache metadata to disk."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
    
    def _generate_cache_key(self, bounds: tuple, start_date: str, end_date: str, 
                           cloud_cover: float, visualization: str, platforms: list) -> str:
        """Generate a consistent cache key from request parameters."""
        key_str = f"{bounds}_{start_date}_{end_date}_{cloud_cover}_{visualization}_{sorted(platforms)}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get_cached_full(self, cache_key: str) -> Optional[bytes]:
        """Get cached full resolution image."""
        file_path = self.full_dir / f"{cache_key}.webp"
        if file_path.exists():
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                    logger.info(f"✓ Loaded full image from cache: {cache_key[:8]}... ({len(data)} bytes)")
                    return data
            except Exception as e:
                logger.error(f"Error reading cached image: {e}", exc_info=True)
        else:
            logger.warning(f"Full image not found in cache: {file_path}")
        return None
    
    def get_cached_preview(self, cache_key: str) -> Optional[bytes]:
        """Get cached low-resolution preview for progressive loading."""
        file_path = self.preview_dir / f"{cache_key}.webp"
        if file_path.exists():
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                    logger.info(f"✓ Loaded preview from cache: {cache_key[:8]}... ({len(data)} bytes)")
                    return data
            except Exception as e:
                logger.error(f"Error reading preview: {e}", exc_info=True)
        else:
            logger.warning(f"Preview not found in cache: {file_path}")
        return None
    
    def get_cached_thumbnail(self, cache_key: str) -> Optional[bytes]:
        """Get cached thumbnail."""
        file_path = self.thumb_dir / f"{cache_key}.webp"
        if file_path.exists():
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                    logger.info(f"✓ Loaded thumbnail from cache: {cache_key[:8]}... ({len(data)} bytes)")
                    return data
            except Exception as e:
                logger.error(f"Error reading thumbnail: {e}", exc_info=True)
        else:
            logger.warning(f"Thumbnail not found in cache: {file_path}")
        return None
    
    def cache_result(self, cache_key: str, image_bytes: bytes, metadata: dict,
                    create_preview: bool = True) -> Dict:
        """
        Cache a fusion result with multiple resolutions for progressive loading.
        
        Args:
            cache_key: Unique cache key
            image_bytes: Full resolution image data (PNG/JPEG)
            metadata: Metadata about the fusion result
            create_preview: Whether to create a low-res preview
            
        Returns:
            Dictionary with cache paths and metadata
        """
        with self.lock:
            try:
                # Open image from bytes
                img = Image.open(io.BytesIO(image_bytes))
                original_size = img.size
                
                # Save full resolution as WEBP (better compression)
                full_path = self.full_dir / f"{cache_key}.webp"
                img.save(full_path, 'WEBP', quality=90)
                full_size = os.path.getsize(full_path)
                
                # Create and save thumbnail (256x256)
                thumb = img.copy()
                thumb.thumbnail((256, 256), Image.Resampling.LANCZOS)
                thumb_path = self.thumb_dir / f"{cache_key}.webp"
                thumb.save(thumb_path, 'WEBP', quality=85)
                thumb_size = os.path.getsize(thumb_path)
                
                # Create and save low-res preview (128x128) for faster loading
                preview = img.copy()
                preview.thumbnail((128, 128), Image.Resampling.LANCZOS)
                preview_path = self.preview_dir / f"{cache_key}.webp"
                preview.save(preview_path, 'WEBP', quality=70)
                preview_size = os.path.getsize(preview_path)
                
                # Update metadata
                self.metadata[cache_key] = {
                    'timestamp': datetime.now().isoformat(),
                    'bounds': metadata.get('bounds'),
                    'start_date': metadata.get('start_date'),
                    'end_date': metadata.get('end_date'),
                    'visualization': metadata.get('visualization'),
                    'platforms': metadata.get('platforms'),
                    'original_size': original_size,
                    'full_size_bytes': full_size,
                    'thumb_size_bytes': thumb_size,
                    'preview_size_bytes': preview_size,
                    'compression_ratio': full_size / len(image_bytes) if image_bytes else 0
                }
                self._save_metadata()
                
                logger.info(f"✓ Cached fusion result: {cache_key[:8]}... "
                           f"(Full: {full_size//1024}KB, Preview: {preview_size//1024}KB)")
                
                return {
                    'full_path': str(full_path),
                    'preview_path': str(preview_path),
                    'thumbnail_path': str(thumb_path),
                    'full_size': full_size,
                    'preview_size': preview_size,
                    'compression_ratio': full_size / len(image_bytes) if image_bytes else 0
                }
            
            except Exception as e:
                logger.error(f"Error caching result: {e}", exc_info=True)
                return None
    
    def get_cache_status(self, cache_key: str) -> Dict:
        """Get status of a cached item."""
        if cache_key not in self.metadata:
            return {'exists': False}
        
        meta = self.metadata[cache_key]
        return {
            'exists': True,
            'timestamp': meta.get('timestamp'),
            'full_size_mb': meta.get('full_size_bytes', 0) / (1024 * 1024),
            'preview_size_kb': meta.get('preview_size_bytes', 0) / 1024,
            'compression_ratio': meta.get('compression_ratio', 0)
        }
    
    def cleanup_old_cache(self, max_age_days: int = 7) -> Dict:
        """
        Clean up cache items older than max_age_days.
        
        Returns:
            Statistics about cleanup (items removed, space freed)
        """
        with self.lock:
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            items_removed = 0
            space_freed = 0
            
            keys_to_remove = []
            for cache_key, meta in self.metadata.items():
                timestamp_str = meta.get('timestamp')
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        if timestamp < cutoff_time:
                            keys_to_remove.append(cache_key)
                    except:
                        pass
            
            for cache_key in keys_to_remove:
                try:
                    # Remove files
                    for file_dir in [self.full_dir, self.thumb_dir, self.preview_dir]:
                        file_path = file_dir / f"{cache_key}.webp"
                        if file_path.exists():
                            space_freed += os.path.getsize(file_path)
                            os.remove(file_path)
                    
                    # Remove metadata
                    del self.metadata[cache_key]
                    items_removed += 1
                except Exception as e:
                    logger.error(f"Error removing cache item {cache_key}: {e}")
            
            if items_removed > 0:
                self._save_metadata()
            
            logger.info(f"✓ Cache cleanup: Removed {items_removed} items, freed {space_freed/(1024*1024):.2f}MB")
            
            return {
                'items_removed': items_removed,
                'space_freed_mb': space_freed / (1024 * 1024)
            }
    
    def get_cache_stats(self) -> Dict:
        """Get overall cache statistics."""
        total_size = 0
        total_items = len(self.metadata)
        
        for dir_path in [self.full_dir, self.thumb_dir, self.preview_dir]:
            for file in dir_path.glob("*.webp"):
                total_size += os.path.getsize(file)
        
        return {
            'total_items': total_items,
            'total_size_mb': total_size / (1024 * 1024),
            'cache_dir': str(self.cache_dir)
        }


# Singleton instance
cache_service = CacheService()
