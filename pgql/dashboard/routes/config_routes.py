# pgql/dashboard/routes/config_routes.py
"""Configuration management endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from pgql.tools.config_tools import config
from pgql.security.rate_limiter import rate_limiter
from pgql.utils.cache import metadata_cache

router = APIRouter(prefix="/config", tags=["Configuration"])

# Well-known LLM provider identifiers
KNOWN_LLM_PROVIDERS = {
    "openai", "anthropic", "google", "groq",
    "mistral", "together", "ollama", "lmstudio",
}


# --- Request/Response Models ---

class ConfigUpdateRequest(BaseModel):
    key: str
    value: str

class APIKeyRequest(BaseModel):
    provider: str  # LLM providers: "openai", "anthropic", or custom name
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[str] = None
    max_tokens: Optional[str] = None

class RateLimitUpdateRequest(BaseModel):
    rate: int = 30
    per: int = 60


# --- Config Endpoints ---

@router.get("")
async def get_config():
    """Get current configuration (sensitive values masked)."""
    api_key = config.get("api_key")
    auth_token = config.get("auth_token")
    base_url = config.get("base_url")
    auth_mode = config.get_auth_mode()
    hasura_endpoint = config.get("hasura_graphql_endpoint")

    # Check which required fields are missing
    missing = []
    if not api_key:
        missing.append({"key": "api_key", "label": "PromptQL Service Key", "env": "PROMPTQL_API_KEY", "hint": "Service auth key for PromptQL Cloud — NOT for external apps. Click Generate to create one.", "required": True})
    if not base_url:
        missing.append({"key": "base_url", "label": "PGQL Base URL", "env": "PGQL_BASE_URL", "hint": "Server base URL (default: http://localhost:8765)", "required": True})
    if not auth_token:
        missing.append({"key": "auth_token", "label": "Auth Token (DDN)", "env": "PROMPTQL_AUTH_TOKEN", "hint": "Optional — only needed for Hasura DDN/PromptQL Cloud. Not required for Hasura CE v2.x", "required": False})

    return {
        "configured": config.is_configured(),
        "missing_fields": missing,
        "config": {
            "api_key": _mask(api_key),
            "base_url": base_url,
            "auth_mode": auth_mode,
            "hasura_graphql_endpoint": hasura_endpoint,
            "hasura_admin_secret": _mask(config.get("hasura_admin_secret")),
            "auth_token": _mask(auth_token),
        },
        "llm_config": {
            "llm_provider_id": config.get("llm_provider_id") or "",
        },
        "llm_configured": bool(config.get("llm_provider_id")),
    }


@router.post("/generate-key")
async def generate_key():
    """Generate a random API key."""
    key = config.generate_api_key()
    return {"key": key}




class LLMConfigUpdate(BaseModel):
    llm_provider_id: Optional[str] = None  # Provider ID from keys tab, or None to disable


@router.get("/llm")
async def get_llm_config():
    """Get current LLM configuration."""
    llm_provider_id = config.get("llm_provider_id") or ""
    return {
        "llm_provider_id": llm_provider_id,
        "configured": bool(llm_provider_id),
    }


@router.put("/llm")
async def update_llm_config(req: LLMConfigUpdate):
    """Update LLM configuration by selecting a provider from keys tab."""
    # Store the provider_id (or None to disable)
    config.set("llm_provider_id", req.llm_provider_id or "")
    return {
        "success": True,
        "llm_provider_id": req.llm_provider_id,
        "message": "LLM provider configured" if req.llm_provider_id else "LLM disabled"
    }


@router.put("")
async def update_config(req: ConfigUpdateRequest):
    """Update a configuration value."""
    try:
        config.set(req.key, req.value)
        return {"success": True, "message": f"Updated {req.key}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/export")
async def export_config():
    """Export configuration as JSON (values masked)."""
    return {
        "config": {k: _mask(v) if _is_sensitive(k) else v for k, v in config.config.items()},
        "message": "Sensitive values are masked. Use the setup tool for full values.",
    }


# --- LLM Provider API Key Management ---
# Note: PromptQL API key is NOT an LLM provider key.
# It is a service auth key managed in Server Configuration.

@router.get("/keys")
async def list_api_keys():
    """List all configured LLM provider API keys (masked).
    
    PromptQL API key is a service auth key (see Server Config),
    not an LLM provider. Only OpenAI, Anthropic, and custom
    LLM providers are listed here.
    """
    keys = {}
    provider_details = {}

    # Well-known LLM provider keys
    known_config_keys = {
        p: f"{p}_api_key" for p in KNOWN_LLM_PROVIDERS
    }

    for provider, config_key in known_config_keys.items():
        val = config.get(config_key)
        if val:
            keys[provider] = _mask(val)
            # Get associated details
            details = {}
            base_url = config.config.get(f"{provider}_base_url")
            model = config.config.get(f"{provider}_model")
            if base_url:
                details["base_url"] = base_url
            if model:
                details["model"] = model
            if details:
                provider_details[provider] = details

    # Custom provider keys
    for key in list(config.config.keys()):
        if key.startswith("custom_api_key_"):
            label = key.replace("custom_api_key_", "")
            pname = f"custom:{label}"
            keys[pname] = _mask(config.get(key))
            details = {}
            base_url = config.config.get(f"custom_base_url_{label}")
            model = config.config.get(f"custom_model_{label}")
            if base_url:
                details["base_url"] = base_url
            if model:
                details["model"] = model
            if details:
                provider_details[pname] = details

    return {"keys": keys, "provider_details": provider_details, "count": len(keys)}


@router.post("/keys")
async def add_api_key(req: APIKeyRequest):
    """Add or update an API key for a provider with optional connection settings."""
    provider = req.provider.lower().strip()

    # PromptQL key should be set via Server Config, not here
    if provider == "promptql":
        raise HTTPException(
            status_code=400,
            detail="PromptQL API key is a service auth key. Set it via Server Configuration, not LLM Provider Keys."
        )

    known_providers = KNOWN_LLM_PROVIDERS

    is_known = provider in known_providers
    is_custom = provider.startswith("custom:") or not is_known

    # Determine config key for API key
    if is_known:
        config_key = f"{provider}_api_key"
        prefix = provider
    else:
        label = provider.replace("custom:", "")
        config_key = f"custom_api_key_{label}"
        prefix = f"custom"
        label_suffix = f"_{label}"

    try:
        config.set(config_key, req.api_key)

        # Save extended connection params
        if is_known:
            if req.base_url:
                config.config[f"{provider}_base_url"] = req.base_url
            if req.model:
                config.config[f"{provider}_model"] = req.model
            if req.temperature:
                config.config[f"{provider}_temperature"] = req.temperature
            if req.max_tokens:
                config.config[f"{provider}_max_tokens"] = req.max_tokens
        else:
            label = provider.replace("custom:", "")
            if req.base_url:
                config.config[f"custom_base_url_{label}"] = req.base_url
            if req.model:
                config.config[f"custom_model_{label}"] = req.model
            if req.temperature:
                config.config[f"custom_temperature_{label}"] = req.temperature
            if req.max_tokens:
                config.config[f"custom_max_tokens_{label}"] = req.max_tokens

        config.save_config()
        return {"success": True, "provider": provider, "config_key": config_key}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/keys/{provider}/activate")
async def activate_provider(provider: str):
    """Set a provider's config as the active LLM configuration for chat."""
    provider = provider.lower().strip()

    known_providers = KNOWN_LLM_PROVIDERS

    is_known = provider in known_providers

    if is_known:
        api_key = config.get(f"{provider}_api_key")
        base_url = config.config.get(f"{provider}_base_url", "")
        model = config.config.get(f"{provider}_model", "")
        temperature = config.config.get(f"{provider}_temperature", "0.7")
        max_tokens = config.config.get(f"{provider}_max_tokens", "4096")
    else:
        label = provider.replace("custom:", "")
        api_key = config.get(f"custom_api_key_{label}")
        base_url = config.config.get(f"custom_base_url_{label}", "")
        model = config.config.get(f"custom_model_{label}", "")
        temperature = config.config.get(f"custom_temperature_{label}", "0.7")
        max_tokens = config.config.get(f"custom_max_tokens_{label}", "4096")

    if not api_key and not base_url:
        raise HTTPException(status_code=404, detail=f"No configuration found for {provider}")

    # Copy to active LLM config
    if api_key:
        config.set("llm_api_key", api_key)
    if base_url:
        config.set("llm_base_url", base_url)
    if model:
        config.config["llm_model"] = model
    if temperature:
        config.config["llm_temperature"] = temperature
    if max_tokens:
        config.config["llm_max_tokens"] = max_tokens
    # Also set as active llm_provider_id
    config.set("llm_provider_id", provider)
    config.save_config()

    return {"success": True, "message": f"{provider} activated as LLM", "model": model or "default"}


