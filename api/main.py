"""api/main.py - FastAPI service wrapping the ShelfPulse agent.

The app is intentionally thin. All business logic lives in the agent
graph and the storage layer; this module only handles HTTP plumbing,
guardrails, and response serialization.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Union

import duckdb
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from agent.graph import build_graph
from agent.guardrails import check_input
from agent.observability import setup_phoenix
from api.schemas import AskRequest, AskResponse, RefusalResponse
from api.storage import get_action_plan, get_insight
from mcp_server.config import settings


log = logging.getLogger("shelfpulse.api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot Phoenix and the graph once at startup."""
    log.info("Starting Phoenix...")
    app.state.phoenix = setup_phoenix()
    
    log.info("Building ShelfPulse agent graph...")
    app.state.graph = build_graph()
    log.info("Graph compiled.")
    yield


app = FastAPI(
    title="ShelfPulse",
    description="LangGraph-powered CPG sales-insight agent.",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/healthz")
def healthz() -> dict:
    """Liveness probe. Checks DuckDB readability and ANTHROPIC_API_KEY presence."""
    status: dict[str, str] = {"status": "ok"}

    # Anthropic key
    if not os.getenv("ANTHROPIC_API_KEY"):
        status["status"] = "degraded"
        status["anthropic_key"] = "missing"
    else:
        status["anthropic_key"] = "present"

    # DuckDB
    try:
        conn = duckdb.connect(str(settings.db_path), read_only=True)
        rows = conn.execute("SELECT COUNT(*) FROM weekly_sales").fetchone()
        conn.close()
        status["warehouse_rows"] = str(rows[0] if rows else 0)
    except Exception as exc:  # noqa: BLE001
        status["status"] = "degraded"
        status["warehouse"] = f"unreachable: {exc}"

    return status


@app.post("/ask", response_model=None)
async def ask(req: AskRequest) -> Union[AskResponse, RefusalResponse]:
    """Run the agent on a user question. Returns either a full answer or a refusal."""
    refusal = check_input(req.question)
    if refusal is not None:
        return refusal
    
    graph = app.state.graph
    result = await graph.ainvoke({"question": req.question})

    decision = result.get("router_decision")
    trace_id = result.get("trace_id", "unknown")

    # Out-of-scope refusal coming back from the agent's router node.
    if decision is None or not decision.in_scope:
        return RefusalResponse(
            trace_id=trace_id,
            reason="out_of_scope",
            message=(
                decision.refusal_message
                if decision and decision.refusal_message
                else "Question is outside the ShelfPulse scope."
            ),
        )
    
    insight = result.get("insight")
    action_plan = result.get("action_plan")
    if insight is None or action_plan is None:
        raise HTTPException(
            status_code=500,
            detail=f"Agent finished without producing an insight or action plan (trace_id={trace_id})."
        )
    
    return AskResponse(
        trace_id=trace_id,
        insight=insight,
        action_plan=action_plan,
        low_confidence=bool(result.get("low_confidence", False)),
    )



@app.get("/insights/{trace_id}", response_model=None)
def fetch_insight(trace_id: str) -> JSONResponse:
    """Fetch a persisted Insight by trace_id."""
    ins = get_insight(trace_id)
    if ins is None:
        raise HTTPException(status_code=404, detail=f"No insight for trace_id={trace_id}")
    return JSONResponse(content=ins.model_dump(mode="json"))


@app.get("/actions/{trace_id}", response_model=None)
def fetch_action_plan(trace_id: str) -> JSONResponse:
    """Fetch a persisted ActionPlan by trace_id."""
    ap = get_action_plan(trace_id)
    if ap is None:
        raise HTTPException(status_code=404, detail=f"No action plan for trace_id={trace_id}")
    return JSONResponse(content=ap.model_dump(mode="json"))