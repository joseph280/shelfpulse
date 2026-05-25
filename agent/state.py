"""agent/state.py - LangGraph state for ShelfPulse.

AgentState flows through every node. Each node returns a partial dict
that LangGraph merges into the state. `total=False` makes every field
optional so nodes can add fields incrementally.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

from api.schemas import ActionPlan, Evidence, Insight


# Agent-internal models (LLM-produced via with_structured_output)

QuestionType = Literal["kpi", "comparison", "ranking", "root_cause", "restock"]


class RouterDecision(BaseModel):
    """First-pass classification of the user question."""

    in_scope: bool
    question_type: QuestionType | None = None
    required_tools: list[str] = Field(default_factory=list)
    refusal_message: str | None = None # populated only when in_scope=False


class ToolCall(BaseModel):
    """A single planned MCP tool invocation."""

    id: str # 'call-1', 'call-2', etc.
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolPlan(BaseModel):
    """Ordered sequence of tool calls produced by the planner."""

    calls: list[ToolCall] = Field(min_length=1, max_length=8)
    resoning: str | None = None


# LangGraph state
class AgentState(TypedDict, total=False):
    """Shared state passed between every LangGraph node."""

    question: str
    router_decision: RouterDecision
    plan: ToolPlan
    tool_calls: list[ToolCall]
    raw_results: dict[str, Any]
    verified_facts: list[Evidence]
    insight: Insight
    action_plan: ActionPlan
    errors: list[str]
    retry_count: int
    started_at: datetime
    finished_at: datetime
    low_confidence: bool

