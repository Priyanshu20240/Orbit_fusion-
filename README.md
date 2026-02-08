# Orbiter Fusion Platform (ASTRAVISION) - Technical Documentation

## 1. Project Overview
**Orbiter Fusion** is a specialized multi-satellite data fusion dashboard. It integrates data from **Sentinel-2** (European Space Agency) and **Landsat-8/9** (NASA/USGS) to create superior fused imagery. 

The core power of this application lies in its ability to **harmonize** data from different satellites with different resolutions (10m vs 30m) into a unified analysis ready for spectral computation (NDVI, Moisture, etc.).

## 2. Technical Stack
*   **Backend**: Python, FastAPI (High-performance Async API)
*   **Processing Engine**: Google Earth Engine (GEE) Python API
*   **Frontend**: React.js, Leaflet (Map visualization), TailwindCSS
*   **Data Handling**: NumPy, Rasterio, SciPy (for local tensor operations)

---

## 3. Core Logic & Mathematical Explanations

This section explains the "Math" and logic requested, specifically found in `backend/services/gee_fusion_service.py`.

### 3.1. The "Master-Slave" Fusion Logic
The system addresses the challenge of merging **10-meter** resolution (Sentinel) with **30-meter** resolution (Landsat).

*   **Logic**: We treat Sentinel-2 as the **Master** (Reference) and Landsat as the **Slave**.
*   **Math**: The resolution ratio is `30m / 10m = 3`.
    *   This means 1 Landsat pixel covers the same area as a **3x3 grid** of Sentinel pixels.
    *   **Resampling**: To fuse them, we "upsample" Landsat. We split every single 30m Landsat pixel into 9 identical 10m pixels (Nearest Neighbor) or smooth them (Bilinear Interpolation) to align perfectly with the Sentinel grid.

### 3.2. Spectral Normalization (The Scaling Math)
Satellite data comes in "Digital Numbers" (DN) or "Surface Reflectance" (SR) which have different scales. We must normalize them before fusion.

*   **Sentinel-2 Usage**: 
    `Reflectance = Band_Value * 0.0001`
    (Sentinel values typically range 0-10000, so this scales them to 0-1.0 float).

*   **Landsat Usage**:
    `Reflectance = (Band_Value * 0.0000275) - 0.2`
    (Landsat Collection 2 uses this specific linear equation to convert packed integer values to surface reflectance).

### 3.3. Fusion Algorithms
Current implementation uses a **Weighted Average** approach in `fuse_collections_server_side`:

**Code Snippet:**
```python
fused_rgb = s2_rgb.add(l8_rgb).divide(2)
```
**Explanation**:
*   After alignment, we take the Sentinel pixel value ($S$) and Landsat pixel value ($L$) at the exact same coordinate.
*   **Formula**: $Fusion = \frac{S + L}{2}$
*   **Benefit**: This reduces "random noise" (sensor grain) because noise is random, but the signal (the ground) is constant. Averaging two sensors improves the Signal-to-Noise Ratio (SNR).

### 3.4. NDVI (Normalized Difference Vegetation Index)
The code calculates vegetation health using the classic formula:

**Formula**: 
$$NDVI = \frac{NIR - Red}{NIR + Red}$$

**Code Implementation**:
*   **Sentinel**: Uses Band 8 (NIR) and Band 4 (Red).
*   **Landsat**: Uses Band 5 (NIR) and Band 4 (Red).
*   **Fused NDVI**: We calculate NDVI for *both* significantly, then average the result, giving a more robust vegetation reading than any single satellite could provide.

### 3.5. Geographic Windowing (Degree-to-Meter Math)
In `create_geo_window`, the code calculates exactly how much of the earth to grab for a 256x256 pixel image.

**The Math**:
1.  **Target**: 256 pixels * 10 meters/pixel = **2560 meters** total width.
2.  **Latitude Correction**: The earth is a sphere, so 1 degree of Longitude shrinks as you move from Equator to Poles.
3.  **Formula**:
    $$MetersPerDegLon = 111,320 \times \cos(Latitude_{radians})$$

**Why?**: Without this `cos(lat)` correction, the images would look "squashed" or "stretched" depending on if you were in India vs. Europe. This ensures square pixels.

---

## 4. Codebase Tour & Snippet Explanation

### Backend (`backend/`)

#### `main.py`
This is the **Entry Point**. It defines the API URL routes.
*   **`@app.post("/api/fusion/gee-harmonize")`**: The main brain. It receives a bounding box, dates, and returns the fused image URL. It handles the error logic (e.g., if clouds cover the area).
*   **`@app.get("/api/fusion/{fusion_id}/tiles/...")`**: This is a **Tile Server**. It cuts the huge satellite image into tiny squares (tiles) that the map frontend needs to load smoothly as you zoom in/out.

#### `services/gee_fusion_service.py`
The "Engine Room".
*   **`initialize_gee()`**: Authenticates with Google servers.
*   **`get_sentinel_image` / `get_landsat_image`**: Filters the massive global archive to find just the images for your specific location and dates, filtering out cloudy days.
*   **`fuse_collections_server_side`**: 
    *   **Input**: Two raw images (Sentinel, Landsat).
    *   **Action**: Performs the Math described in Section 3 (Scaling, Matching, Averaging).
    *   **Output**: A single "Fused" image ready for display.

### Frontend (`frontend/`)

#### `src/App.jsx`
The **Controller**.
*   Manages State: `aoi` (Area of Interest), `dateRange`, `activeSatellites`.
*   **`handleGEEFusion`**: When you click "Merge Satellite", this function bundles your map selection and sends it to the backend API.
*   **`handleLayerUpdate`**: Updates the map when the backend replies with a new image.

#### `src/components/Sidebar.jsx`
The **Interface**.
*   Contains the buttons "Merge Satellite", "Vegetation (NDVI)", "Moisture".
*   Passes the user's choice (e.g., "ndvi") up to `App.jsx` to trigger the correct fusion mode.

---

## 5. How to Run

1.  **Backend**:
    ```bash
    cd backend
    # Activate virtual environment
    venv_new\Scripts\activate
    # Run server
    # Option A: With auto-reload (development)
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```
    # for production
    uvicorn main:app --host 0.0.0.0 --port 8000

3.  **Frontend**:
    ```bash
    cd frontend
    npm run dev
    ```

4.  **Access**:
    Open `http://localhost:5173` in your browser.
