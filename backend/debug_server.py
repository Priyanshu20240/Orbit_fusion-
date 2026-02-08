
import requests
import json
import time

URL = "http://localhost:8000/api/fusion/gee-harmonize"

def test_server():
    print(f"Testing connectivity to {URL}...")
    
    # Payload similar to frontend
    payload = {
        "bounds": [77.10, 28.50, 77.30, 28.70],
        "start_date": "2023-01-01",
        "end_date": "2023-01-31",
        "window_size": 256,
        "cloud_cover": 20,
        "visualization": "true_color"
    }
    
    try:
        start = time.time()
        print("Sending request...")
        response = requests.post(URL, json=payload, timeout=60) # 60s timeout
        elapsed = time.time() - start
        
        print(f"Response status: {response.status_code}")
        print(f"Elapsed time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            print("Response JSON:", json.dumps(response.json(), indent=2)[:500] + "...")
        else:
            print("Error Response:", response.text)
            
    except Exception as e:
        print(f"Request FAILED: {e}")

if __name__ == "__main__":
    test_server()
