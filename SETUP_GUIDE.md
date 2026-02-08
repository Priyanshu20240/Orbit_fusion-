# Orbiter Fusion - User Setup Guide

## Prerequisites
- **Python 3.9+** (Download from [python.org](https://www.python.org/))
- **Node.js 16+** (Download from [nodejs.org](https://nodejs.org/))
- **Git** (Download from [git-scm.com](https://git-scm.com/))
- Google Earth Engine account (Free, sign up at [earthengine.google.com](https://earthengine.google.com/))

---

## Quick Start (5 minutes)

### 1. Clone the Repository
```bash
git clone https://github.com/Priyanshu20240/Orbit_fusion-.git
cd orbiter-fusion
```

### 2. Start Backend
```bash
cd backend
.\venv_new\Scripts\Activate.ps1   # Windows PowerShell
# OR
python -m venv venv               # Create venv if needed
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Option A: With auto-reload (development)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Option B: Without reload (production)
uvicorn main:app --host 0.0.0.0 --port 8000
```
✅ Backend runs on `http://localhost:8000`

### 3. Start Frontend (in new terminal)
```bash
cd frontend
npm install
npm run dev
```
✅ Frontend runs on `http://localhost:5173`

---

## Detailed Setup Instructions

### Backend Setup

#### Step 1: Navigate to Backend
```bash
cd backend
```

#### Step 2: Create/Activate Virtual Environment
```bash
# Option A: Use existing venv_new
.\venv_new\Scripts\Activate.ps1

# Option B: Create fresh venv
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- **FastAPI** - Web framework
- **Earth Engine API** - Satellite data access
- **NumPy, Scipy** - Data processing
- **Rasterio** - GIS raster handling
- **Pillow** - Image processing

#### Step 4: Configure Google Earth Engine
```bash
earthengine authenticate
```
Follow the browser prompts to authorize your Earth Engine account.

#### Step 5: Run Backend Server
```bash
# Option A: With auto-reload (development)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Option B: Without reload (production)
uvicorn main:app --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

### Frontend Setup

#### Step 1: Navigate to Frontend
```bash
cd frontend
```

#### Step 2: Install Dependencies
```bash
npm install
```

#### Step 3: Run Development Server
```bash
npm run dev
```

Expected output:
```
VITE v4.x.x  ready in 234 ms

➜  Local:   http://localhost:5173/
```

#### Step 4: Open in Browser
Go to: **http://localhost:5173**

---

## Features Available

### Visualization Modes
- 🌈 **True Color (RGB)** - Natural Earth observation
- 🌿 **NDVI** - Vegetation health index
- 🏔️ **SWIR** - Geological/moisture analysis
- 🏢 **NDBI** - Built-up areas detection (NEW)
- 💧 **NDWI** - Water and wetlands (NEW)
- 🌡️ **LST** - Land surface temperature (NEW)
- 👁️ **NIR False Color** - Vegetation emphasis

### Data Sources
- 🌍 **Sentinel-2** (10m resolution, ESA)
- 🌎 **Landsat 8/9** (30m resolution, USGS)
- 🇮🇳 **ISRO Bhuvan** (India-focused layers)

### Analysis Tools
- 📍 **AOI Drawing** - Draw areas of interest on map
- 📊 **Timelapse** - Generate animation of changes over time
- 💾 **Save Dataset** - Export analysis results
- 🔍 **Search by Location** - Find places worldwide

---

## Troubleshooting

### Backend Issues

**Error: "Module not found"**
```bash
# Activate venv and reinstall
.\venv_new\Scripts\Activate.ps1
pip install -r requirements.txt --upgrade
```

**Error: "Google Earth Engine not authenticated"**
```bash
earthengine authenticate
```

**Error: Port 8000 already in use**
```bash
# Kill the process
Get-Process | Where-Object {$_.Name -eq "python"} | Stop-Process -Force

# Or run on different port
python main.py --port 8001
```

### Frontend Issues

**Error: "Node modules not found"**
```bash
rm -r node_modules package-lock.json
npm install
npm run dev
```

**Error: "Cannot connect to backend"**
- Check backend is running: http://localhost:8000/docs
- Check frontend is looking for correct backend URL
- Default: `http://localhost:8000`

---

## Development Tips

### Hot Reload
- **Frontend**: Changes auto-reload (Vite)
- **Backend**: Changes auto-reload (Uvicorn)

### API Documentation
Visit: **http://localhost:8000/docs** (Interactive Swagger UI)

### Common Tasks

#### Add New Satellite
1. Implement in `backend/services/`
2. Add visualization option in `backend/services/gee_fusion_service.py`
3. Add button in `frontend/src/components/Sidebar.jsx`

#### Add New Index
Example (NDWI added):
```python
# Backend
elif visualization == 'ndwi':
    ndwi = img.normalizedDifference(['B8', 'B11'])
    return ndwi.visualize(...)

# Frontend
<button onClick={() => onGEEFusion('ndwi')}>
    💧 NDWI
</button>
```

---

## Project Structure
```
orbiter-fusion/
├── backend/
│   ├── services/
│   │   ├── gee_fusion_service.py    (Core satellite processing)
│   │   ├── sentinel.py              (Sentinel-2 specific)
│   │   ├── landsat.py               (Landsat specific)
│   │   └── ...
│   ├── models/
│   ├── main.py                      (FastAPI app)
│   ├── requirements.txt             (Python dependencies)
│   └── venv_new/                    (Virtual environment)
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Sidebar.jsx          (Analysis controls)
│   │   │   ├── Map.jsx              (Leaflet map)
│   │   │   └── ...
│   │   ├── App.jsx                  (Main component)
│   │   └── index.css                (Styles)
│   ├── package.json                 (Node dependencies)
│   ├── vite.config.js
│   └── node_modules/
│
└── README.md
```

---

## Performance Notes

### Large AOI Processing
- Process areas up to **50 km²** for optimal performance
- Larger areas may timeout (adjust in backend)
- Use smaller date ranges for faster results

### Timelapse Generation
- Default: 50 frames max (prevents timeouts)
- Frame rate: 4 fps
- Output: MP4 video format

### Satellite Data Coverage
- **Sentinel-2**: Global, 10-day revisit, 5% cloud limit
- **Landsat**: Global, 16-day revisit, 30% cloud limit
- **Cloudless scenes**: May require multi-day search

---

## Support & Documentation

- 📖 **API Docs**: http://localhost:8000/docs
- 🐛 **Report Issues**: Create GitHub issue
- 📚 **Technical Docs**: See README.md
- 🗣️ **Discussions**: GitHub Discussions tab

---

## License
[Add your license here]

---

**Last Updated**: February 8, 2026  
**Orbiter Fusion v1.0**
