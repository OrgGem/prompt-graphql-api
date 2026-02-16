# pgql/dashboard/app.py
"""FastAPI dashboard application for PromptQL MCP Server."""

import os
import logging
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from pgql.dashboard.auth import verify_api_key, get_dashboard_key

logger = logging.getLogger("promptql_dashboard")

# Create FastAPI app
app = FastAPI(
    title="PromptQL Admin Dashboard",
    description="Admin dashboard for monitoring and configuring PromptQL MCP Server",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    dependencies=[Depends(verify_api_key)],
)

# CORS — restrict to localhost by default, override with DASHBOARD_CORS_ORIGINS env var
_raw_origins = os.getenv("DASHBOARD_CORS_ORIGINS", "http://localhost:8765,http://127.0.0.1:8765")
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Register API routes
from pgql.dashboard.routes import health_routes, metrics_routes, config_routes, chat_routes, app_routes, external_api_routes, theme_routes

app.include_router(health_routes.router, prefix="/api", tags=["Health"])
app.include_router(metrics_routes.router, prefix="/api", tags=["Metrics"])
app.include_router(config_routes.router, prefix="/api", tags=["Configuration"])
app.include_router(chat_routes.router, prefix="/api", tags=["Chat"])
app.include_router(app_routes.router, prefix="/api", tags=["Apps"])
app.include_router(external_api_routes.router, prefix="/api", tags=["External API v1"])
app.include_router(theme_routes.router, prefix="/api", tags=["Theme"])

logger.info("Dashboard app created successfully")


@app.get("/", include_in_schema=False)
async def root():
    """Serve the dashboard SPA."""
    return FileResponse(str(static_dir / "index.html"))


@app.on_event("startup")
async def startup_event():
    """Log dashboard startup info."""
    key = get_dashboard_key()
    logger.info("Dashboard API key initialized")
    logger.info(f"  Use header: X-Dashboard-Key: {key}")
