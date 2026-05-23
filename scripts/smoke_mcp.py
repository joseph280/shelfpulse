"""Smoke test for the running MCP server. Usage: uv run python scripts/smoke_mcp.py"""
import asyncio
from fastmcp import Client


async def main() -> None:
    async with Client("http://127.0.0.1:8001/mcp") as c:
        tools = await c.list_tools()
        print(f"Connected. {len(tools)} tool(s):")
        for t in tools:
            print(f"  - {t.name}")

        if any(t.name == "list_products" for t in tools):
            result = await c.call_tool("list_products", {})
            print(f"\nlist_products returned {len(result.data)} rows")
            print(f"first row: {result.data[0]}")


if __name__ == "__main__":
    asyncio.run(main())