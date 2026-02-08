
import os
import sys
import asyncio
from services.sentinel import sentinel_service
from rio_tiler.io import Reader
from datetime import date, timedelta

# Fix env for Windows/GDAL
os.environ["GDAL_HTTP_UNSAFESSL"] = "YES"
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR" # Optimization often needed for COGs

async def test_sentinel_read():
    print("Searching for a Sentinel-2 scene to test...")
    
    # Search generic area (Bangalore)
    bbox = [77.5, 12.9, 77.7, 13.1]
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    try:
        results = sentinel_service.search_scenes(
            bbox=bbox, 
            start_date=start_date, 
            end_date=end_date,
            limit=1
        )
        
        if not results.get("scenes"):
            print("No scenes found to test.")
            return

        scene = results["scenes"][0]
        print(f"Found Scene ID: {scene['id']}")
        
        url = scene.get("download_url") or scene.get("bands", {}).get("visual")
        
        if not url:
            print("No Visual URL found in scene.")
            print(f"Available bands: {scene.get('bands').keys()}")
            return
            
        print(f"Testing URL: {url[:100]}...") # Print beginning of URL (hide some signature)
        
        try:
            with Reader(url) as src:
                print("Reader opened successfully.")
                print(f"Bounds: {src.bounds}")
                print("Attempting to read low-res preview...")
                img = src.preview(max_size=128)
                print(f"Read Success! Data Shape: {img.data.shape}")
                print("Min/Max:", img.data.min(), img.data.max())
        except Exception as e:
            print(f"FAILED to read with Reader: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"Search/Service error: {e}")

if __name__ == "__main__":
    asyncio.run(test_sentinel_read())
