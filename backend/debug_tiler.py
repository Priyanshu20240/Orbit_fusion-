
import os
import sys

# Attempt to fix SSL BEFORE importing rasterio
os.environ["GDAL_HTTP_UNSAFESSL"] = "YES"
os.environ["CURL_CA_BUNDLE"] = ""

try:
    import rasterio
    print(f"Rasterio Version: {rasterio.__version__}")
except ImportError as e:
    print(f"Failed to import rasterio: {e}")
    sys.exit(1)

# Test URL (OpenAerialMap - Public)
TEST_URL = "https://oin-hotosm.s3.amazonaws.com/59c66c5223c8440011d7b1e4/0/7ad397c0-bba2-4f98-a08a-931ec3a6e943.tif"

print(f"\nTesting URL: {TEST_URL}")

try:
    with rasterio.open(TEST_URL) as src:
        print("✅ SUCCESS: Successfully opened URL with rasterio!")
        print(f"Profile: {src.profile}")
except Exception as e:
    print(f"❌ ERROR: Failed to open URL.")
    print(f"Error Type: {type(e).__name__}")
    print(f"Error Message: {e}")
    import traceback
    traceback.print_exc()

print("\n-------------------------------------------")
print("Diagnosis:")
print("If specific SSL cert error -> GDAL env vars needed.")
print("If 'permissions' error -> Bucket is private/requester pays.")
print("If DLL load failed -> rasterio installation broken.")
