# Installation & Setup Guide

## Prerequisites
- Python 3.9+
- Node.js 16+ and npm
- Google Earth Engine account (for satellite data fusion)

---

## Backend Setup

### 1. Create Virtual Environment
```bash
cd backend
python -m venv venv
```

### 2. Activate Virtual Environment

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Google Earth Engine
This is **required** for satellite data fusion:
```bash
earthengine authenticate
```

Follow the browser prompt to authorize. Credentials will be saved locally.

### 5. Create Environment File
```bash
cp .env.example .env
```

(Optional) Edit `.env` for custom settings.

### 6. Create Required Directories
```bash
mkdir -p static/fusion datasets cache
```

### 7. Run Backend Server
**Development with auto-reload:**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Production:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Backend will be available at: **http://localhost:8000**

### 8. Verify Backend Health
Open in browser:
```
http://localhost:8000/api/health/detailed
```

---

## Frontend Setup

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Create Environment File
```bash
cp .env.example .env
```

(Optional) Edit `.env` for custom API URL or other settings.

### 3. Install Tailwind CSS
```bash
npm install -D tailwindcss postcss autoprefixer
```

### 4. Run Development Server
```bash
npm run dev
```

Frontend will be available at: **http://localhost:5173**

### 5. Build for Production
```bash
npm run build
```

---

## Full Stack Testing

### Open Both Servers:

**Terminal 1 - Backend:**
```bash
cd backend
.\venv\Scripts\Activate.ps1  # or: source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

### Access Application:
1. Open **http://localhost:5173** in your browser
2. Draw an area on the map
3. Select date range and satellites
4. Click "Search" to find satellite data
5. Click "Merge Satellite" or visualization buttons

---

## Troubleshooting

### Backend Issues:

**Error: `earthengine-api` import failed**
```bash
pip install --upgrade earthengine-api
earthengine authenticate
```

**Error: GDAL/Rasterio issues on Windows**
- This is handled automatically in `main.py`
- Do not install `gdal` directly via pip on Windows unless you have full GDAL build tools.
- Use a supported Python version for prebuilt geospatial wheels (recommended: Python 3.11 or 3.12).
- Recreate the venv and reinstall:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Error: Port 8000 already in use**
```bash
uvicorn main:app --host 0.0.0.0 --port 8001  # Use different port
```

### Frontend Issues:

**Error: API requests failing**
- Verify backend is running on port 8000
- Check vite.config.js proxy settings
- Check browser console (F12) for details

**Error: npm install fails**
```bash
npm cache clean --force
npm install
```

**Tailwind styles not loading**
```bash
npm install -D tailwindcss postcss autoprefixer
npm run dev
```

---

## Environment Variables

### Backend (.env)
```env
GEE_CREDENTIALS_PATH=~/.config/earthengine/credentials.json
HOST=0.0.0.0
PORT=8000
DEBUG=True
LOG_LEVEL=INFO
DATASETS_FOLDER=./datasets
CACHE_FOLDER=./cache
MAX_CLOUD_COVER=20
```

### Frontend (.env)
```env
VITE_API_URL=http://localhost:8000
VITE_DEBUG=true
```

---

## API Documentation

Once backend is running, visit:
- **API Docs (Swagger UI):** http://localhost:8000/docs
- **Alternative Docs (ReDoc):** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/api/health/detailed

---

## Performance Tips

1. **Backend**: Use production mode for better performance
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

2. **Frontend**: Build and serve static files
   ```bash
   npm run build
   npm run preview  # Preview production build
   ```

3. **Google Earth Engine**:
   - Limit cloud cover to < 20% for faster results
   - Use smaller window sizes for quicker processing
   - Cache results to avoid re-downloading

---

## Support & Documentation

- **GitHub:** https://github.com/Priyanshu20240/Orbit_fusion-
- **Technical Docs:** See README.md for architecture details
- **Performance Guide:** See PERFORMANCE_OPTIMIZATIONS.md
