"""agent/nodes/finalizer.py - Terminal node.

Stamps the trace_id, finish timestamp, and low_confidence flag.
Persistence happens here so the graph result is the source of truth
for the API layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from agent.state import AgentState
from api.storage import save_run


def finalizer(state: AgentState) -> dict:
    """Return finalized state fields and persist the run."""
    trace_id = state.get("trace_id") or uuid.uuid4().hex[:12]
    finished_at = datetime.now(timezone.utc)

    insight = state.get("insight")
    action_plan = state.get("action_plan")
    low_confidence = bool(state.get("low_confidence", False))

    # Insight is missing only on out-of-scope refusals. Question may be
    # answerable but the action plan is independent.
    save_run(
        trace_id=trace_id,
        question=state.get("question", ""),
        insight=insight,
        action_plan=action_plan,
        low_confidence=low_confidence,
        full_state=dict(state)
    )

    return{
        "trace_id": trace_id,
        "finished_at": finished_at,
        "low_confidence": low_confidence
    }