"""agent/tool_client.py - MCP client wrapper for the LangGraph agent.
Loads the 6 tools exposed by the ShelfPulse FastMCP server and converts
them into LangChain Tool objects ready to be bound to the LLM.
The MCP server must be running on http://127.0.0.1:8001 before any node
that uses these tools is invoked. Start it with:
uv run python -m mcp_server.server
"""

from __future__ import annotations

import os

from functools import lru_cache
from langchain_core.tools import BaseTool

from langchain_mcp_adapters.client import MultiServerMCPClient

MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/mcp"


@lru_cache(maxsize=1)
def _client() -> MultiServerMCPClient:
    """Singleton MCP client so we open one HTTP session per process."""
    return MultiServerMCPClient(
        {
            "shelfpulse":{
                "url": MCP_URL,
                "transport": "streamable_http"
            }
        }
    )


async def load_mcp_tools() -> list[BaseTool]:
    """
    Return the 6 ShelfPulse MCP tools as LangChain Tool objects.
    Async because the MCP handshake requires an HTTP round-trip. Call
    once at graph build time and bind the result to the LLM.
    """
    return await _client().get_tools()