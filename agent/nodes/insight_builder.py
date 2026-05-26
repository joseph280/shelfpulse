"""agent/nodes/insight_builder.py - Produce the structured Insight.

Constrained to cite only Evidence rows from state['verified_facts'].
The validator already verified the numbers; this node writes the
narrative around them. Per-SKU detail from raw_results is allowed for
color but every numeric claim in the summary requires an evidence id.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
import uuid

from langchain_core.messages import HumanMessage, SystemMessage

from agent.llm import get_llm
from agent.state import AgentState
from agent.tool_client import unwrap_result
from api.schemas import Insight


_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "insight.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


def _summarize_raw_rows(raw_results: dict, plan_calls) -> str:
    """Compact per-SKU narrative context for the LLM.

    For each query_sales call, aggregate units_sold and gross_sales
    per product_id so the LLM sees totals, not 1000 rows. Other tool
    outputs are skipped here (they are already represented in the
    evidence list).
    """
    call_index = {c.id: c for c in plan_calls}
    chunks: list[str] = []

    for call_id, raw in raw_results.items():
        call = call_index.get(call_id)
        if call is None or call.tool_name != "query_sales":
            continue
        try:
            rows = unwrap_result(raw)
        except Exception:
            continue
        if not isinstance(rows, list):
            continue

        per_sku: dict[str, dict[str, float]] = {}
        for r in rows:
            pid = r.get("product_id", "?")
            agg = per_sku.setdefault(pid, {"units_sold": 0.0, "gross_sales": 0.0})
            agg["units_sold"] += float(r.get("units_sold", 0))
            agg["gross_sales"] += float(r.get("gross_sales", 0.0))

        ranked = sorted(per_sku.items(), key=lambda kv: kv[1]["gross_sales"], reverse=True)
        filter_str = json.dumps(call.arguments.get("filter", {}))
        chunks.append(f"\nquery_sales {call.id} filter={filter_str}:")
        for pid, agg in ranked[:10]:
            chunks.append(
                f"  {pid}: units_sold={int(agg['units_sold'])}, "
                    f"gross_sales={agg['gross_sales']:.2f}"
            )
    
    return "\n".join(chunks) if chunks else "(no per-SKU rows available)"



def insight_builder(state: AgentState) -> dict:
    """Return {'insight': Insight}."""
    question = state.get("question", "")
    verified_facts = state.get("verified_facts", [])
    raw_results = state.get("raw_results", {})
    plan = state.get("plan")
    if plan is None:
        raise RuntimeError(
            "insight_builder called without a plan; check graph wiring"
        )

    evidence_lines = [
        f"- {ev.id}: metric={ev.metric}, value={ev.value}, "
        f"period={ev.period}, filter={ev.filter}, tool={ev.source_tool}"
        for ev in verified_facts
    ]
    evidence_block = (
        "\n".join(evidence_lines) if evidence_lines else "(no verified evidence)"
    )

    per_sku_block = _summarize_raw_rows(raw_results, plan.calls)

    user_msg = (
        f"User question:\n{question}\n\n"
        f"Verified Evidence rows:\n{evidence_block}\n\n"
        f"Per-SKU rows (for narrative color only):\n{per_sku_block}\n"
    )

    llm = get_llm(temperature=0.2, max_tokens=1500).with_structured_output(Insight)
    insight = cast(
        Insight,
        llm.invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=user_msg)
            ]
        )
    )
    insight.id = f"ins-{uuid.uuid4().hex[:8]}" 
    return {"insight": insight}