# pgql/dashboard/routes/health_routes.py
"""Health check endpoints."""

from fastapi import APIRouter
from pgql.monitoring import request_metrics

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "uptime_seconds": round(request_metrics.uptime_seconds, 1),
        "version": "0.1.0",
    }
