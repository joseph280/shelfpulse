"""Shared helpers for MCP tools — WHERE-clause builder, period parser."""


import re
from datetime import date, timedelta
from typing import Any, Sequence

import duckdb

from mcp_server.models import SalesQueryFilter

_QUARTER_RE = re.compile(r"^Q([1-4])-(\d{4})$")
_RANGE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})$")


def fetch_one_strict(conn: duckdb.DuckDBPyConnection, sql: str, params: Sequence[Any] = ()) -> tuple:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        raise RuntimeError(f"Expected one row but got zero for query: {sql} with params {params}")
    return row


def build_where(
        filter: SalesQueryFilter, table_alias: str = "ws"
) -> tuple[str, list]:
    """Translate a SalesQueryFilter into a SQL WHERE fragment + params.

    The 'category' filter assumes the caller has JOINed 'products' aliased
    as 'p'. Returns ("", []) for an empty filter.
    """
    conditions: list[str] = []
    params: list = []

    if filter.product_id:
        conditions.append(f"{table_alias}.product_id = ?")
        params.append(filter.product_id)
    if filter.category:
        conditions.append("p.category = ?")
        params.append(filter.category)
    if filter.subcategory:
        conditions.append("p.subcategory = ?")
        params.append(filter.subcategory)
    if filter.region_id:
        conditions.append(f"{table_alias}.region_id = ?")
        params.append(filter.region_id)
    if filter.channel_id:
        conditions.append(f"{table_alias}.channel_id = ?")
        params.append(filter.channel_id)
    if filter.start_date:
        conditions.append(f"{table_alias}.week_start >= ?")
        params.append(filter.start_date)
    if filter.end_date:
        conditions.append(f"{table_alias}.week_start <= ?")
        params.append(filter.end_date)
     
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    return where, params


def parse_period(period: str) -> tuple[str, str]:
    """Parse 'QN-YYYY' or 'YYYY-MM-DD..YYYY-MM-DD' into ISO (start, end)."""
    m = _QUARTER_RE.match(period)
    if m:
        q = int(m.group(1))
        year = int(m.group(2))
        start_month = (q -1) *3 + 1
        end_month = start_month + 2
        if end_month == 12:
            end= date(year, 12, 31)
        else:
            end = date(year, end_month + 1, 1) - timedelta(days=1)
        return f"{year}-{start_month:02d}-01", end.isoformat()
    
    m = _RANGE_RE.match(period)
    if m:
        return m.group(1), m.group(2)
    
    raise ValueError(
        f"Invalid period format: {period}. Use 'QN-YYYY' or 'YYYY-MM-DD..YYYY-MM-DD'."
    )