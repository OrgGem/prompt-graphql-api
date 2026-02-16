# pgql/dashboard/routes/metrics_routes.py
"""Metrics and monitoring endpoints."""

from fastapi import APIRouter
from pgql.monitoring import request_metrics
from pgql.utils.cache import metadata_cache

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("")
async def get_metrics():
    """Get full metrics summary including cache stats."""
    summary = request_metrics.get_summary()
    summary["cache"] = metadata_cache.stats()
    return summary


@router.get("/requests")
async def get_request_history(limit: int = 50):
    """Get recent request history."""
    return {
        "requests": request_metrics.get_recent_requests(limit),
        "total": request_metrics.total_requests,
    }


@router.get("/errors")
async def get_recent_errors(limit: int = 20):
    """Get recent errors."""
    return {
        "errors": request_metrics.get_recent_errors(limit),
        "total_errors": request_metrics.failed_requests,
    }


@router.post("/reset")
async def reset_metrics():
    """Reset all metrics counters."""
    request_metrics.reset()
    return {"message": "Metrics reset successfully"}
