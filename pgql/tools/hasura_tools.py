# pgql/tools/hasura_tools.py
"""Hasura CE v2 integration tools for MCP server with security integration."""

from mcp.server.fastmcp import FastMCP
from typing import Optional
import logging
import time

from pgql.api.hasura_ce_client import HasuraCEClient
from pgql.api.hasura_query_planner import plan_prompt_to_graphql, synthesize_answer
from pgql.security import validate_message, rate_limiter
from pgql.monitoring import request_metrics
from pgql.tools.config_tools import config
from pgql.apps import app_manager

logger = logging.getLogger("promptql_server")


def _check_write_permission(query: str, app_role: str) -> bool:
    """Check if the query is allowed for the given app role.

    Read-only apps can only execute queries, not mutations.
    """
    if app_role == "write":
        return True
    query_stripped = query.strip().lower()
    if query_stripped.startswith("mutation"):
        return False
    return True


def _get_hasura_ce_client(
    graphql_endpoint: Optional[str] = None,
    admin_secret: Optional[str] = None
) -> HasuraCEClient:
    """Get a configured Hasura CE client."""
    endpoint = graphql_endpoint or config.get("hasura_graphql_endpoint")
    secret = admin_secret or config.get("hasura_admin_secret")
    if not endpoint:
        raise ValueError(
            "Hasura GraphQL endpoint must be configured. "
            "Use query_hasura_ce argument 'graphql_endpoint' or set PROMPTQL_HASURA_GRAPHQL_ENDPOINT."
        )
    return HasuraCEClient(graphql_endpoint=endpoint, admin_secret=secret)


def register_hasura_tools(mcp: FastMCP):
    """Register Hasura CE v2 tools with security integration."""

    @mcp.tool(name="query_hasura_ce")
    def query_hasura_ce(
        prompt: str,
        graphql_endpoint: Optional[str] = None,
        admin_secret: Optional[str] = None,
        role: Optional[str] = None,
        max_limit: int = 100,
        app_api_key: Optional[str] = None,
    ) -> dict:
        """
        Execute a prompt-driven Hasura CE v2 query flow:
        metadata -> planner -> GraphQL -> answer synthesis.

        Args:
            prompt: Natural language prompt to convert to a query
            graphql_endpoint: Optional Hasura GraphQL endpoint
            admin_secret: Optional Hasura admin secret
            role: Optional Hasura role
            max_limit: Maximum number of results (default: 100)
            app_api_key: Optional app API key for access control

        Returns:
            Query results with success status, answer, plan, and raw results
        """
        logger.info("=" * 80)
        logger.info("TOOL CALL: query_hasura_ce")
        logger.info(f"Prompt: '{prompt}'")
        logger.info("=" * 80)

        # --- Security ---
        if not rate_limiter.is_allowed():
            return {"success": False, "error": "Rate limit exceeded. Please try again later."}

        try:
            prompt = validate_message(prompt)
        except (ValueError, Exception) as e:
            return {"success": False, "error": f"Invalid prompt: {str(e)}"}

        _start = time.time()
        try:
            hasura = _get_hasura_ce_client(graphql_endpoint=graphql_endpoint, admin_secret=admin_secret)
            metadata = hasura.export_metadata()

            # Resolve app context for access control
            app_context = app_manager.resolve_by_api_key(app_api_key) if app_api_key else None
            allowed_tables = app_context["allowed_tables"] if app_context and app_context.get("allowed_tables") else None
            app_role = app_context["role"] if app_context else "write"

            plan = plan_prompt_to_graphql(
                prompt=prompt,
                metadata=metadata,
                max_limit=max_limit,
                allowed_tables=allowed_tables,
            )

            if not plan.get("success"):
                request_metrics.record_request("query_hasura_ce", time.time() - _start, False, plan.get("error", "Plan failed"))
                return {
                    "success": False,
                    "error": plan.get("error", "Could not create query plan."),
                    "plan": plan,
                }

            # Check write permission before executing
            if not _check_write_permission(plan["query"], app_role):
                request_metrics.record_request("query_hasura_ce", time.time() - _start, False, "Write denied")
                return {
                    "success": False,
                    "error": "Write access denied — this app has read-only permission",
                    "app_id": app_context.get("app_id") if app_context else None,
                }

            graphql_result = hasura.execute_graphql(query=plan["query"], role=role)
            answer = synthesize_answer(prompt=prompt, selected_table=plan["selected_table"], graphql_result=graphql_result)

            request_metrics.record_request("query_hasura_ce", time.time() - _start, True)
            return {
                "success": True,
                "prompt": prompt,
                "answer": answer,
                "plan": plan,
                "graphql_result": graphql_result,
            }
        except Exception as e:
            logger.error(f"ERROR in query_hasura_ce: {str(e)}")
            request_metrics.record_request("query_hasura_ce", time.time() - _start, False, str(e))
            return {
                "success": False,
                "error": f"query_hasura_ce error: {str(e)}",
            }