@router.delete("/keys/{provider}")
async def delete_api_key(provider: str):
    """Remove an API key and all associated config for a provider."""
    provider = provider.lower().strip()

    if provider == "promptql":
        raise HTTPException(
            status_code=400,
            detail="PromptQL API key is managed via Server Configuration."
        )

    known_providers = KNOWN_LLM_PROVIDERS

    is_known = provider in known_providers

    if is_known:
        keys_to_remove = [
            f"{provider}_api_key", f"{provider}_base_url",
            f"{provider}_model", f"{provider}_temperature",
            f"{provider}_max_tokens",
        ]
    else:
        label = provider.replace("custom:", "")
        keys_to_remove = [
            f"custom_api_key_{label}", f"custom_base_url_{label}",
            f"custom_model_{label}", f"custom_temperature_{label}",
            f"custom_max_tokens_{label}",
        ]

    removed = False
    for k in keys_to_remove:
        if k in config.config:
            del config.config[k]
            removed = True

    if removed:
        config.save_config()
        return {"success": True, "message": f"Removed {provider} and all associated settings"}
    else:
        raise HTTPException(status_code=404, detail=f"No configuration found for {provider}")


# --- Rate Limit Endpoints ---

@router.get("/rate-limit")
async def get_rate_limit():
    """Get current rate limit configuration."""
    return {
        "rate": rate_limiter.rate,
        "per_seconds": rate_limiter.per,
        "description": f"{rate_limiter.rate} requests per {rate_limiter.per} seconds",
    }


