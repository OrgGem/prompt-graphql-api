# pgql/dashboard/routes/chat_routes.py
"""Chat endpoint supporting both PromptQL and direct LLM modes."""

import logging
import time
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from pgql.tools.config_tools import config
from pgql.api.promptql_client import PromptQLClient
from pgql.api.llm_client import LLMClient
from pgql.monitoring import request_metrics

logger = logging.getLogger("promptql_dashboard")

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str
    system_instructions: Optional[str] = None
    mode: str = "auto"  # "auto", "promptql", "llm"
    app_id: Optional[str] = None  # Optional app ID for testing with app credentials



def _resolve_provider_config(provider_id: str) -> dict:
    """Resolve LLM config from a provider ID (e.g. 'ollama', 'custom:open-router').

    Returns dict with api_key, base_url, model, temperature, max_tokens.
    """
    from pgql.dashboard.routes.config_routes import KNOWN_LLM_PROVIDERS

    is_known = provider_id in KNOWN_LLM_PROVIDERS

    if is_known:
        return {
            "api_key": config.get(f"{provider_id}_api_key") or "",
            "base_url": config.config.get(f"{provider_id}_base_url", ""),
            "model": config.config.get(f"{provider_id}_model", ""),
            "temperature": config.config.get(f"{provider_id}_temperature", "0.7"),
            "max_tokens": config.config.get(f"{provider_id}_max_tokens", "4096"),
        }
    else:
        # Custom provider: "custom:label" -> label
        label = provider_id.replace("custom:", "")
        return {
            "api_key": config.get(f"custom_api_key_{label}") or "",
            "base_url": config.config.get(f"custom_base_url_{label}", ""),
            "model": config.config.get(f"custom_model_{label}", ""),
            "temperature": config.config.get(f"custom_temperature_{label}", "0.7"),
            "max_tokens": config.config.get(f"custom_max_tokens_{label}", "4096"),
        }


