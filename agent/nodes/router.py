"""agent/nodes/router.py - First node of the graph.
Classifies the question, sets in_scope flag, and produces a refusal
message for out-of-scope questions so the finalizer can return a clean
structured response without ever calling the planner.
"""
from __future__ import annotations

from pathlib import Path
from typing import cast
from langchain_core.messages import HumanMessage, SystemMessage
from agent.llm import get_llm
from agent.state import AgentState, RouterDecision


_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "router.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


def router(state: AgentState) -> dict:
    """Return {'router_decision': RouterDecision, 'retry_count': 0}."""
    question = state.get("question", "")

    llm = get_llm(temperature=0.0, max_tokens=512).with_structured_output(RouterDecision)
    
    decision: RouterDecision = cast(RouterDecision, llm.invoke(
        [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"Question: {question}")
        ]
    ))
    return {
        "router_decision": decision,
        "retry_count": 0
    }



def route_after_router(state: AgentState) -> str:
    """Conditional edge function used by graph.add_conditional_edges."""
    decision= state.get("router_decision")
    if not decision:
        return "finalizer"
    return "planner" if decision.in_scope else "finalizer"