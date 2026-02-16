#!/usr/bin/env python3
"""Quick test script to verify PromptQL MCP server."""

import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_server():
    """Test that the server starts and can list tools."""
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "pgql", "run"],
        env=None
    )
    
    print("🔌 Connecting to PromptQL MCP server...")
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as client:
                # Initialize connection
                await client.initialize()
                print("✅ Server initialized successfully")
                
                # List available tools
                tools_response = await client.list_tools()
                print(f"\n📋 Available tools ({len(tools_response.tools)}):")
                
                for tool in tools_response.tools:
                    print(f"  • {tool.name}: {tool.description}")
                
                print("\n✅ Server test passed!")
                return True
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_server())
    sys.exit(0 if result else 1)
