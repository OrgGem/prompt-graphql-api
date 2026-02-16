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


@router.get("/logs/dates")
async def get_log_dates():
    """Get list of available log dates."""
    return {
        "dates": request_metrics.list_available_log_dates()
    }


@router.get("/logs/{date}")
async def get_log_by_date(date: str, limit: int = 100):
    """Get log entries for a specific date (YYYY-MM-DD format)."""
    import re
    from datetime import datetime
    
    # Validate date format to prevent path traversal
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400, 
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    # Validate date is actually valid
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid date")
    
    entries = request_metrics.get_daily_log(date, limit)
    return {
        "date": date,
        "entries": entries,
        "total": len(entries)
    }

