
import asyncio
import os
import json
from services.sentinel import sentinel_service
from cogeo_mosaic.mosaic import MosaicJSON
from cogeo_mosaic.backends import MemoryBackend
import mercantile
from datetime import date, timedelta

# Mocking the request/scene data structure
class MockScene:
    def __init__(self, url, geometry):
        self.url = url
        self.geometry = geometry

async def test_mosaic_coverage():
    print("Searching for a Sentinel-2 scene...")
    # Bbox for Bangalore/Southern India
    bbox = [77.0, 12.0, 78.0, 13.0]
    
    # Tile 9/365/225 bounds
    tile_bounds = mercantile.bounds(365, 225, 9)
    print(f"Target Tile (9/365/225) Bounds (Lon/Lat): {tile_bounds}")
    
    # Use center of this tile for search to ensure we get a covering scene
    center_lon = (tile_bounds.west + tile_bounds.east) / 2
    center_lat = (tile_bounds.south + tile_bounds.north) / 2
    print(f"Searching around {center_lon}, {center_lat}")
    
    bbox = [center_lon - 0.1, center_lat - 0.1, center_lon + 0.1, center_lat + 0.1]

    results = sentinel_service.search_scenes(
        bbox=bbox, 
        start_date=date.today() - timedelta(days=30), 
        end_date=date.today(),
        limit=1
    )
    
    if not results.get("scenes"):
        print("No scenes found covering this tile.")
        return

    scene = results["scenes"][0]
    print(f"Found Scene: {scene['id']}")
    
    url = scene.get("download_url") or scene.get("bands", {}).get("visual")
    print(f"Scene URL: {url[:50]}...")
    
    # Create Mosaic Definition
    feature = {
        "type": "Feature",
        "geometry": scene["geometry"],
        "properties": {
             "path": url
        }
    }
    
    print("Generating MosaicJSON...")
    # Matches main.py logic with fix?
    mosaic_def = MosaicJSON.from_features([feature], minzoom=1, maxzoom=15, quadkey_zoom=15)
    
    print(f"Mosaic Bounds: {mosaic_def.bounds}")
    
    # Check if target tile is in mosaic
    # mosaic_def.tiles is a dict of {quadkey: [assets]}
    # We need to convert 9/372/216 to quadkey
    qk = mercantile.quadkey(372, 216, 9)
    print(f"Target Quadkey: {qk}")
    
    if qk in mosaic_def.tiles:
        print("SUCCESS: Target tile IS in the mosaic definition.")
        print(f"Assets for tile: {mosaic_def.tiles[qk]}")
    else:
        print("FAILURE: Target tile is NOT in the mosaic definition.")
        # Print some close quadkeys
        print(f"Total tiles in mosaic: {len(mosaic_def.tiles)}")
    
    
    # Inspect generated zoom levels
    zooms = set([len(k) for k in mosaic_def.tiles.keys()])
    print(f"Generated Zoom Levels: {sorted(list(zooms))}")

    # SIMULATE BACKEND REQUEST
    print("\n--- Simulating Backend Request ---")
    
    # Needs to match main.py class exactly or import it?
    # Let's import the actual backend definition from main if possible, 
    # but main.py is an app, might run code.
    # Let's just define a minimal backend here or use cogeo_mosaic's base if compatible
    # But main.py defined a custom InMemoryMosaicBackend.
    # Let's just mock it using the standard MemoryBackend which is what InMemoryMosaicBackend basically does
    
    mosaic_data = mosaic_def.dict(exclude_none=True)
    
    try:
        # Use context manager as per main.py
        with MemoryBackend(mosaic_def) as backend:
            print(f"Backend initialized. Quads: {len(mosaic_data.get('tiles', {}))}")
            
            # Tile from User Request: 9/365/225
            z, x, y = 9, 365, 225
            print(f"Requesting tile {z}/{x}/{y}...")
            
            assets = backend.assets_for_tile(x, y, z)
            print(f"Assets found: {len(assets)}")
            if assets:
                print(f"First asset: {assets[0]}")
                
            img, _ = backend.tile(x, y, z)
            print(f"Backend Tile Read SUCCESS. Shape: {img.data.shape}")
            
            # Also try the other user reported tile: 8/184/110
            z2, x2, y2 = 8, 184, 110
            print(f"Requesting tile {z2}/{x2}/{y2}...")
            img2, _ = backend.tile(x2, y2, z2)
            print(f"Backend Tile Read SUCCESS (8/184/110). Shape: {img2.data.shape}")

    except Exception as e:
        print(f"BACKEND SIMULATION FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mosaic_coverage())
