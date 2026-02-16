# pgql/__main__.py

import sys
import os
import argparse
import logging
from pgql.server import mcp
from pgql.tools.config_tools import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)

logger = logging.getLogger("promptql_main")

def main():
    """Main entry point for the PromptQL MCP server."""
    logger.info("="*80)
    logger.info("STARTING PROMPTQL MCP SERVER")
    logger.info("="*80)
    
    parser = argparse.ArgumentParser(description="PromptQL MCP Server")
    subparsers = parser.add_subparsers(dest="command")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Configure the server")
    setup_parser.add_argument("--api-key", required=True, help="PromptQL API key")
    setup_parser.add_argument("--base-url", required=True, help="PromptQL PGQL Base URL")
    setup_parser.add_argument("--auth-token", required=False, default="", help="DDN Auth Token (optional, for PromptQL Cloud only)")
    setup_parser.add_argument("--auth-mode", default="public", choices=["public", "private"],
                             help="Authentication mode: 'public' for Auth-Token or 'private' for x-hasura-ddn-token (default: public)")
    setup_parser.add_argument("--hasura-graphql-endpoint", required=False, help="Optional Hasura CE v2 GraphQL endpoint")
    setup_parser.add_argument("--hasura-admin-secret", required=False, help="Optional Hasura CE v2 admin secret")

    # Run command (default)
    run_parser = subparsers.add_parser("run", help="Run the MCP server")
    run_parser.add_argument("--dashboard", action="store_true", help="Also start admin dashboard")
    run_parser.add_argument("--dashboard-port", type=int, default=8765, help="Dashboard port (default: 8765)")

    # Dashboard command
    dash_parser = subparsers.add_parser("dashboard", help="Start admin dashboard only")
    dash_parser.add_argument("--port", type=int, default=8765, help="Port to run dashboard on (default: 8765)")
    dash_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")

    args = parser.parse_args()

    if args.command == "setup":
        config.set("api_key", args.api_key)
        config.set("base_url", args.base_url)
        config.set("auth_token", args.auth_token)
        config.set("auth_mode", args.auth_mode)
        if args.hasura_graphql_endpoint:
            config.set("hasura_graphql_endpoint", args.hasura_graphql_endpoint)
        if args.hasura_admin_secret:
            config.set("hasura_admin_secret", args.hasura_admin_secret)
        logger.info(f"Configuration saved successfully with auth_mode: {args.auth_mode}")
        return 0
    
    if args.command == "dashboard":
        return _start_dashboard(args.host, args.port)
    
    # Default to running the MCP server
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Current directory: {os.getcwd()}")
    
    # Check if configuration is set
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    auth_token = config.get("auth_token")
    auth_mode = config.get_auth_mode()

    if not api_key or not base_url:
        logger.warning("WARNING: PromptQL configuration incomplete.")
        logger.warning("You can configure by running:")
        logger.warning("  python -m pgql setup --api-key YOUR_API_KEY --base-url YOUR_base_url --auth-token YOUR_AUTH_TOKEN --auth-mode public")
        logger.warning("Or by setting environment variables:")
        logger.warning("  PROMPTQL_API_KEY, PGQL_BASE_URL, PROMPTQL_AUTH_TOKEN, and PROMPTQL_AUTH_MODE")
        logger.warning("Continuing with unconfigured server...")
    else:
        # Show partial credentials for debugging
        masked_key = f"{api_key[:8]}...{api_key[-4:]}" if api_key else "None"
        masked_token = f"{auth_token[:8]}...{auth_token[-4:]}" if len(auth_token) > 12 else auth_token[:4] + "..."
        logger.info(f"Using API Key: {masked_key}")
        logger.info(f"Using PGQL Base URL: {base_url}")
        logger.info(f"Using Auth Token: {masked_token}")
        logger.info(f"Using Auth Mode: {auth_mode}")

    # Start dashboard alongside MCP if requested
    if hasattr(args, 'dashboard') and args.dashboard:
        import threading
        port = getattr(args, 'dashboard_port', 8765)
        dash_thread = threading.Thread(
            target=_start_dashboard,
            args=("127.0.0.1", port),
            daemon=True,
        )
        dash_thread.start()
        logger.info(f"Admin dashboard started on http://127.0.0.1:{port}")
    
    # Run the MCP server
    logger.info("STARTING MCP SERVER - READY FOR CONNECTIONS")
    mcp.run()
    return 0


def _start_dashboard(host: str = "127.0.0.1", port: int = 8765) -> int:
    """Start the admin dashboard server."""
    try:
        import uvicorn
        from pgql.dashboard.app import app
        logger.info(f"Starting admin dashboard on http://{host}:{port}")
        logger.info(f"API docs at http://{host}:{port}/api/docs")
        uvicorn.run(app, host=host, port=port, log_level="info")
        return 0
    except ImportError:
        logger.error("Dashboard requires fastapi and uvicorn. Install with: pip install fastapi uvicorn")
        return 1


if __name__ == "__main__":
    sys.exit(main())
