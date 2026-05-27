"""agent/nodes/planner.py - Produces the ordered ToolPlan."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage

from agent.llm import get_llm
from agent.state import AgentState, ToolPlan


_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "planner.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


def planner(state: AgentState) -> dict:
    """Return {'plan': ToolPlan, 'retry_count': n}."""
    question = state.get("question", "")
    decision = state.get("router_decision")
    if decision is  None: 
        raise RuntimeError("planner called without router_decision")
    retry_count = state.get("retry_count", 0)
    feedback = "\n".join(state.get("errors", []))

    today = "2026-05-18"

    user_msg = (
        f"Today is {today}.\n"
        f"Question: {question}\n"
        f"Question type: {decision.question_type}\n"
        f"Suggested tools (non-binding): {decision.required_tools}\n"
    )
    if feedback:
        user_msg += (
            "\nPrevious attempt produced mismatches. Adjust the plan "
            f"to address this feedback:\n{feedback}\n"
        )

    llm = get_llm(temperature=0.0, max_tokens=1024).with_structured_output(ToolPlan)
    plan = cast(
        ToolPlan,
        llm.invoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=user_msg),
            ]
        ),
    )
    return {"plan": plan, "retry_count": retry_count}