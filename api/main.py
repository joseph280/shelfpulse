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
from fastapi.middleware.cors import CORSMiddleware

import duckdb
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from agent.graph import build_graph
from agent.guardrails import check_input
from agent.observability import current_trace_id, setup_phoenix
from api.schemas import AskRequest, AskResponse, RefusalResponse
from api.storage import get_action_plan, get_insight
from mcp_server.config import settings


log = logging.getLogger("shelfpulse.api")

# Shared password gate. The frontend is public, so the password is enforced
# server-side here (not just in the browser) to protect paid LLM calls.
APP_PASSWORD = os.getenv("APP_PASSWORD", "shelfpulse")


def require_password(x_app_password: str | None = Header(default=None)) -> None:
    """FastAPI dependency: reject requests without the correct X-App-Password header."""
    if x_app_password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid or missing password.")

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

# Origins are env-driven so the deployed frontend (e.g. a *.vercel.app domain)
# can be allowed without a code change. Comma-separated list, or "*" for any.
# Defaults to the local Next.js dev server.
_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").strip()
_allow_origins = ["*"] if _origins_env == "*" else [
    o.strip() for o in _origins_env.split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    # No cookies are used; auth travels in the X-App-Password header. Keeping
    # credentials off lets us safely allow any origin/header for this demo.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/healthz")
def healthz() -> dict:
    """Liveness probe. Checks DuckDB readability and the LLM key for the
    configured provider (anthropic / groq / google)."""
    status: dict[str, str] = {"status": "ok"}

    # LLM key for whichever provider is active.
    provider = os.getenv("SHELFPULSE_PROVIDER", "anthropic").lower()
    key_var = {
        "anthropic": "ANTHROPIC_API_KEY",
        "groq": "GROQ_API_KEY",
        "google": "GOOGLE_API_KEY",
    }.get(provider, "ANTHROPIC_API_KEY")
    status["llm_provider"] = provider
    if not os.getenv(key_var):
        status["status"] = "degraded"
        status["llm_key"] = f"{key_var} missing"
    else:
        status["llm_key"] = f"{key_var} present"

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


@app.get("/verify")
def verify(_: None = Depends(require_password)) -> dict:
    """Password check for the frontend gate. 200 if correct, 401 otherwise."""
    return {"ok": True}


@app.post("/ask", response_model=None)
async def ask(
    req: AskRequest, _: None = Depends(require_password)
) -> Union[AskResponse, RefusalResponse]:
    """Run the agent on a user question. Returns either a full answer or a refusal."""
    refusal = check_input(req.question)
    if refusal is not None:
        return refusal

    graph = app.state.graph

    # Run the graph inside a single OTEL span so every downstream LLM/tool span
    # shares one trace, and capture that trace ID for deep-linking into Phoenix.
    try:
        from opentelemetry import trace as otel_trace

        with otel_trace.get_tracer("shelfpulse.api").start_as_current_span("ask"):
            result = await graph.ainvoke({"question": req.question})
            phoenix_trace_id = current_trace_id()
    except ImportError:
        result = await graph.ainvoke({"question": req.question})
        phoenix_trace_id = None

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
            phoenix_trace_id=phoenix_trace_id,
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
        phoenix_trace_id=phoenix_trace_id,
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