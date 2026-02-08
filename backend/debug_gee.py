
import logging
import sys
import os
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from services.gee_fusion_service import gee_fusion_service
    import ee
except ImportError:
    # Handle running from root or backend dir
    sys.path.append(os.getcwd())
    from services.gee_fusion_service import gee_fusion_service
    import ee

def test_gee_fusion():
    print("Testing GEE Fusion Service...")
    
    # 1. Initialize
    print("Initializing GEE...")
    if not gee_fusion_service.initialize_gee():
        print("Failed to initialize GEE!")
        return
        
    print("GEE Initialized.")
    
    # 2. Define test parameters (New Delhi area)
    bounds = (77.10, 28.50, 77.30, 28.70)
    start_date = "2023-02-01"
    end_date = "2023-02-28"
    
    # 3. Test Sentinel fetching
    print("\nTesting Sentinel fetch...")
    try:
        s_img = gee_fusion_service.get_sentinel_image(bounds, start_date, end_date)
        if s_img:
            print("Sentinel image found (Lazy EE object)")
            # Try to get info to verify it's real
            print("Band names:", s_img.bandNames().getInfo())
        else:
            print("No Sentinel image found!")
    except Exception as e:
        print(f"Sentinel fetch FAILED: {e}")
        import traceback
        traceback.print_exc()

    # 4. Test Landsat fetching
    print("\nTesting Landsat fetch...")
    try:
        l_img = gee_fusion_service.get_landsat_image(bounds, start_date, end_date)
        if l_img:
            print("Landsat image found (Lazy EE object)")
            print("Band names:", l_img.bandNames().getInfo())
        else:
            print("No Landsat image found!")
    except Exception as e:
        print(f"Landsat fetch FAILED: {e}")
        import traceback
        traceback.print_exc()

    # 5. Test Full Fusion
    print("\nTesting Full Fusion Pipeline...")
    try:
        result = gee_fusion_service.create_harmonized_fusion(
            bounds=bounds,
            start_date=start_date,
            end_date=end_date,
            visualization="true_color"
        )
        print("Fusion Result:", result)
        if result.get("success"):
            print("Fusion SUCCESS!")
        else:
            print("Fusion FAILED explicitly:", result.get("error"))
    except Exception as e:
        print(f"Fusion CRASHED: {e}")
        import traceback
        traceback.print_exc()

    # 6. Test Cache
    print("\nTesting Cache (Second Call)...")
    try:
        start = time.time()
        result = gee_fusion_service.create_harmonized_fusion(
            bounds=bounds,
            start_date=start_date,
            end_date=end_date,
            visualization="true_color"
        )
        elapsed = time.time() - start
        print(f"Second call took {elapsed:.4f}s")
        if elapsed < 1.0:
            print("Cache HIT - SUCCESS!")
        else:
            print("Cache MISS - Failed to cache?")
            
    except Exception as e:
        print(f"Cache Test CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gee_fusion()