def _build_llm_client() -> LLMClient:
    """Build an OpenAI-compatible LLM client from config.

    Resolution order:
    1. If llm_provider_id is set, resolve from provider-specific config keys
    2. Otherwise fall back to generic llm_* config keys
    """
    provider_id = config.get("llm_provider_id") or ""

    if provider_id:
        # Resolve from provider-specific config
        pconf = _resolve_provider_config(provider_id)
        llm_api_key = pconf["api_key"]
        llm_base_url = pconf["base_url"]
        model = pconf["model"] or "gpt-3.5-turbo"
        temp_str = pconf["temperature"]
        max_str = pconf["max_tokens"]
        logger.info(f"Using LLM provider '{provider_id}': base_url={llm_base_url}, model={model}")
    else:
        # Fallback to generic llm_* keys
        llm_api_key = config.get("llm_api_key") or ""
        llm_base_url = config.get("llm_base_url")
        model = config.get("llm_model") or "gpt-3.5-turbo"
        temp_str = config.get("llm_temperature") or "0.7"
        max_str = config.get("llm_max_tokens") or "4096"

    if not llm_base_url:
        raise ValueError("LLM Base URL must be configured. Add a provider in the API Keys tab and activate it.")

    try:
        temperature = float(temp_str or "0.7")
    except (ValueError, TypeError):
        temperature = 0.7
    try:
        max_tokens = int(max_str or "4096")
    except (ValueError, TypeError):
        max_tokens = 4096

    return LLMClient(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _resolve_mode(mode: str) -> str:
    """Resolve 'auto' mode to 'llm' or 'promptql'."""
    if mode == "llm":
        return "llm"
    if mode == "promptql":
        return "promptql"
    # auto: prefer LLM if configured, else PromptQL
    if config.get("llm_provider_id"):
        return "llm"
    if config.get("llm_api_key") and config.get("llm_base_url"):
        return "llm"
    if config.is_configured():
        return "promptql"
    return "none"


@router.post("")
async def chat(req: ChatRequest):
    """Send a chat message using PromptQL or direct LLM."""
    start_time = time.time()
    success = False
    error_msg = None
    
    try:
        if not req.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty.")

        resolved = _resolve_mode(req.mode)

        if resolved == "none":
            raise HTTPException(
                status_code=400,
                detail="No LLM or PromptQL configured. Set up in Configuration tab."
            )

        if resolved == "llm":
            result = await _chat_llm(req)
        else:
            result = await _chat_promptql(req)
        
        # Check if the operation was successful
        success = result.get("success", False)
        if not success:
            error_msg = result.get("error", "Unknown error")
        
        return result
    
    except HTTPException:
        # Let FastAPI handle HTTP exceptions
        raise
    except (ValueError, requests.RequestException) as e:
        # Expected errors (config issues, network problems)
        error_msg = str(e)
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # Unexpected errors - log with stack trace
        error_msg = str(e)
        logger.critical(f"Unexpected chat error: {e}", exc_info=True)
        raise
    finally:
        # Always record metrics
        duration = time.time() - start_time
        request_metrics.record_request(
            tool_name="chat_request",
            duration=duration,
            success=success,
            error_message=error_msg
        )


def _build_hasura_context(app_context: dict, max_tables: int = 3, sample_limit: int = 5) -> str:
    """Build a data context string from Hasura CE for LLM system prompt.

    Connects to Hasura CE, fetches schema and sample data for the app's
    allowed tables, and returns a formatted context string.
    """
    from pgql.api.hasura_ce_client import HasuraCEClient
    import json

    endpoint = config.get("hasura_graphql_endpoint")
    secret = config.get("hasura_admin_secret")
    if not endpoint:
        return ""

    try:
        hasura = HasuraCEClient(graphql_endpoint=endpoint, admin_secret=secret)
        allowed_tables = app_context.get("allowed_tables") or None
        role = app_context.get("role", "read")

        # Get tracked tables filtered by app's allowed_tables
        tables = hasura.get_tracked_tables(allowed_tables=allowed_tables)
        if not tables:
            return "No accessible tables found in the database."

        # Limit tables to avoid token overflow
        tables_to_query = tables[:max_tables]

        context_parts = []
        context_parts.append(f"## Database Context (Hasura CE)")
        context_parts.append(f"Available tables: {', '.join(tables)}")
        context_parts.append(f"App role: {role} ({'read-only — do NOT suggest mutations' if role == 'read' else 'read/write'})")
        context_parts.append("")

        for table_name in tables_to_query:
            sample = hasura.query_sample_rows(table_name, limit=sample_limit, role=None)
            columns = sample.get("columns", [])
            rows = sample.get("rows", [])

            if columns:
                context_parts.append(f"### Table: {table_name}")
                context_parts.append(f"Columns: {', '.join(columns)}")
                if rows:
                    context_parts.append(f"Sample data ({len(rows)} rows):")
                    context_parts.append("```json")
                    context_parts.append(json.dumps(rows, indent=2, default=str, ensure_ascii=False))
                    context_parts.append("```")
                else:
                    context_parts.append("(No data rows)")
                context_parts.append("")

        logger.info(f"Built Hasura context: {len(tables)} tables, queried {len(tables_to_query)}")
        return "\n".join(context_parts)
    except requests.RequestException as e:
        logger.error(f"Hasura connection error building context: {e}")
        return f"(Failed to connect to Hasura: {e})"
    except (KeyError, ValueError) as e:
        logger.error(f"Data error building Hasura context: {e}")
        return f"(Failed to parse database context: {e})"


async def _chat_llm(req: ChatRequest) -> dict:
    """Chat via direct OpenAI-compatible API, with optional Hasura CE query loop.

    When app_id is provided, uses a 3-phase approach:
    1. Extract schema from Hasura CE via introspection
    2. LLM generates a GraphQL query from user question + schema
    3. Execute query on Hasura CE, then LLM summarizes results

    Falls back to sample-data mode if query generation fails.
    """
    try:
        client = _build_llm_client()

        # No app_id → simple LLM chat without data context
        if not req.app_id:
            return _simple_llm_chat(client, req)

        # Resolve app context
        from pgql.apps import app_manager
        app = app_manager.get_app(req.app_id)
        if not app:
            return {"success": False, "mode": "llm", "error": f"App '{req.app_id}' not found"}
        if not app.get("active", True):
            return {"success": False, "mode": "llm", "error": f"App '{req.app_id}' is disabled"}

        logger.info(f"LLM chat with app '{req.app_id}', role={app.get('role')}, tables={app.get('allowed_tables')}")

        # Try 3-phase query loop first
        query_result = _query_loop(client, req, app)
        if query_result:
            return query_result

        # Fallback: inject sample data context into prompt
        logger.info("Query loop failed or unavailable, falling back to sample data mode")
        return _fallback_sample_chat(client, req, app)

    except requests.RequestException as e:
        logger.error(f"LLM connection error: {e}")
        return {"success": False, "mode": "llm", "error": f"LLM connection error: {e}"}
    except ValueError as e:
        logger.error(f"LLM config error: {e}")
        return {"success": False, "mode": "llm", "error": str(e)}


def _simple_llm_chat(client, req: ChatRequest) -> dict:
    """Simple LLM chat without data context."""
    result = client.chat(
        message=req.message,
        system_instructions=req.system_instructions or None,
    )
    if not result.get("success"):
        return {"success": False, "mode": "llm", "error": result.get("error", "Unknown LLM error")}
    return {
        "success": True,
        "mode": "llm",
        "content": result.get("content", ""),
        "model": result.get("model", ""),
        "usage": result.get("usage", {}),
    }


def _query_loop(client, req: ChatRequest, app: dict) -> dict | None:
    """Execute the 3-phase query generation loop.

    Returns response dict on success, None to signal fallback.
    """
    from pgql.api.hasura_ce_client import HasuraCEClient
    from pgql.api.schema_extractor import extract_schema
    from pgql.api.query_generator import generate_graphql_query, validate_query, summarize_results

    endpoint = config.get("hasura_graphql_endpoint")
    secret = config.get("hasura_admin_secret")
    if not endpoint:
        return None

    try:
        hasura = HasuraCEClient(graphql_endpoint=endpoint, admin_secret=secret)
        allowed_tables = app.get("allowed_tables") or None
        role = app.get("role", "read")
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # Phase 1: Extract schema
        schema_dsl = extract_schema(hasura, allowed_tables=allowed_tables)
        if not schema_dsl or schema_dsl.startswith("No "):
            logger.warning(f"Schema extraction returned empty: {schema_dsl}")
            return None

        # Phase 2: LLM generates GraphQL query
        gen_result = generate_graphql_query(client, schema_dsl, req.message)
        if not gen_result.get("success"):
            logger.warning(f"Query generation failed: {gen_result.get('error')}")
            return None

        query = gen_result["query"]
        _merge_usage(total_usage, gen_result.get("usage", {}))

        # Validate the generated query
        validation = validate_query(query, role=role, allowed_tables=allowed_tables)
        if not validation.get("valid"):
            logger.warning(f"Generated query failed validation: {validation.get('reason')}")
            return None

        # Phase 3: Execute query on Hasura CE
        logger.info(f"Executing generated query: {query[:200]}")
        gql_result = hasura.execute_graphql(query, role=None)

        # Check for GraphQL errors
        if gql_result.get("errors"):
            error_msg = gql_result["errors"][0].get("message", "Unknown GraphQL error")
            logger.warning(f"GraphQL execution error: {error_msg}")
            return None

        # Summarize results with LLM
        summary = summarize_results(client, req.message, query, gql_result)
        _merge_usage(total_usage, summary.get("usage", {}))

        return {
            "success": True,
            "mode": "llm",
            "content": summary.get("summary", ""),
            "model": gen_result.get("raw_response", ""),
            "usage": total_usage,
            "app_id": req.app_id,
            "query_generated": query,
            "query_results": gql_result.get("data"),
        }

    except requests.RequestException as e:
        logger.warning(f"Hasura connection error in query loop: {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.warning(f"Query loop error: {e}")
        return None


def _fallback_sample_chat(client, req: ChatRequest, app: dict) -> dict:
    """Fallback: inject sample data into prompt and chat."""
    system_instructions = req.system_instructions or ""
    hasura_context = _build_hasura_context(app)
    if hasura_context:
        data_preamble = (
            "You are a data assistant connected to a database via Hasura GraphQL.\n"
            "Use the following database context to answer the user's question.\n"
            "Answer based on the actual data provided. If the data is insufficient, say so.\n\n"
        )
        system_instructions = data_preamble + hasura_context + "\n\n" + system_instructions

    result = client.chat(
        message=req.message,
        system_instructions=system_instructions.strip() or None,
    )

    if not result.get("success"):
        return {"success": False, "mode": "llm", "error": result.get("error", "Unknown LLM error")}

    return {
        "success": True,
        "mode": "llm",
        "content": result.get("content", ""),
        "model": result.get("model", ""),
        "usage": result.get("usage", {}),
        "app_id": req.app_id,
    }


def _merge_usage(total: dict, new: dict):
    """Merge LLM usage counters."""
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        total[key] = total.get(key, 0) + new.get(key, 0)


async def _chat_promptql(req: ChatRequest) -> dict:
    """Chat via PromptQL thread API."""
    # If app_id is provided, use app's credentials instead of default config
    if req.app_id:
        from pgql.apps import app_manager
        app = app_manager.get_app(req.app_id)
        if not app:
            return {
                "success": False,
                "mode": "promptql",
                "error": f"App '{req.app_id}' not found"
            }
        if not app.get("active", True):
            return {
                "success": False,
                "mode": "promptql",
                "error": f"App '{req.app_id}' is disabled"
            }
        # Get app with unmasked API key via public method
        app_full = app_manager.get_app_with_key(req.app_id)
        if not app_full:
            return {
                "success": False,
                "mode": "promptql",
                "error": f"Cannot retrieve app credentials for '{req.app_id}'"
            }
        api_key = app_full.get("api_key")
        logger.info(f"Chat using app '{req.app_id}' with role={app_full.get('role')}")
    else:
        # Use default config
        if not config.is_configured():
            raise HTTPException(
                status_code=400,
                detail="PromptQL not configured. Set API Key and Base URL first."
            )
        api_key = config.get("api_key")

    try:
        base_url = config.get("base_url")
        auth_token = config.get("auth_token") or ""
        auth_mode = config.get_auth_mode()

        if not api_key or not base_url:
            raise ValueError("API Key and Base URL must be configured.")

        client = PromptQLClient(
            api_key=api_key,
            base_url=base_url,
            auth_token=auth_token,
            auth_mode=auth_mode,
        )

        result = client.start_thread(
            message=req.message,
            system_instructions=req.system_instructions
        )

        if isinstance(result, dict) and "error" in result:
            return {
                "success": False,
                "mode": "promptql",
                "error": result.get("error"),
                "details": result.get("details", "")
            }

        return {
            "success": True,
            "mode": "promptql",
            "thread_id": result.get("thread_id"),
            "response": result,
            "app_id": req.app_id if req.app_id else None,
        }
    except Exception as e:
        logger.error(f"PromptQL chat error: {e}")
        return {"success": False, "mode": "promptql", "error": str(e)}
