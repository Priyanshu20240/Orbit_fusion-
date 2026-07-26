# Multi-stage Dockerfile for Orbiter Fusion Platform
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements & install dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend /app/backend

WORKDIR /app/backend

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV ORBITER_GEE_PROJECT=compact-arc-482620-r8

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
