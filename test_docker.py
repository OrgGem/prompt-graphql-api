#!/usr/bin/env python3
"""Test the PromptQL MCP server running in a Docker container."""

import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_docker_server():
    """Test the server running in Docker."""
    server_params = StdioServerParameters(
        command="docker",
        args=[
            "run", "--rm", "-i",
            "--env-file", ".env",
            "prompt-graphql-server:local"
        ],
        env=None
    )
    
    print("🐳 Testing PromptQL MCP server in Docker container...")
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as client:
                # Initialize connection
                await client.initialize()
                print("✅ Docker server initialized successfully")
                
                # Check configuration
                config_response = await client.call_tool("check_config", {})
                print(f"\n📋 Configuration Status:")
                if hasattr(config_response, 'content') and config_response.content:
                    import json
                    config_data = json.loads(config_response.content[0].text)
                    print(f"  • Configured: {config_data.get('configured')}")
                    print(f"  • Auth Mode: {config_data.get('auth_mode')}")
                    for key, value in config_data.get('configured_items', {}).items():
                        status = "✅" if value else "❌"
                        print(f"  {status} {key}")
                
                # List available tools
                tools_response = await client.list_tools()
                print(f"\n🛠️  Available tools: {len(tools_response.tools)}")
                
                print("\n✅ Docker container test passed!")
                return True
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_docker_server())
    sys.exit(0 if result else 1)
