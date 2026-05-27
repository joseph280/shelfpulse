"""agent/nodes/validator.py - Extract Evidence from raw tool results.

It does not call the LLM and does not trigger retries. 

Its sole job: take the raw MCP tool results from state['raw_results'] 
and materialize a list of Evidence objects thatthe insight_builder 
will be constrained to cite from.

Why this matters: by building Evidence BEFORE the insight LLM runs,
the insight builder can only reference numbers that came from real
tool calls. Hallucination of metric values becomes structurally
impossible.
"""

from __future__ import annotations

from typing import Any

from agent.state import AgentState
from agent.tool_client import unwrap_result
from api.schemas import Evidence


# Which fields in a KPISnapshot we want to surface as evidence.
# These are the metrics the insight builder may cite.
_KPI_METRICS = (
    "units_sold",
    "gross_sales",
    "cost_of_goods_sold",
    "gross_profit",
    "gross_margin_pct",
    "promo_sales_share_pct",
    "avg_discount_pct",
)


def _period_label(filter_dict: dict[str, Any]) -> str:
    """Build a short period label from a filter's date range."""
    start = filter_dict.get("start_date")
    end = filter_dict.get("end_date")
    if start and end:
        return f"{start}..{end}"
    if start:
        return f"from {start}"
    if end:
        return f"through {end}"
    return "all time"


def _filter_str_keys(filter_dict: dict[str, Any]) -> dict[str, str]:
    """Normalize a filter dict to {str: str} for the Evidence schema."""
    return {k: str(v) for k, v in filter_dict.items() if v is not None}


def validator(state: AgentState) -> dict:
    """Return {'verified_facts': list[Evidence]}.

    Iterates state['raw_results'], unwraps each, and converts known
    tool outputs into Evidence rows. Unknown tool outputs are skipped
    silently. "query_sales rows", l"ist_products", etc. are valuable to
    the insight LLM but they are not aggregate numeric claims, so
    they don't go in verified_facts.
    """
    plan = state.get("plan")
    raw_results = state.get("raw_results", {})
    if plan is  None: 
        raise RuntimeError("validator called without a plan; check graph wiring")   
    
    # Map call_id -> tool_name + arguments so we can attribute each result.
    call_index = {c.id: c for c in plan.calls}

    evidence: list[Evidence] = []
    ev_counter = 0


    def next_id() -> str:
        nonlocal ev_counter
        ev_counter += 1
        return f"ev-{ev_counter}"
    
    for call_id, raw in raw_results.items():
        call = call_index.get(call_id)
        if call is None:
            continue

        try:
            payload = unwrap_result(raw)
        except (ValueError, Exception):
            continue

        if call.tool_name == "compute_kpi":
            # payload is a single KPISnapshot dict
            filter_dict = call.arguments.get("filter", {}) or {}
            period = _period_label(filter_dict)
            filter_str = _filter_str_keys(filter_dict)
            for metric in _KPI_METRICS:
                if metric in payload:
                    evidence.append(
                        Evidence(
                            id=next_id(),
                            metric= metric,
                            value=float(payload[metric]),
                            period=period,
                            filter=filter_str,
                            source_tool="compute_kpi"
                        )
                    )
        elif call.tool_name == "compare_periods":
            # payload is a single PeriodComparison dict
            filter_dict = call.arguments.get("filter", {}) or {}
            filter_str = _filter_str_keys(filter_dict)
            metric = payload.get("metric", call.arguments.get("metric", "unknown"))

            evidence.append(
                Evidence(
                            id=next_id(),
                            metric= metric,
                            value=float(payload["value_a"]),
                            period=payload.get("period_a", "period_a"),
                            filter=filter_str,
                            source_tool="compare_periods"
                )
            )
            evidence.append(
                Evidence(
                            id=next_id(),
                            metric= metric,
                            value=float(payload["value_b"]),
                            period=payload.get("period_b", "period_b"),
                            filter=filter_str,
                            source_tool="compare_periods"
                )
            )
            evidence.append(
                Evidence(
                            id=next_id(),
                            metric= f"{metric}_pct_change",
                            value=float(payload["percentage_change"]),
                            period=f"{payload.get('period_a')} -> {payload.get('period_b')}",
                            filter=filter_str,
                            source_tool="compare_periods"
                )
            )
        elif call.tool_name == "detect_stockout_risk":
            rows = unwrap_result(raw)
            if isinstance(rows, list):
                # Cap at the 10 most critical (lowest weeks_of_cover) so we
                # stay within Insight.evidence max_length=10.
                rows = sorted(rows, key=lambda r: r.get("weeks_of_cover", 99))[:10]
                for row in rows:
                    evidence.append(Evidence(
                        id=f"ev-{ev_counter}",
                        metric="weeks_of_cover",
                        value=float(row.get("weeks_of_cover", 0)),
                        period="current",
                        filter={
                            "product_id": str(row.get("product_id", "")),
                            "region_id": str(row.get("region_id", "")),
                            "risk_level": str(row.get("risk_level", "")),
                        },
                        source_tool="detect_stockout_risk",
                    ))
                    ev_counter += 1

        # query_sales, list_products, list_regions, list_channels,
        # detect_stockout_risk: not aggregate numeric claims, skipped.
        # The insight builder will still see them via raw_results.


    return {"verified_facts": evidence}