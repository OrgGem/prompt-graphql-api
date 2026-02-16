# pgql/dashboard/routes/external_api_routes.py
"""External API v1 — endpoints for apps authenticated via X-App-Api-Key.

These endpoints are separate from the admin dashboard API.
External consumers use their App API key (pgql_xxx) to:
  - Query Hasura via natural language
  - List their allowed tables
  - Check their app info
"""

import logging
import time
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from pgql.apps import app_manager
from pgql.tools.config_tools import config
from pgql.api.hasura_ce_client import HasuraCEClient
from pgql.api.hasura_query_planner import plan_prompt_to_graphql, synthesize_answer
from pgql.security import validate_message, rate_limiter
from pgql.monitoring import request_metrics

logger = logging.getLogger("promptql_dashboard")

router = APIRouter(prefix="/v1", tags=["External API v1"])


# --- Auth helper ---

def _resolve_app(api_key: Optional[str]) -> dict:
    """Resolve and validate app from API key."""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-App-Api-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    app = app_manager.resolve_by_api_key(api_key)
    if not app:
        raise HTTPException(
            status_code=401,
            detail="Invalid or inactive API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return app


# --- Request Models ---

class QueryRequest(BaseModel):
    """Natural language query request."""
    prompt: str
    max_limit: int = 100


class GraphQLRequest(BaseModel):
    """Raw GraphQL query request."""
    query: str
    variables: Optional[dict] = None


# --- Endpoints ---

@router.get("/me")
async def get_app_info(x_app_api_key: Optional[str] = Header(None)):
    """Get current app info — identity, role, and allowed tables.

    Returns the app's configuration without the API key.
    Use this to verify your credentials and check permissions.
    """
    app = _resolve_app(x_app_api_key)
    return {
        "app_id": app.get("app_id"),
        "role": app.get("role"),
        "allowed_tables": app.get("allowed_tables", []),
        "description": app.get("description", ""),
        "active": app.get("active", True),
    }


@router.get("/schema")
async def get_schema(x_app_api_key: Optional[str] = Header(None)):
    """Get available tables for this app.

    Returns only the tables the app is allowed to access.
    If no table restrictions are set, returns all cached tables.
    """
    app = _resolve_app(x_app_api_key)
    allowed = app.get("allowed_tables", [])

    # If app has table restrictions, return only those
    if allowed:
        return {
            "tables": allowed,
            "total": len(allowed),
            "restricted": True,
        }

    # Otherwise return all cached tables
    cached = app_manager.get_cached_tables()
    tables = cached.get("tables", [])
    return {
        "tables": tables,
        "total": len(tables),
        "restricted": False,
    }


@router.post("/query")
async def query(req: QueryRequest, x_app_api_key: Optional[str] = Header(None)):
    """Execute a natural language query against Hasura.

    Converts the prompt to GraphQL, executes it, and returns
    a synthesized answer. Access is filtered by app permissions.
    """
    app = _resolve_app(x_app_api_key)

    # Rate limiting
    if not rate_limiter.is_allowed():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Validate prompt
    try:
        prompt = validate_message(req.prompt)
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=f"Invalid prompt: {str(e)}")

    # Get Hasura client
    endpoint = config.get("hasura_graphql_endpoint")
    secret = config.get("hasura_admin_secret")
    if not endpoint:
        raise HTTPException(
            status_code=503,
            detail="Hasura endpoint not configured on this server",
        )

    _start = time.time()
    try:
        hasura = HasuraCEClient(graphql_endpoint=endpoint, admin_secret=secret)
        metadata = hasura.export_metadata()

        # Apply app permissions
        allowed_tables = app.get("allowed_tables") or None
        app_role = app.get("role", "read")

        plan = plan_prompt_to_graphql(
            prompt=prompt,
            metadata=metadata,
            max_limit=req.max_limit,
            allowed_tables=allowed_tables,
        )

        if not plan.get("success"):
            request_metrics.record_request("v1_query", time.time() - _start, False, plan.get("error", "Plan failed"))
            raise HTTPException(status_code=400, detail=plan.get("error", "Could not create query plan"))

        # Check write permission
        query_text = plan["query"].strip().lower()
        if query_text.startswith("mutation") and app_role != "write":
            request_metrics.record_request("v1_query", time.time() - _start, False, "Write denied")
            raise HTTPException(
                status_code=403,
                detail="Write access denied — this app has read-only permission",
            )

        graphql_result = hasura.execute_graphql(query=plan["query"])
        answer = synthesize_answer(prompt=prompt, selected_table=plan["selected_table"], graphql_result=graphql_result)

        request_metrics.record_request("v1_query", time.time() - _start, True)
        return {
            "success": True,
            "answer": answer,
            "query": plan["query"],
            "selected_table": plan.get("selected_table"),
            "data": graphql_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"v1/query error: {e}")
        request_metrics.record_request("v1_query", time.time() - _start, False, str(e))
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")
