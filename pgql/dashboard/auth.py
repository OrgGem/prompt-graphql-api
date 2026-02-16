# pgql/dashboard/auth.py
"""Dashboard authentication middleware."""

import os
import secrets
import logging
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader

logger = logging.getLogger("promptql_dashboard")

# API key header scheme
api_key_header = APIKeyHeader(name="X-Dashboard-Key", auto_error=False)

# The dashboard API key — set via env var or auto-generated on startup
_dashboard_key: str | None = None


def get_dashboard_key() -> str:
    """Get or generate the dashboard API key."""
    global _dashboard_key
    if _dashboard_key is None:
        _dashboard_key = os.getenv("DASHBOARD_API_KEY", "")
        if not _dashboard_key:
            _dashboard_key = secrets.token_urlsafe(32)
            logger.warning("=" * 60)
            logger.warning("No DASHBOARD_API_KEY set — auto-generated:")
            logger.warning(f"  {_dashboard_key}")
            logger.warning("Set DASHBOARD_API_KEY env var to use a fixed key.")
            logger.warning("=" * 60)
    return _dashboard_key


async def verify_api_key(request: Request, api_key: str | None = Depends(api_key_header)):
    """Verify the dashboard API key.
    
    Static assets (/, /static/*) are exempt from auth.
    All /api/* endpoints require the X-Dashboard-Key header.
    """
    path = request.url.path

    # Allow static assets, docs, and health check without auth
    if path in ("/", "/api/docs", "/api/redoc", "/api/openapi.json", "/api/health"):
        return
    if path.startswith("/static/"):
        return

    # API endpoints require auth
    if path.startswith("/api/"):
        expected = get_dashboard_key()
        if api_key != expected:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing X-Dashboard-Key header",
                headers={"WWW-Authenticate": "ApiKey"},
            )
