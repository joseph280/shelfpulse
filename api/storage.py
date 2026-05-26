"""api/storage.py - SQLite persistence for completed agent runs.

Stores one row per /ask invocation. The whole AgentState (minus
non-serializable pieces) goes into a JSON blob; specific fields are
denormalized to columns for cheap lookup. This is intentionally a
single file with no migrations.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.schemas import ActionPlan, Insight


DB_PATH = Path(__file__).parent.parent / "warehouse" / "runs.sqlite"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the runs table if it does not exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                trace_id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                created_at TEXT NOT NULL,
                low_confidence INTEGER NOT NULL DEFAULT 0,
                insight_json TEXT,
                action_plan_json TEXT,
                state_json TEXT NOT NULL
            )
            """
        )


def save_run(
    trace_id: str,
    question: str,
    insight: Insight | None,
    action_plan: ActionPlan | None,
    low_confidence: bool,
    full_state: dict[str, Any]
) -> None:
    """Persist a completed run."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs
            (trace_id, question, created_at, low_confidence,
             insight_json, action_plan_json, state_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                question,
                datetime.now(timezone.utc).isoformat(),
                int(low_confidence),
                insight.model_dump_json() if insight else None,
                action_plan.model_dump_json() if action_plan else None,
                json.dumps(_jsonable(full_state))
            )
        )



def get_insight(trace_id: str) -> Insight | None:
    """Fetch the persisted Insight for a trace_id, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT insight_json FROM runs WHERE trace_id = ?", (trace_id,)
        ).fetchone()
        if row and row["insight_json"]:
            return Insight.model_validate_json(row["insight_json"])
    return None



def get_action_plan(trace_id: str) -> ActionPlan | None:
    """Fetch the persisted ActionPlan for a trace_id, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT action_plan_json FROM runs WHERE trace_id = ?", (trace_id,)
        ).fetchone()
        if row and row["action_plan_json"]:
            return ActionPlan.model_validate_json(row["action_plan_json"])
    return None



def _jsonable(value: Any) -> Any:
    """Recursively coerce Pydantic models, datetimes, and ToolCalls to JSON-safe forms."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value