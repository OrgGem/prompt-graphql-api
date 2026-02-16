# pgql/tools/thread_tools.py
"""Thread management tools for MCP server with security integration."""

from mcp.server.fastmcp import FastMCP
from typing import Optional
import logging
import time
import traceback

from pgql.api.promptql_client import PromptQLClient
from pgql.security import validate_thread_id, validate_message, rate_limiter
from pgql.monitoring import request_metrics
from pgql.tools.config_tools import config

logger = logging.getLogger("promptql_server")


def _get_promptql_client() -> PromptQLClient:
    """Get a configured PromptQL client."""
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    auth_token = config.get("auth_token") or ""
    auth_mode = config.get_auth_mode()

    logger.info(f"Loading config - API Key exists: {bool(api_key)}, PGQL Base URL exists: {bool(base_url)}, Auth Token exists: {bool(auth_token)}, Auth Mode: {auth_mode}")

    if not api_key or not base_url:
        raise ValueError("PromptQL API key and PGQL Base URL must be configured. Use the setup_config tool.")

    return PromptQLClient(api_key=api_key, base_url=base_url, auth_token=auth_token, auth_mode=auth_mode)


def _extract_response_data(interactions: list) -> dict:
    """Extract structured data from thread interactions.
    
    Returns:
        Dict with answer, plans, code_blocks, code_outputs, artifacts
    """
    answer_text = "No answer received from PromptQL."
    plans = []
    code_blocks = []
    code_outputs = []
    artifacts_found = []

    if interactions:
        latest_interaction = interactions[-1]
        assistant_actions = latest_interaction.get("assistant_actions", [])

        if assistant_actions:
            for action in reversed(assistant_actions):
                if action.get("message"):
                    answer_text = action.get("message", "")
                    break

            for action in assistant_actions:
                plan = action.get("plan")
                if plan:
                    plans.append(plan)
                code = action.get("code")
                if code:
                    code_blocks.append(code)
                code_output = action.get("code_output")
                if code_output:
                    code_outputs.append(code_output)

        # Collect artifacts from all interactions
        for interaction in interactions:
            for action in interaction.get("assistant_actions", []):
                artifact_identifiers = action.get("artifact_identifiers", [])
                if artifact_identifiers:
                    artifacts_found.extend(artifact_identifiers)

    return {
        "answer": answer_text,
        "plans": plans,
        "code_blocks": code_blocks,
        "code_outputs": code_outputs,
        "artifacts": artifacts_found,
    }


