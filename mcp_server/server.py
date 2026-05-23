"""mcp_server/server.py - FastMCP server for ShelfPulse.
 
Exposes DuckDB-backed tools over HTTP MCP transport. The LangGraph agent
consumes this server via langchain-mcp-adapters.
 
Run with:
    uv run python -m mcp_server.server
 
Default bind: 127.0.0.1:8001. Override with MCP_HOST / MCP_PORT env vars.
"""
 
from __future__ import annotations
 
from contextlib import contextmanager
from typing import Iterator
 
import duckdb
from fastmcp import FastMCP
 
from mcp_server.models import Product

# Config
from mcp_server.config import settings
# ... settings.db_path, settings.mcp_host, settings.mcp_port


# Server instance
mcp: FastMCP = FastMCP(
    name="shelfpulse",
    instructions=(
        "ShelfPulse MCP server. Provides read-only access to a synthetic CPG "
        "warehouse: products, regions, channels, weekly sales, and inventory "
        "snapshots. All tools return Pydantic-typed results."
    )
)

# Connection helper
@contextmanager
def db() -> Iterator[duckdb.DuckDBPyConnection]:
    """Read-only DuckDB connection scoped to one tool call.
 
    Read-only mode lets multiple tool calls run concurrently without lock
    contention. The warehouse is rebuilt by data/seed.py, never by the agent.
    """
    if not settings.db_path.exists():
        raise FileNotFoundError(
            f"Warehouse not found at {settings.db_path}. Run data/seed.py to create it."
        )
    conn = duckdb.connect(str(settings.db_path), read_only=True)
    try:
        yield conn
    finally:
        conn.close()


# Tools
@mcp.tool
def list_products() -> list[Product]:
    """List every product in the catalog.
 
    Returns all 40 SKUs with brand, category, subcategory, pack size, list
    price, and COGS. Use this to resolve SKU IDs before calling query_sales
    or compute_kpi.
    """
    with db() as conn:
        rows = conn.execute(
            """
            SELECT product_id, brand, category, subcategory, pack_size, list_price, cogs
            FROM products
            ORDER BY product_id
            """
        ).fetchall()

    return [
        Product(
            product_id=row[0],
            brand=row[1],
            category=row[2],
            subcategory=row[3],
            pack_size=row[4],
            list_price=row[5],
            cogs=row[6],
        ) for row in rows
    ]


# Entry point
if __name__ == "__main__":
    print(f"ShelfPulse MCP server starting on http://{settings.mcp_host}:{settings.mcp_port}")
    print(f"Warehouse: {settings.db_path.resolve()}")
    mcp.run(transport="http", host=settings.mcp_host, port=settings.mcp_port)