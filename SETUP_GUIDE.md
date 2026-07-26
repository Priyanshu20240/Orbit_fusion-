# 🛠️ Orbiter Fusion - Complete Setup & Deployment Guide

This guide details setup instructions for running **Orbiter Fusion** locally, via Docker containers, and on Vercel/Render production platforms.

---

## 📋 Prerequisites
- **Python 3.10+**
- **Node.js 18+** & **npm**
- **Docker & Docker Compose** (Optional, for 1-command deployment)
- **Google Earth Engine Cloud Project ID** ([earthengine.google.com](https://earthengine.google.com/))
- **Mistral AI API Key** ([console.mistral.ai](https://console.mistral.ai/))

---

## ⚡ 1. Fast Track (1-Command Docker Setup)

The fastest way to launch the entire stack locally:

```bash
# Clone the repository
git clone https://github.com/Priyanshu20240/Orbit_fusion-.git
cd orbiter-fusion

# Launch with Docker Compose
docker compose up --build
```

Access the app at **`http://localhost:5173`**!

---

## 🔧 2. Manual Local Setup

### A. Backend Setup (FastAPI + Google Earth Engine)

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # Windows PowerShell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Create environment file `backend/.env`:
   ```env
   ORBITER_GEE_PROJECT=compact-arc-482620-r8
   MISTRAL_API_KEY=your-mistral-api-key
   ORBITER_CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
   ```

5. Authenticate with Google Earth Engine (if running for the first time):
   ```bash
   earthengine authenticate
   ```

6. Start the FastAPI server:
   ```bash
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   ✅ API running on `http://127.0.0.1:8000`

---

### B. Frontend Setup (React + Vite + Leaflet)

1. Open a new terminal and navigate to `frontend`:
   ```bash
   cd frontend
   ```

2. Install Node dependencies:
   ```bash
   npm install
   ```

3. Create frontend `.env` file (optional for custom backend ports):
   ```env
   VITE_API_URL=http://localhost:8000
   ```

4. Start Vite development server:
   ```bash
   npm run dev
   ```
   ✅ Web UI running on `http://localhost:5173`

---

## 🌐 3. Production Deployment (Vercel + Render)

For step-by-step instructions on deploying the frontend to **Vercel Edge CDN** and the backend container to **Render / Railway**, refer to [deployment_guide.md](file:///C:/Users/ppgku/.gemini/antigravity/brain/9a03477b-8e11-4406-8195-8213f067b40c/deployment_guide.md)!

---

## 🧪 4. Running Verification Tests

### Backend Unit & Integration Tests:
```bash
cd backend
pytest
```

### Frontend E2E Playwright Browser Tests:
```bash
cd frontend
npx playwright test
```
