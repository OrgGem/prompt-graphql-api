# pgql/dashboard/routes/external_api_routes.py
"""External API v1 — endpoints for apps authenticated via X-App-Api-Key.

These endpoints are separate from the admin dashboard API.
External consumers use their App API key (pgql_xxx) to:
  - Query Hasura via natural language (LLM-powered)
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
from pgql.api.schema_extractor import extract_schema
from pgql.api.query_generator import (
    generate_graphql_query,
    validate_query,
    summarize_results,
)
from pgql.api.llm_client import LLMClient
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


def _build_llm_client() -> Optional[LLMClient]:
    """Try to build LLM client from config. Returns None if not configured."""
    try:
        # Build directly instead of importing from chat_routes to avoid circular deps
        api_key = config.get("llm_api_key") or ""
        base_url = config.get("llm_base_url")
        if not base_url:
            return None
        model = config.get("llm_model") or "gpt-3.5-turbo"
        try:
            temperature = float(config.get("llm_temperature") or "0.7")
        except (ValueError, TypeError):
            temperature = 0.7
        try:
            max_tokens = int(config.get("llm_max_tokens") or "4096")
        except (ValueError, TypeError):
            max_tokens = 4096
        return LLMClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        logger.debug(f"LLM client not available: {e}")
        return None


# --- Request Models ---

class QueryRequest(BaseModel):
    """Natural language query request."""
    prompt: str
    max_limit: int = 100



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

    Uses the LLM-powered 3-phase pipeline (same as /api/chat):
    1. Extract schema via introspection
    2. LLM generates GraphQL query from question + schema
    3. Execute on Hasura, LLM summarizes results

    Falls back to rule-based count-aggregate if LLM is not configured.
    """
    app = _resolve_app(x_app_api_key)

    # Rate limiting (per-app isolation)
    if not rate_limiter.is_allowed(client_id=app.get("app_id", "default")):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Validate prompt
    try:
        prompt = validate_message(req.prompt)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid prompt: {str(e)}")

    # Get Hasura client
    endpoint = config.get("hasura_graphql_endpoint")
    secret = config.get("hasura_admin_secret")
    if not endpoint:
        raise HTTPException(
            status_code=503,
            detail="Hasura endpoint not configured on this server",
        )

    allowed_tables = app.get("allowed_tables") or None
    app_role = app.get("role", "read")
    _start = time.time()

    try:
        hasura = HasuraCEClient(graphql_endpoint=endpoint, admin_secret=secret)

        # Try LLM-powered pipeline first
        llm_client = _build_llm_client()
        if llm_client:
            result = _query_with_llm(
                llm_client, hasura, prompt, allowed_tables, app_role, req.max_limit,
            )
            if result:
                request_metrics.record_request("v1_query", time.time() - _start, True)
                return result

        # Fallback: rule-based count-aggregate (no LLM required)
        result = _query_rule_based(hasura, prompt, allowed_tables, app_role, req.max_limit)
        request_metrics.record_request("v1_query", time.time() - _start, True)
        return result

    except HTTPException:
        raise
    except ValueError as e:
        request_metrics.record_request("v1_query", time.time() - _start, False, str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        request_metrics.record_request("v1_query", time.time() - _start, False, str(e))
        raise HTTPException(status_code=503, detail=f"Hasura connection error: {str(e)}")
    except Exception as e:
        logger.error(f"v1/query error: {e}", exc_info=True)
        request_metrics.record_request("v1_query", time.time() - _start, False, str(e))
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


# --- Internal helpers ---

def _query_with_llm(
    llm_client: LLMClient,
    hasura: HasuraCEClient,
    prompt: str,
    allowed_tables: Optional[list],
    role: str,
    max_limit: int,
) -> Optional[dict]:
    """LLM-powered query pipeline (3 phases).

    Returns result dict on success, None to signal fallback.
    """
    try:
        # Phase 1: Extract schema
        schema_dsl = extract_schema(hasura, allowed_tables=allowed_tables)
        if not schema_dsl or schema_dsl.startswith("No "):
            logger.warning("Schema extraction returned empty — falling back")
            return None

        # Phase 2: Generate query
        gen_result = generate_graphql_query(llm_client, schema_dsl, prompt)
        if not gen_result.get("success"):
            logger.info(f"LLM query gen failed: {gen_result.get('error')}")
            return None

        query_str = gen_result["query"]

        # Validate
        validation = validate_query(query_str, role=role, allowed_tables=allowed_tables)
        if not validation.get("valid"):
            logger.warning(f"Query validation failed: {validation.get('reason')}")
            return None

        # Phase 3: Execute
        graphql_result = hasura.execute_graphql(query=query_str)
        if graphql_result.get("errors"):
            logger.warning(f"GraphQL exec errors: {graphql_result['errors']}")
            return None

        data = graphql_result.get("data", {})

        # Summarize
        summary_result = summarize_results(llm_client, prompt, query_str, data)
        answer = summary_result.get("summary", str(data))

        return {
            "success": True,
            "answer": answer,
            "query": query_str,
            "pipeline": "llm",
            "data": data,
        }

    except Exception as e:
        logger.warning(f"LLM pipeline error, falling back: {e}")
        return None


def _query_rule_based(
    hasura: HasuraCEClient,
    prompt: str,
    allowed_tables: Optional[list],
    role: str,
    max_limit: int,
) -> dict:
    """Rule-based fallback: keyword match → count_aggregate query."""
    from pgql.api.hasura_query_planner import plan_prompt_to_graphql, synthesize_answer

    metadata = hasura.export_metadata()
    plan = plan_prompt_to_graphql(
        prompt=prompt,
        metadata=metadata,
        max_limit=max_limit,
        allowed_tables=allowed_tables,
    )

    if not plan.get("success"):
        raise ValueError(plan.get("error", "Could not create query plan"))

    # Mutation check
    query_text = plan["query"].strip().lower()
    if query_text.startswith("mutation") and role != "write":
        raise HTTPException(
            status_code=403,
            detail="Write access denied — this app has read-only permission",
        )

    graphql_result = hasura.execute_graphql(query=plan["query"])
    answer = synthesize_answer(prompt=prompt, selected_table=plan["selected_table"], graphql_result=graphql_result)

    return {
        "success": True,
        "answer": answer,
        "query": plan["query"],
        "selected_table": plan.get("selected_table"),
        "pipeline": "rule_based",
        "data": graphql_result,
    }
