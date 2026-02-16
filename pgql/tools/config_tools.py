# pgql/tools/config_tools.py
"""Configuration management tools for MCP server."""

from mcp.server.fastmcp import FastMCP
from typing import Optional
import logging

from pgql.config import ConfigManager

logger = logging.getLogger("promptql_server")

# Shared config instance
config = ConfigManager()


def register_config_tools(mcp: FastMCP):
    """Register configuration management tools."""

    @mcp.tool(name="setup_config")
    def setup_config(
        api_key: str,
        base_url: str,
        auth_token: str,
        auth_mode: str = "public",
        hasura_graphql_endpoint: Optional[str] = None,
        hasura_admin_secret: Optional[str] = None
    ) -> dict:
        """
        Configure the PromptQL MCP server with API key, PGQL Base URL, and auth token.

        Args:
            api_key: PromptQL API key
            base_url: PromptQL PGQL Base URL (e.g., https://promptql.<dataplane-name>.private-ddn.hasura.app/playground)
            auth_token: DDN Auth Token for accessing your data
            auth_mode: Authentication mode - "public" for Auth-Token or "private" for x-hasura-ddn-token (default: "public")
            hasura_graphql_endpoint: Optional Hasura CE v2 GraphQL endpoint (e.g. http://localhost:8080/v1/graphql)
            hasura_admin_secret: Optional Hasura admin secret

        Returns:
            Configuration result with success status and details
        """
        logger.info("=" * 80)
        logger.info("TOOL CALL: setup_config")
        masked_key = api_key[:5] + "..." + api_key[-5:] if api_key else "None"
        masked_token = auth_token[:8] + "..." + auth_token[-4:] if len(auth_token) > 12 else auth_token[:4] + "..."
        logger.info(f"API Key: '{masked_key}' (redacted)")
        logger.info(f"PGQL Base URL: '{base_url}'")
        logger.info(f"Auth Mode: '{auth_mode}'")
        logger.info("=" * 80)

        # Validate auth_mode
        if auth_mode.lower() not in ["public", "private"]:
            return {
                "success": False,
                "error": f"Invalid auth_mode '{auth_mode}'. Must be 'public' or 'private'.",
                "configured_items": {}
            }

        try:
            config.set("api_key", api_key)
            config.set("base_url", base_url)
            config.set("auth_token", auth_token)
            config.set("auth_mode", auth_mode.lower())
            if hasura_graphql_endpoint:
                config.set("hasura_graphql_endpoint", hasura_graphql_endpoint)
            if hasura_admin_secret:
                config.set("hasura_admin_secret", hasura_admin_secret)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid URL: {str(e)}",
                "configured_items": {}
            }

        logger.info("CONFIGURATION SAVED SUCCESSFULLY")
        return {
            "success": True,
            "message": "Configuration saved successfully.",
            "configured_items": {
                "api_key": masked_key,
                "base_url": base_url,
                "auth_token": masked_token,
                "auth_mode": auth_mode.lower(),
                "hasura_graphql_endpoint": hasura_graphql_endpoint,
                "hasura_admin_secret": bool(hasura_admin_secret)
            }
        }

    @mcp.tool(name="check_config")
    def check_config() -> dict:
        """
        Check if the PromptQL MCP server is already configured with API key, PGQL Base URL, and auth token.

        Returns:
            Configuration status with detailed information about what's configured
        """
        logger.info("=" * 80)
        logger.info("TOOL CALL: check_config")
        logger.info("=" * 80)

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        auth_token = config.get("auth_token")
        auth_mode = config.get_auth_mode()
        hasura_graphql_endpoint = config.get("hasura_graphql_endpoint")
        hasura_admin_secret = config.get("hasura_admin_secret")

        if api_key and base_url and auth_token:
            masked_key = api_key[:5] + "..." + api_key[-5:] if api_key else "None"
            masked_token = auth_token[:8] + "..." + auth_token[-4:] if len(auth_token) > 12 else auth_token[:4] + "..."
            logger.info("CONFIGURATION CHECK: Already configured")
            return {
                "configured": True,
                "message": "PromptQL is fully configured",
                "configuration": {
                    "api_key": masked_key,
                    "base_url": base_url,
                    "auth_token": masked_token,
                    "auth_mode": auth_mode,
                    "hasura_graphql_endpoint": hasura_graphql_endpoint,
                    "hasura_admin_secret_configured": bool(hasura_admin_secret)
                },
                "missing_items": []
            }
        else:
            missing = []
            if not api_key:
                missing.append("API Key")
            if not base_url:
                missing.append("PGQL Base URL")
            if not auth_token:
                missing.append("Auth Token")

            logger.info(f"CONFIGURATION CHECK: Missing {', '.join(missing)}")
            return {
                "configured": False,
                "message": f"PromptQL is not fully configured. Missing: {', '.join(missing)}",
                "configuration": {
                    "api_key": api_key[:5] + "..." + api_key[-5:] if api_key else None,
                    "base_url": base_url,
                    "auth_token": auth_token[:8] + "..." + auth_token[-4:] if auth_token and len(auth_token) > 12 else auth_token[:4] + "..." if auth_token else None,
                    "hasura_graphql_endpoint": hasura_graphql_endpoint,
                    "hasura_admin_secret_configured": bool(hasura_admin_secret)
                },
                "missing_items": missing
            }
