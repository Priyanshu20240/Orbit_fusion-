
import requests
import json
import time

URL = "http://localhost:8000/api/fusion/gee-harmonize"

def test_small_area():
    print(f"Testing Small Area (Scale 10m) connectivity to {URL}...")
    
    # Small AOI (approx 0.01 deg ~ 1km)
    # 1km at 10m scale = 100x100 pixels. fast.
    bounds = [77.200, 28.600, 77.210, 28.610] 
    
    payload = {
        "bounds": bounds,
        "start_date": "2023-01-01",
        "end_date": "2023-01-31",
        "cloud_cover": 20,
        "visualization": "true_color"
    }
    
    try:
        start = time.time()
        print("Sending request...")
        response = requests.post(URL, json=payload, timeout=60)
        elapsed = time.time() - start
        
        print(f"Response status: {response.status_code}")
        print(f"Elapsed time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print("Success!")
            print(f"Image Shape: {data.get('shape')}") # Should reflect small size
            print(f"Image URL: {data.get('imageUrl')}")
        else:
            print("Error Response:", response.text)
            
    except Exception as e:
        print(f"Request FAILED: {e}")

if __name__ == "__main__":
    test_small_area()