@router.put("/rate-limit")
async def update_rate_limit(req: RateLimitUpdateRequest):
    """Update rate limit settings."""
    rate_limiter.rate = req.rate
    rate_limiter.per = req.per
    # Reset allowances to apply new rate
    rate_limiter.allowance.clear()
    rate_limiter.last_check.clear()
    return {
        "success": True,
        "rate": req.rate,
        "per_seconds": req.per,
        "message": f"Rate limit updated to {req.rate} per {req.per}s",
    }


# --- Cache Endpoints ---

@router.get("/cache")
async def get_cache_stats():
    """Get cache statistics."""
    return metadata_cache.stats()


@router.post("/cache/clear")
async def clear_cache():
    """Clear the metadata cache."""
    metadata_cache.clear()
    return {"success": True, "message": "Cache cleared"}


# --- Helpers ---

def _mask(value: Optional[str]) -> Optional[str]:
    """Mask a sensitive string showing first 4 and last 4 chars."""
    if not value:
        return None
    if len(value) <= 8:
        return value[:2] + "***"
    return value[:4] + "****" + value[-4:]


def _is_sensitive(key: str) -> bool:
    """Check if a config key is sensitive."""
    sensitive = ["api_key", "auth_token", "admin_secret", "secret"]
    return any(s in key.lower() for s in sensitive)
