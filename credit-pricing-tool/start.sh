#!/bin/bash
echo "============================================"
echo "  Credit Pricing Tool - Starting Server"
echo "============================================"
echo ""

# Install deps
pip install fastapi "uvicorn[standard]" python-multipart httpx pyyaml anthropic pdfplumber --quiet 2>/dev/null

echo "Starting server at http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

cd "$(dirname "$0")"
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
