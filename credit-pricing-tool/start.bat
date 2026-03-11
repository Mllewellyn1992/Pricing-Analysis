@echo off
echo ============================================
echo   Credit Pricing Tool - Starting Server
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
echo Installing dependencies...
pip install fastapi "uvicorn[standard]" python-multipart httpx pyyaml anthropic pdfplumber --quiet

echo.
echo Starting server at http://localhost:8000
echo Press Ctrl+C to stop
echo.
echo ============================================
echo   Open http://localhost:8000 in your browser
echo ============================================
echo.

cd /d "%~dp0"
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

pause
