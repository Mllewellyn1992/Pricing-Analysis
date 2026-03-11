"""
Credit Pricing Tool - FastAPI Application
Serves both the API and the static frontend.
"""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from api.rate import routes as rate_routes
from api.pricing import routes as pricing_routes
from api.scrape import routes as scrape_routes
from api.extract import routes as extract_routes
from api.db import routes as db_routes

# Load environment variables from .env file if present
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Credit Pricing Tool",
        description="Rating engine and pricing lookup for credit analysis",
        version="1.0.0"
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount route modules
    app.include_router(rate_routes.router, prefix="/api")
    app.include_router(pricing_routes.router, prefix="/api")
    app.include_router(scrape_routes.router, prefix="/api")
    app.include_router(extract_routes.router, prefix="/api")
    app.include_router(db_routes.router, prefix="/api")

    @app.get("/health")
    def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    # Serve built frontend (production)
    FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

    if FRONTEND_DIST.exists():
        # Mount static assets from built frontend
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

        @app.get("/{path:path}")
        async def serve_spa(path: str):
            """Serve SPA - return index.html for non-API routes."""
            # Don't intercept API routes
            if path.startswith("api/"):
                return {"error": "Not found"}, 404

            file_path = FRONTEND_DIST / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(FRONTEND_DIST / "index.html")
    else:
        # Fallback to static directory for development
        @app.get("/")
        def serve_frontend():
            """Serve the main frontend page from static directory."""
            return FileResponse(STATIC_DIR / "index.html")

    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
