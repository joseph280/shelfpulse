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

from mcp_server.config import settings
from mcp_server.models import (
    Channel,
    KPISnapshot,
    MetricName,
    PeriodComparison,
    Product,
    Region,
    SalesQueryFilter,
    SalesRow,
    StockoutRisk,
)
from mcp_server.tools._helpers import build_where, fetch_one_strict, parse_period


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
    contention.
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


@mcp.tool
def list_regions() -> list[Region]:
    """List all sales regions (US census divisions).

    Returns 12 regions. Use this to resolve region_id values for filters.
    """
    with db() as conn:
        rows = conn.execute(
            "SELECT region_id, region_name FROM regions ORDER BY region_id"
        ).fetchall()
        return [Region(region_id=row[0], region_name=row[1]) for row in rows]
    


@mcp.tool
def list_channels() -> list[Channel]:
    """List all sales channels.
    
    Returns 4 channels: GRO (grocery), CST (convenience), CLU (club),
    ONL (online). Use this to resolve channel_id values for filters.    
    """
    with db() as conn:
        rows = conn.execute(
            "SELECT channel_id, channel_name FROM channels ORDER BY channel_id"
        ).fetchall()
        return [Channel(channel_id=row[0], channel_name=row[1]) for row in rows]
    


@mcp.tool
def query_sales(filter: SalesQueryFilter, limit: int = 100) -> list[SalesRow]:
    """Return raw weekly_sales rows matching the filter.

    Requires at least one filter constraint to avoid pulling the full
    warehouse. Returns up to `limit` rows (default 1000) ordered by
    week_start, product_id. For aggregated KPIs use `compute_kpi` instead.
    """
    if not any(
        [
            filter.product_id,
            filter.category,
            filter.region_id,
            filter.channel_id,
            filter.start_date,
            filter.end_date,
        ]
    ):
        raise ValueError("At least one filter constraint is required")
    
    where, params = build_where(filter)
    sql = f"""
        SELECT ws.week_start, ws.product_id, ws.region_id, ws.channel_id, 
               ws.units_sold, ws.gross_sales, ws.promo_flag, ws.discount_pct
        FROM weekly_sales ws
        JOIN products p ON p.product_id = ws.product_id
        {where}
        ORDER BY ws.week_start, ws.product_id, ws.region_id, ws.channel_id
        LIMIT ?
    """
    params.append(limit)

    with db() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [
        SalesRow(
            week_start=str(row[0]),
            product_id=row[1],
            region_id=row[2],
            channel_id=row[3],
            units_sold=row[4],
            gross_sales=row[5],
            promo_flag=row[6],
            discount_pct=row[7],
        ) for row in rows
    ]


@mcp.tool
def compute_kpi(filter: SalesQueryFilter) -> KPISnapshot:
    """Compute aggregated KPIs for sales matching the filter.

    Returns a single snapshot with all seven metrics (units, gross sales,
    COGS, profit, margin %, promo share %, avg discount %). Empty result
    sets return zeros — not an error.
    """
    where, params = build_where(filter)
    sql = f"""
        SELECT
            COALESCE(SUM(ws.units_sold), 0)                                              AS units_sold,
            COALESCE(SUM(ws.gross_sales), 0.0)                                           AS gross_sales,
            COALESCE(SUM(ws.units_sold * p.cogs), 0.0)                                   AS cogs,
            COALESCE(SUM(CASE WHEN ws.promo_flag THEN ws.gross_sales ELSE 0 END), 0.0)   AS promo_sales,
            AVG(CASE WHEN ws.promo_flag THEN ws.discount_pct END)                        AS avg_disc_pct
        FROM weekly_sales ws
        JOIN products p ON p.product_id = ws.product_id
        {where}
    """
    with db() as conn:
        row = fetch_one_strict(conn, sql, params)

    units = int(row[0])
    gross = float(row[1])
    cogs = float(row[2])
    promo = float(row[3])
    avg_disc = float(row[4]) if row[4] is not None else 0.0

    profit = gross - cogs
    margin_pct = (profit / gross * 100.0) if gross > 0 else 0.0
    promo_share = (promo / gross * 100.0) if gross > 0 else 0.0

    print(f"row tuple: {row}")


    return KPISnapshot(
        units_sold=units,
        gross_sales=round(gross, 2),
        cost_of_goods_sold=round(cogs, 2),
        gross_profit=round(profit, 2),
        gross_margin_pct=round(margin_pct, 2),
        promo_sales_share_pct=round(promo_share, 2),
        avg_discount_pct=round(avg_disc, 2)
    )


@mcp.tool
def compare_periods(
    metric: MetricName,
    filter: SalesQueryFilter,
    period_a: str,
    period_b: str,
) -> PeriodComparison:
    """Compare a single metric between two periods.

    Periods: 'QN-YYYY' (e.g. 'Q1-2026') or 'YYYY-MM-DD..YYYY-MM-DD'.
    The filter's start_date / end_date are ignored — periods override.
    Negative percentage_change means period_b is lower than period_a.
    """
    a_start, a_end = parse_period(period_a)
    b_start, b_end = parse_period(period_b)

    filter_a = filter.model_copy(update={"start_date": a_start, "end_date": a_end})
    filter_b = filter.model_copy(update={"start_date": b_start, "end_date": b_end})

    kpi_a = compute_kpi(filter_a)
    kpi_b = compute_kpi(filter_b)

    value_a = float(getattr(kpi_a, metric))
    value_b = float(getattr(kpi_b, metric))

    abs_change = value_b - value_a
    pct_change = (abs_change / value_a * 100.0) if value_a != 0 else 0.0

    return PeriodComparison(
        metric=metric,
        period_a=period_a,
        period_b=period_b,
        value_a= round(value_a, 2),
        value_b= round(value_b, 2),
        absolute_change=round(abs_change, 2),
        percentage_change=round(pct_change, 2)
    )


@mcp.tool
def detect_stockout_risk(horizon_days: int = 30) -> list[StockoutRisk]:
    """Detect SKU+region pairs at risk of stockout within `horizon_days`.

    Uses the most recent inventory snapshot. Anything with weeks_of_cover
    <= horizon_days/7 is returned. Labels: CRITICAL (<= 2.0 weeks),
    WARNING (everything else within the horizon). OK rows are filtered out.
    """
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    
    threshold_weeks = horizon_days / 7.0

    sql = """
        SELECT product_id, region_id, on_hand_units, weeks_of_cover
        FROM inventory_snapshots
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_snapshots)
          AND weeks_of_cover <= ?
        ORDER BY weeks_of_cover ASC
    """
    with db() as conn:
        rows = conn.execute(sql, [threshold_weeks]).fetchall()

    return [
        StockoutRisk(
            product_id=row[0],
            region_id=row[1],
            on_hand_units=int(row[2]),
            weeks_of_cover=float(row[3]),
            risk_level="CRITICAL" if float(row[3]) <= 2.0 else "WARNING"
        ) for row in rows
    ]


# Entry point
if __name__ == "__main__":
    print(f"ShelfPulse MCP server starting on http://{settings.mcp_host}:{settings.mcp_port}")
    print(f"Warehouse: {settings.db_path.resolve()}")
    mcp.run(transport="http", host=settings.mcp_host, port=settings.mcp_port)