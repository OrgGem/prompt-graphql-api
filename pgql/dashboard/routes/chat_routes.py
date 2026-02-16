# pgql/dashboard/routes/chat_routes.py
"""Chat endpoint supporting both PromptQL and direct LLM modes."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from pgql.tools.config_tools import config
from pgql.api.promptql_client import PromptQLClient
from pgql.api.llm_client import LLMClient

logger = logging.getLogger("promptql_dashboard")

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str
    system_instructions: Optional[str] = None
    mode: str = "auto"  # "auto", "promptql", "llm"
    app_id: Optional[str] = None  # Optional app ID for testing with app credentials



def _build_llm_client() -> LLMClient:
    """Build an OpenAI-compatible LLM client from config."""
    llm_api_key = config.get("llm_api_key") or ""
    llm_base_url = config.get("llm_base_url")

    if not llm_base_url:
        raise ValueError("LLM Base URL must be configured.")

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
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    resolved = _resolve_mode(req.mode)

    if resolved == "none":
        raise HTTPException(
            status_code=400,
            detail="No LLM or PromptQL configured. Set up in Configuration tab."
        )

    if resolved == "llm":
        return await _chat_llm(req)
    else:
        return await _chat_promptql(req)


async def _chat_llm(req: ChatRequest) -> dict:
    """Chat via direct OpenAI-compatible API."""
    try:
        client = _build_llm_client()
        result = client.chat(
            message=req.message,
            system_instructions=req.system_instructions,
        )

        if not result.get("success"):
            return {
                "success": False,
                "mode": "llm",
                "error": result.get("error", "Unknown LLM error"),
            }

        return {
            "success": True,
            "mode": "llm",
            "content": result.get("content", ""),
            "model": result.get("model", ""),
            "usage": result.get("usage", {}),
        }
    except Exception as e:
        logger.error(f"LLM chat error: {e}")
        return {"success": False, "mode": "llm", "error": str(e)}


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
