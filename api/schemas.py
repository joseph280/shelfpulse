"""API-layer request/response schemas.
 
Imports closed enums and shared types from mcp_server.models. The Evidence
model is the contract between the LLM (which writes it) and the validator
node (which re-runs the cited tool). Keeping its fields aligned with the
MCP tool surface is what makes claim verification mechanical.
"""
 
from __future__ import annotations
 
from datetime import datetime

from typing import Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mcp_server.models import MetricName, ToolName



# Request
class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid") # Prevents arbitrary parameters
    question: str = Field(..., min_length=3, max_length=2000) 
    max_tokens: int = Field(default=25_000, ge=1_000, le=100_000)
    temperature: float = Field(0.2, ge=0.0, le=1.0)


#Evidence: The validator's contract
class Evidence(BaseModel):
    """A single numeric claim with enough info for the validator to re-run.
 
    The validator node reads evidence[*], calls source_tool with (filter,
    period), and compares the returned value to this value within 1 percent
    tolerance. Mismatches kick state back to the planner.
    """
    id: str = Field(pattern=r"^ev-\d+$", description="Unique evidence ID tag, e.g., ev-1")
    metric: str
    value: float
    period: str = Field(min_length=2, max_length=32) # matches Period.label
    filter: Dict[str,str] = Field(description="Flat key/value filter, e.g. {'region_id': 'NE', 'category': 'beverage'}")
    source_tool: ToolName

#Insight: output of insight_builder node
class Insight(BaseModel):
    model_config = ConfigDict(extra="forbid") # Prevents arbitrary parameters

    id: str = Field(pattern=r"^ins-[0-9a-f]{8,}$")
    title: str = Field(min_length=5, max_length=120)
    summary: str = Field(min_length=5, max_length=120, description="3-5 senteces sysnthesis where every numeric claim references an evidence id")
    evidence: List[Evidence] = Field(min_length=1, max_length=10)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_unique_evidence_ids(self) -> "Insight":
        ids = [e.id for e in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("Evidence IDs must be unique within an insight")
        return self


#Action Plan: output of action_planner node
ActionLever = Literal['promo', 'assortment', 'price', 'distribution', 'planogram', 'supply']

OwnerRole = Literal['Category Manager', 'Demand Planner', 'Trade Marketing', 'Supply Chain']


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid") # Prevents arbitrary parameters

    rank: int = Field(ge=1, le=5)
    lever: ActionLever
    description: str = Field(min_length=15, max_length=500)
    expected_impact_low_usd: float
    expected_impact_high_usd: float
    confidence: float = Field(..., ge=0.0, le=1.0)
    owner_role: OwnerRole
    evidence_refs: List[str] = Field(min_length=1, description="List of evidence IDs that support this action, e.g. ['ev-1', 'ev-2']")


    @model_validator(mode="after")
    def _check_impact_range(self) -> "Action":
        if self.expected_impact_high_usd < self.expected_impact_low_usd:
            raise ValueError("expected_impact_high_usd must be greater than or equal to expected_impact_low_usd")
        return self


class ActionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid") # Prevents arbitrary parameters

    id: str = Field(pattern=r"^ap-[0-9a-f]{8,}$")
    actions: List[Action] = Field(min_length=3, max_length=5)
    generated_at: datetime


    @model_validator(mode="after")
    def _check_ranks(self) -> "ActionPlan":
        ranks = sorted(a.rank for a in self.actions)
        expected = list(range(1, len(ranks) + 1))
        if ranks != expected:
            raise ValueError(f"Action ranks must be unique and sequential starting from 1. Found ranks: {ranks}")
        return self
    

# Top-level API response
class AskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid") # Prevents arbitrary parameters

    trace_id: str = Field(pattern=r"^[0-9a-f]{8,}$")
    insight: Insight
    action_plan: ActionPlan
    low_confidence: bool = False


class RefusalResponse(BaseModel):
    """Returned when the router classifies a question as out-of-scope."""
    model_config = ConfigDict(extra="forbid") # Prevents arbitrary parameters

    trace_id: str
    reason: Literal['out_of_scope', 'harmful', 'pii', "oversized_input"]
    message: str = Field(min_length=10, max_length=400)




__all__ = [
    "AskRequest",
    "Evidence",
    "Insight",
    "Action",
    "ActionPlan",
    "ActionLever",
    "OwnerRole",
    "AskResponse",
    "RefusalResponse"
]
