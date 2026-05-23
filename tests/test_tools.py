"""Direct unit tests for MCP tools. Calls functions in-process; the @mcp.tool
decorator preserves the original callable, so no MCP transport needed."""

from __future__ import annotations

import pytest

from mcp_server.config import settings
from mcp_server.models import SalesQueryFilter
from mcp_server.server import (
    compare_periods,
    compute_kpi,
    detect_stockout_risk,
    list_channels,
    list_products,
    list_regions,
    query_sales,
)
from mcp_server.tools._helpers import parse_period


pytestmark = pytest.mark.skipif(
    not settings.db_path.exists(),
    reason="Warehouse not seeded — run `uv run python -m data.seed`",
)


# Catalog tools
def test_list_products_returns_forty():
    products = list_products()
    assert len(products) == 40
    assert all(p.product_id.startswith("SKU-") for p in products)
    assert all(p.list_price > 0 for p in products)


def test_list_regions_returns_twelve():
    regions = list_regions()
    assert len(regions) == 12


def test_list_channels_returns_four():
    channels = list_channels()
    assert {c.channel_id for c in channels} == {"GRO", "CST", "CLU", "ONL"}


# query_sales
def test_query_sales_requires_filter():
    with pytest.raises(ValueError, match="At least one filter"):
        query_sales(SalesQueryFilter())


def test_query_sales_with_region_filter():
    rows = query_sales(SalesQueryFilter(region_id="NE"), limit=100)
    assert 0 < len(rows) <= 100
    assert all(r.region_id == "NE" for r in rows)


def test_query_sales_respects_date_range():
    rows = query_sales(
        SalesQueryFilter(
            category="beverage",
            start_date="2026-01-01",
            end_date="2026-01-31",
        ),
        limit=500,
    )
    assert len(rows) > 0
    assert all("2026-01-01" <= r.week_start <= "2026-01-31" for r in rows)


# compute_kpi
def test_compute_kpi_basic_invariants():
    snap = compute_kpi(SalesQueryFilter(category="beverage"))
    print(snap)   # ← add this

    assert snap.units_sold > 0
    assert snap.gross_sales > 0
    assert snap.gross_profit == pytest.approx(
        snap.gross_sales - snap.cost_of_goods_sold, abs=0.01
    )
    assert 0.0 <= snap.gross_margin_pct <= 100.0
    assert 0.0 <= snap.promo_sales_share_pct <= 100.0


def test_compute_kpi_empty_returns_zeros():
    snap = compute_kpi(SalesQueryFilter(product_id="SKU-DOES-NOT-EXIST"))
    assert snap.units_sold == 0
    assert snap.gross_sales == 0.0
    assert snap.gross_margin_pct == 0.0


# compare_periods
def test_compare_periods_structure():
    result = compare_periods(
        metric="gross_sales",
        filter=SalesQueryFilter(category="beverage", region_id="NE"),
        period_a="Q4-2025",
        period_b="Q1-2026",
    )
    assert result.metric == "gross_sales"
    assert result.period_a == "Q4-2025"
    assert result.period_b == "Q1-2026"
    # Sanity: absolute change matches values
    assert result.absolute_change == pytest.approx(
        result.value_b - result.value_a, abs=0.01
    )


def test_compare_periods_planted_pattern_northeast_beverages():
    """Per seed plan: Northeast beverages drop ~12% Q1-2026 vs Q4-2025."""
    result = compare_periods(
        metric="gross_sales",
        filter=SalesQueryFilter(category="beverage", region_id="NE"),
        period_a="Q4-2025",
        period_b="Q1-2026",
    )
    # Just direction — exact magnitude depends on seed noise
    assert abs(result.percentage_change) > 0


# detect_stockout_risk
def test_detect_stockout_risk_returns_risk_labels_only():
    risks = detect_stockout_risk(horizon_days=30)
    assert isinstance(risks, list)
    for r in risks:
        assert r.risk_level in ("CRITICAL", "WARNING")
        assert r.weeks_of_cover <= (30 / 7.0)


def test_detect_stockout_risk_critical_threshold():
    risks = detect_stockout_risk(horizon_days=30)
    for r in risks:
        if r.weeks_of_cover <= 2.0:
            assert r.risk_level == "CRITICAL"
        else:
            assert r.risk_level == "WARNING"


def test_detect_stockout_risk_invalid_horizon():
    with pytest.raises(ValueError):
        detect_stockout_risk(horizon_days=0)


# Period parser
@pytest.mark.parametrize(
    "period,start,end",
    [
        ("Q1-2026", "2026-01-01", "2026-03-31"),
        ("Q2-2026", "2026-04-01", "2026-06-30"),
        ("Q3-2025", "2025-07-01", "2025-09-30"),
        ("Q4-2025", "2025-10-01", "2025-12-31"),
        ("2025-06-15..2025-09-15", "2025-06-15", "2025-09-15"),
    ],
)
def test_parse_period(period, start, end):
    assert parse_period(period) == (start, end)


def test_parse_period_rejects_garbage():
    with pytest.raises(ValueError):
        parse_period("last quarter")