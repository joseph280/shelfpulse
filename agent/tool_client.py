"""agent/tool_client.py - MCP client wrapper for the LangGraph agent.

Loads the 7 tools exposed by the ShelfPulse FastMCP server and converts
them into LangChain BaseTool objects ready to be bound to the LLM.
Also exposes `unwrap_result()` for parsing MCP content-block responses
into plain Python objects.

The MCP server must be running on http://127.0.0.1:8001 (or the host/
port set via MCP_HOST / MCP_PORT) before any node that uses these
tools is invoked. Start it with:

    uv run python -m mcp_server.server
"""

from __future__ import annotations

import json
import os

from functools import lru_cache
from typing import Any
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


def unwrap_result(raw: Any) -> Any:
    """Unwrap MCP content-block lists into plain Python objects."""
    if (
        isinstance(raw, list)
        and raw
        and isinstance(raw[0], dict)
        and raw[0].get("type") == "text"
    ):
        return json.loads(raw[0]["text"])
    return raw