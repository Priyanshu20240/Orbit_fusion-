
import os
from rio_tiler.io import Reader
import sys

# Fix env
os.environ["GDAL_HTTP_UNSAFESSL"] = "YES"
os.environ["CURL_CA_BUNDLE"] = ""

def test_read():
    # Use a solid COG URL (Sentinel-2 L2A TCI)
    # Note: Sentinel-2 on AWS is Request Pays.
    # Let's use a simpler one.
    # OpenAerialMap?
    url = "https://s3.amazonaws.com/elevation-tiles-prod/geotiff/1/0/0.tif" 
    # Or simple standard COG
    # https://github.com/cogeotiff/rio-tiler/blob/main/tests/fixtures/cog.tif?raw=true
    url = "https://github.com/cogeotiff/rio-tiler/raw/main/tests/fixtures/cog.tif"
    
    print(f"Testing Reader with {url}")
    try:
        with Reader(url) as src:
            print("Reader Opened.")
            info = src.info()
            print(f"Info: {info.bounds}")
            
            print("Reading tile 0/0/0...")
            # For this specific COG, 0/0/0 might be outside bounds?
            # It's a small COG. Coverage?
            # Bounds: usually in web mercator or latlon?
            # Test fixture is usually small.
            # Let's just read preview().
            
            img = src.preview(max_size=128)
            print(f"Preview Read Success! Shape: {img.data.shape}")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_read()