def register_thread_tools(mcp: FastMCP):
    """Register thread management tools with security integration."""

    @mcp.tool(name="start_thread")
    async def start_thread(message: str, system_instructions: Optional[str] = None) -> dict:
        """
        Start a new PromptQL thread with a message and poll for completion.

        Args:
            message: The initial message to start the thread with
            system_instructions: Optional system instructions for the LLM

        Returns:
            Complete response from PromptQL with structured data including thread_id, interaction_id, answer, plans, code, and artifacts
        """
        logger.info("=" * 80)
        logger.info("TOOL CALL: start_thread")
        logger.info(f"Message: '{message}'")
        logger.info("=" * 80)

        # --- Security: Rate limiting ---
        if not rate_limiter.is_allowed():
            return {"success": False, "error": "Rate limit exceeded. Please try again later.", "thread_id": None, "interaction_id": None}

        # --- Security: Input validation ---
        try:
            message = validate_message(message)
        except (ValueError, Exception) as e:
            return {"success": False, "error": f"Invalid message: {str(e)}", "thread_id": None, "interaction_id": None}

        _start = time.time()
        try:
            client = _get_promptql_client()
            result = client.start_thread(message=message, system_instructions=system_instructions)

            if "error" in result:
                logger.error(f"ERROR RESPONSE: {result['error']}")
                request_metrics.record_request("start_thread", time.time() - _start, False, result["error"])
                return {"success": False, "error": result["error"], "details": result.get("details", ""), "thread_id": None, "interaction_id": None}

            thread_id = result.get("thread_id")
            interaction_id = result.get("interaction_id")

            if not thread_id:
                request_metrics.record_request("start_thread", time.time() - _start, False, "No thread_id received")
                return {"success": False, "error": "No thread_id received from PromptQL", "thread_id": None, "interaction_id": None}

            interactions = result.get("interactions", [])
            response_data = _extract_response_data(interactions)

            logger.info(f"THREAD COMPLETED: {thread_id}")
            request_metrics.record_request("start_thread", time.time() - _start, True)
            return {
                "success": True,
                "thread_id": thread_id,
                "interaction_id": interaction_id,
                **response_data,
                "interactions_count": len(interactions),
                "raw_response": result
            }

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"UNEXPECTED ERROR: {str(e)}")
            logger.error(error_trace)
            request_metrics.record_request("start_thread", time.time() - _start, False, str(e))
            return {"success": False, "error": f"Unexpected error: {str(e)}", "error_trace": error_trace, "thread_id": None, "interaction_id": None}

    @mcp.tool(name="start_thread_without_polling")
    async def start_thread_without_polling(message: str, system_instructions: Optional[str] = None) -> dict:
        """
        Start a new PromptQL thread with a message without waiting for completion.

        Args:
            message: The initial message to start the thread with
            system_instructions: Optional system instructions for the LLM

        Returns:
            Thread ID and interaction ID for the started thread with status information
        """
        logger.info("=" * 80)
        logger.info("TOOL CALL: start_thread_without_polling")
        logger.info(f"Message: '{message}'")
        logger.info("=" * 80)

        # --- Security ---
        if not rate_limiter.is_allowed():
            return {"success": False, "error": "Rate limit exceeded. Please try again later.", "thread_id": None, "interaction_id": None}

        try:
            message = validate_message(message)
        except (ValueError, Exception) as e:
            return {"success": False, "error": f"Invalid message: {str(e)}", "thread_id": None, "interaction_id": None}

        _start = time.time()
        try:
            client = _get_promptql_client()
            result = client.start_thread_without_polling(message=message, system_instructions=system_instructions)

            if "error" in result:
                request_metrics.record_request("start_thread_without_polling", time.time() - _start, False, result["error"])
                return {"success": False, "error": result["error"], "details": result.get("details", ""), "thread_id": None, "interaction_id": None}

            thread_id = result.get("thread_id")
            interaction_id = result.get("interaction_id")

            if not thread_id:
                request_metrics.record_request("start_thread_without_polling", time.time() - _start, False, "No thread_id")
                return {"success": False, "error": "No thread_id received from PromptQL", "thread_id": None, "interaction_id": None}

            logger.info(f"THREAD STARTED (NO POLLING): {thread_id}")
            request_metrics.record_request("start_thread_without_polling", time.time() - _start, True)
            return {
                "success": True,
                "thread_id": thread_id,
                "interaction_id": interaction_id,
                "message": "Thread started successfully. Use get_thread_status to check progress or continue_thread to add more messages.",
                "status": "started",
                "polling": False
            }

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"UNEXPECTED ERROR: {str(e)}")
            request_metrics.record_request("start_thread_without_polling", time.time() - _start, False, str(e))
            return {"success": False, "error": f"Unexpected error: {str(e)}", "error_trace": error_trace, "thread_id": None, "interaction_id": None}

    @mcp.tool(name="continue_thread")
    async def continue_thread(thread_id: str, message: str, system_instructions: Optional[str] = None) -> dict:
        """
        Continue an existing PromptQL thread with a new message.

        Args:
            thread_id: The ID of the thread to continue
            message: The new message to add to the thread
            system_instructions: Optional system instructions for the LLM

        Returns:
            Structured response from PromptQL for the continued conversation
        """
        logger.info("=" * 80)
        logger.info("TOOL CALL: continue_thread")
        logger.info(f"Thread ID: {thread_id}")
        logger.info(f"Message: '{message}'")
        logger.info("=" * 80)

        # --- Security ---
        if not rate_limiter.is_allowed():
            return {"success": False, "error": "Rate limit exceeded.", "thread_id": thread_id, "interaction_id": None}

        try:
            thread_id = validate_thread_id(thread_id)
            message = validate_message(message)
        except (ValueError, Exception) as e:
            return {"success": False, "error": f"Validation error: {str(e)}", "thread_id": thread_id, "interaction_id": None}

        _start = time.time()
        try:
            client = _get_promptql_client()
            response = client.continue_thread(thread_id=thread_id, message=message, system_instructions=system_instructions)

            if "error" in response:
                request_metrics.record_request("continue_thread", time.time() - _start, False, response["error"])
                return {"success": False, "error": response["error"], "details": response.get("details", ""), "thread_id": thread_id, "interaction_id": None}

            interactions = response.get("interactions", [])
            response_data = _extract_response_data(interactions)

            interaction_id = interactions[-1].get("interaction_id") if interactions else None

            logger.info("RESPONSE PROCESSED SUCCESSFULLY")
            request_metrics.record_request("continue_thread", time.time() - _start, True)
            return {
                "success": True,
                "thread_id": thread_id,
                "interaction_id": interaction_id,
                **response_data,
                "interactions_count": len(interactions),
                "raw_response": response
            }

        except Exception as e:
            logger.error(f"UNEXPECTED ERROR: {str(e)}")
            request_metrics.record_request("continue_thread", time.time() - _start, False, str(e))
            return {"success": False, "error": f"Unexpected error: {str(e)}", "thread_id": thread_id, "interaction_id": None}

    @mcp.tool(name="get_thread_status")
    async def get_thread_status(thread_id: str) -> dict:
        """
        Get the current status of a PromptQL thread with detailed information.

        Args:
            thread_id: The ID of the thread to check

        Returns:
            Comprehensive thread status as structured data
        """
        logger.info("=" * 80)
        logger.info("TOOL CALL: get_thread_status")
        logger.info(f"Thread ID: {thread_id}")
        logger.info("=" * 80)

        # --- Security ---
        if not rate_limiter.is_allowed():
            return {"success": False, "error": "Rate limit exceeded.", "thread_id": thread_id, "status": "error"}

        try:
            thread_id = validate_thread_id(thread_id)
        except (ValueError, Exception) as e:
            return {"success": False, "error": f"Invalid thread_id: {str(e)}", "thread_id": thread_id, "status": "error"}

        _start = time.time()
        try:
            client = _get_promptql_client()
            result = client.get_thread_status(thread_id)

            if "error" in result:
                request_metrics.record_request("get_thread_status", time.time() - _start, False, result["error"])
                return {
                    "success": False, "error": result["error"], "details": result.get("details", ""),
                    "thread_id": thread_id, "status": "error", "title": "", "version": "",
                    "interactions_count": 0, "message": f"Error getting thread {thread_id} status", "interactions": []
                }

            status = result.get("status", "unknown")
            thread_data = result.get("thread_data", {})
            interactions = thread_data.get("interactions", [])

            response_data = {
                "success": True,
                "thread_id": thread_id,
                "status": status,
                "interactions_count": len(interactions),
                "message": f"Thread {thread_id} is {status}",
                "title": thread_data.get("title", ""),
                "version": thread_data.get("version", ""),
                "interactions": [],
            }

            for i, interaction in enumerate(interactions, 1):
                interaction_data = {
                    "interaction_number": i,
                    "interaction_id": interaction.get("interaction_id"),
                    "user_message": {},
                    "assistant_actions": []
                }

                user_message_data = interaction.get("user_message", {})
                if user_message_data:
                    if isinstance(user_message_data, dict):
                        interaction_data["user_message"] = {
                            "message": user_message_data.get("message", ""),
                            "timestamp": user_message_data.get("timestamp", ""),
                            "timezone": user_message_data.get("timezone", ""),
                            "uploads": user_message_data.get("uploads", [])
                        }
                    else:
                        interaction_data["user_message"] = {"message": str(user_message_data), "timestamp": "", "timezone": "", "uploads": []}

                for j, action in enumerate(interaction.get("assistant_actions", []), 1):
                    action_data = {
                        "action_number": j,
                        "action_id": action.get("action_id"),
                        "status": action.get("status", "unknown"),
                        "message": action.get("message", ""),
                        "plan": action.get("plan", ""),
                        "code": {},
                        "code_output": action.get("code_output", ""),
                        "artifacts": action.get("artifact_identifiers", []),
                        "timing": {
                            "created_timestamp": action.get("created_timestamp", ""),
                            "response_start_timestamp": action.get("response_start_timestamp", ""),
                            "action_end_timestamp": action.get("action_end_timestamp", ""),
                            "llm_call_start_timestamp": action.get("llm_call_start_timestamp", ""),
                            "llm_call_end_timestamp": action.get("llm_call_end_timestamp", "")
                        }
                    }

                    code_data = action.get("code", {})
                    if code_data:
                        if isinstance(code_data, dict):
                            action_data["code"] = {
                                "code_block_id": code_data.get("code_block_id", ""),
                                "code": code_data.get("code", ""),
                                "query_plan": code_data.get("query_plan", ""),
                                "execution_start_timestamp": code_data.get("execution_start_timestamp"),
                                "execution_end_timestamp": code_data.get("execution_end_timestamp"),
                                "output": code_data.get("output"),
                                "error": code_data.get("error"),
                                "sql_statements": code_data.get("sql_statements", [])
                            }
                        else:
                            action_data["code"] = {"code": str(code_data)}

                    interaction_data["assistant_actions"].append(action_data)
                response_data["interactions"].append(interaction_data)

            response_data["raw_thread_data"] = thread_data
            logger.info(f"THREAD STATUS: {status}")
            request_metrics.record_request("get_thread_status", time.time() - _start, True)
            return response_data

        except Exception as e:
            logger.error(f"UNEXPECTED ERROR: {str(e)}")
            request_metrics.record_request("get_thread_status", time.time() - _start, False, str(e))
            return {
                "success": False, "error": f"Unexpected error: {str(e)}", "thread_id": thread_id,
                "status": "error", "title": "", "version": "", "interactions_count": 0,
                "message": f"Unexpected error getting thread {thread_id} status", "interactions": []
            }

    @mcp.tool(name="cancel_thread")
    async def cancel_thread(thread_id: str) -> dict:
        """
        Cancel the processing of the latest interaction in a PromptQL thread.

        Args:
            thread_id: The ID of the thread to cancel

        Returns:
            Cancellation result with success status and details
        """
        logger.info("=" * 80)
        logger.info("TOOL CALL: cancel_thread")
        logger.info(f"Thread ID: {thread_id}")
        logger.info("=" * 80)

        # --- Security ---
        try:
            thread_id = validate_thread_id(thread_id)
        except (ValueError, Exception) as e:
            return {"success": False, "error": f"Invalid thread_id: {str(e)}", "thread_id": thread_id}

        _start = time.time()
        try:
            client = _get_promptql_client()
            result = client.cancel_thread(thread_id)

            if "error" in result:
                request_metrics.record_request("cancel_thread", time.time() - _start, False, result["error"])
                return {"success": False, "error": result["error"], "details": result.get("details", ""), "thread_id": thread_id}

            logger.info(f"THREAD CANCELLED: {thread_id}")
            request_metrics.record_request("cancel_thread", time.time() - _start, True)
            return {
                "success": True,
                "thread_id": thread_id,
                "message": result.get("message", "Thread cancelled"),
                "action": "cancelled",
                "raw_response": result
            }

        except Exception as e:
            logger.error(f"UNEXPECTED ERROR: {str(e)}")
            request_metrics.record_request("cancel_thread", time.time() - _start, False, str(e))
            return {"success": False, "error": f"Unexpected error: {str(e)}", "thread_id": thread_id}

    @mcp.tool(name="get_artifact")
    def get_artifact(thread_id: str, artifact_id: str) -> dict:
        """
        Get artifact data from a specific thread.

        Args:
            thread_id: The ID of the thread containing the artifact
            artifact_id: The ID of the artifact to retrieve

        Returns:
            Dictionary containing artifact data, metadata, and retrieval status
        """
        logger.info("=" * 80)
        logger.info("TOOL CALL: get_artifact")
        logger.info(f"Thread ID: {thread_id}, Artifact ID: {artifact_id}")
        logger.info("=" * 80)

        # --- Security ---
        try:
            thread_id = validate_thread_id(thread_id)
        except (ValueError, Exception) as e:
            return {"success": False, "error": f"Invalid thread_id: {str(e)}", "thread_id": thread_id, "artifact_id": artifact_id}

        _start = time.time()
        try:
            client = _get_promptql_client()
            response_data = client.get_artifact(thread_id, artifact_id)

            if "error" in response_data:
                request_metrics.record_request("get_artifact", time.time() - _start, False, response_data["error"])
                return {"success": False, "error": response_data["error"], "details": response_data.get("details", ""), "thread_id": thread_id, "artifact_id": artifact_id}

            logger.info(f"ARTIFACT RETRIEVED: {artifact_id}")
            request_metrics.record_request("get_artifact", time.time() - _start, True)
            return {
                "success": True,
                "thread_id": thread_id,
                "artifact_id": artifact_id,
                "content_type": response_data.get("content_type"),
                "size": response_data.get("size"),
                "data": response_data.get("data"),
                "message": f"Artifact {artifact_id} retrieved successfully from thread {thread_id}",
                "raw_response": response_data
            }
        except Exception as e:
            logger.error(f"ERROR in get_artifact tool: {str(e)}")
            request_metrics.record_request("get_artifact", time.time() - _start, False, str(e))
            return {"success": False, "error": f"Get artifact error: {str(e)}", "thread_id": thread_id, "artifact_id": artifact_id}
