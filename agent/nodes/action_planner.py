"""agent/nodes/action_planner.py - Produce the ranked ActionPlan.

Given the Insight, produces 3 to 5 ranked Actions. Each action
references at least one Evidence ID from the insight, keeping
recommendations grounded in the verified facts.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage

from agent.llm import get_llm
from agent.state import AgentState
from api.schemas import ActionPlan


_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "action_planner.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


def action_planner(state: AgentState) -> dict:
    """Return {'action_plan': ActionPlan}."""
    question = state.get("question", "")
    insight = state.get("insight")
    if insight is None:
        raise RuntimeError(
            "action_planner called without an insight; check graph wiring"
        )

    evidence_lines = [
        f"- {ev.id}: metric={ev.metric}, value={ev.value}, "
        f"period={ev.period}, filter={ev.filter}"
        for ev in insight.evidence
    ]
    evidence_block = "\n".join(evidence_lines) if evidence_lines else "(none)"

    user_msg = (
        f"User question:\n{question}\n\n"
        f"Insight title: {insight.title}\n"
        f"Insight confidence: {insight.confidence}\n\n"
        f"Insight summary:\n{insight.summary}\n\n"
        f"Available Evidence IDs to cite via evidence_refs:\n{evidence_block}\n"
    )

    llm = get_llm(temperature=0.3, max_tokens=2000).with_structured_output(ActionPlan)
    action_plan = cast(
        ActionPlan,
        llm.invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=user_msg)
            ]
        ) 
    )
    return {"action_plan": action_plan}

