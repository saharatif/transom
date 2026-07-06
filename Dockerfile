# ---- Stage 1: build the Vue frontend ----
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend (serves the built frontend too) ----
FROM python:3.10-slim
WORKDIR /app

# OpenCV runtime libraries (opencv-python needs libGL even headless)
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.1/en_core_web_lg-3.7.1-py3-none-any.whl

# Bake the cross-encoder reranker into the image — otherwise the first
# chat request on a fresh host downloads ~1GB before answering.
RUN python -c "from langchain_community.cross_encoders import HuggingFaceCrossEncoder; HuggingFaceCrossEncoder(model_name='BAAI/bge-reranker-base')"

COPY backend/ backend/
COPY --from=frontend /app/frontend/dist frontend/dist

# SQLite DB + uploaded photos live on a mounted volume so they survive
# restarts/redeploys. The app creates the schema on first boot.
ENV DATABASE_PATH=/data/property_intel.db \
    UPLOADS_DIR=/data/uploads
VOLUME /data

EXPOSE 8000
# ${PORT} so platforms that inject their own port (Railway, Render,
# Heroku-style) work without changes; defaults to 8000 elsewhere.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
