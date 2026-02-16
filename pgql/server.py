# pgql/server.py
"""
PromptQL MCP Server - Main entry point.

Modular server that registers tools from dedicated modules.
Security features (rate limiting, input validation) are integrated
into each tool module.
"""

from mcp.server.fastmcp import FastMCP
import logging

# Ensure logger is configured to output to stderr
logger = logging.getLogger("promptql_server")

# Create an MCP server
mcp = FastMCP("PromptQL")

# Register tool modules
from pgql.tools import (
    register_config_tools,
    register_thread_tools,
    register_hasura_tools,
)

register_config_tools(mcp)
register_thread_tools(mcp)
register_hasura_tools(mcp)
logger.info("All tool modules registered successfully.")


# --- MCP Prompts ---

@mcp.prompt(name="data_analysis")
def data_analysis_prompt(topic: str) -> str:
    """Create a prompt for data analysis on a specific topic."""
    logger.info("=" * 80)
    logger.info("PROMPT: data_analysis")
    logger.info(f"Topic: '{topic}'")
    logger.info("=" * 80)

    prompt = f"""
Please analyze my data related to {topic}. 
Include the following in your analysis:
1. Key trends over time
2. Important correlations
3. Unusual patterns or anomalies
4. Actionable insights
"""
    logger.info(f"Generated prompt: {prompt}")

    return prompt
