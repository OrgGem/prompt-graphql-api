# pgql/dashboard/routes/app_routes.py
"""REST API routes for multi-app access control management."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from pgql.apps import app_manager
from pgql.apps.schema_loader import load_hasura_tables
from pgql.tools.config_tools import config

logger = logging.getLogger("promptql_dashboard")

router = APIRouter(prefix="/apps", tags=["Apps"])


# ── Request Models ───────────────────────────────────────────

class CreateAppRequest(BaseModel):
    app_id: str
    description: str = ""
    allowed_tables: list[str] = []
    role: str = "read"


class UpdateAppRequest(BaseModel):
    description: Optional[str] = None
    allowed_tables: Optional[list[str]] = None
    role: Optional[str] = None
    active: Optional[bool] = None


# ── App CRUD Endpoints ───────────────────────────────────────

@router.get("")
async def list_apps(page: int = 1, size: int = 100):
    """List all apps with masked API keys. Supports pagination."""
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if size < 1 or size > 1000:
        raise HTTPException(status_code=400, detail="size must be between 1 and 1000")
    
    all_apps = app_manager.list_apps()
    total = len(all_apps)
    
    # Calculate pagination
    start = (page - 1) * size
    end = start + size
    paginated_apps = all_apps[start:end]
    
    return {
        "apps": paginated_apps,
        "pagination": {
            "page": page,
            "size": size,
            "total": total,
            "total_pages": (total + size - 1) // size  # Ceiling division
        }
    }


@router.post("")
async def create_app(req: CreateAppRequest):
    """Create a new app with its own API key and table permissions."""
    try:
        app = app_manager.create_app(
            app_id=req.app_id,
            description=req.description,
            allowed_tables=req.allowed_tables,
            role=req.role,
        )
        return {"success": True, "app": app}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/schema/tables")
async def get_schema_tables():
    """Get available tables from cached Hasura metadata."""
    cached = app_manager.get_cached_tables()
    return {
        "tables": cached.get("tables", []),
        "last_loaded": cached.get("last_loaded"),
        "source": "cache",
    }


@router.post("/schema/reload")
async def reload_schema():
    """Reload tracked tables from Hasura metadata."""
    endpoint = config.get("hasura_graphql_endpoint")
    if not endpoint:
        raise HTTPException(
            status_code=400,
            detail="Hasura GraphQL endpoint not configured. Set it in Configuration tab first.",
        )
    secret = config.get("hasura_admin_secret")

    try:
        tables = load_hasura_tables(
            graphql_endpoint=endpoint,
            admin_secret=secret,
        )
        app_manager.update_schema_cache(tables)
        return {
            "success": True,
            "tables": tables,
            "total": len(tables),
            "message": f"Loaded {len(tables)} tables from Hasura",
        }
    except Exception as e:
        logger.error(f"Schema reload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load schema: {e}")


@router.get("/{app_id}")
async def get_app(app_id: str):
    """Get details of a specific app."""
    app = app_manager.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")
    return {"app": app}


@router.put("/{app_id}")
async def update_app(app_id: str, req: UpdateAppRequest):
    """Update an app's configuration."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        app = app_manager.update_app(app_id, **updates)
        return {"success": True, "app": app}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{app_id}")
async def delete_app(app_id: str):
    """Delete an app."""
    if not app_manager.delete_app(app_id):
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")
    return {"success": True, "message": f"App '{app_id}' deleted"}


@router.post("/{app_id}/regenerate-key")
async def regenerate_key(app_id: str):
    """Regenerate the API key for an app."""
    try:
        new_key = app_manager.regenerate_key(app_id)
        return {"success": True, "api_key": new_key, "app_id": app_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
