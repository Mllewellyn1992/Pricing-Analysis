# Build stage for frontend
FROM node:22-slim as frontend-builder

WORKDIR /app/frontend

# Copy frontend files (only package.json, skip lockfile for npm compat)
COPY frontend/package.json ./
RUN npm install --legacy-peer-deps

COPY frontend/ ./
RUN npm run build

# Main application stage
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/ api/
COPY engines/ engines/
COPY extraction/ extraction/

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy static directory for fallback
COPY static/ static/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Default PORT for Railway is 8000, but accept PORT environment variable
ENV PORT=8000

# Run the application
# --workers 1: single worker to minimize memory footprint
# --timeout-keep-alive 30: free idle connections sooner
# --limit-max-requests 100: restart worker after 100 requests to prevent memory leaks
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 30 --limit-max-requests 100"]
