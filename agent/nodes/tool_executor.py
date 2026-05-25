"""agent/nodes/tool_executor.py - Execute the planned MCP tool calls.

Sequential execution keeps the Phoenix trace readable and avoids race
conditions in the validator. Errors are captured into state['errors']
but this node never retries — the validator owns the retry decision.
"""

from __future__ import annotations

from typing import Any

from agent.state import AgentState
from agent.tool_client import load_mcp_tools


async def tool_executor(state: AgentState) -> dict:
    """Return {'raw_results', 'errors', 'tool_calls'} — merged into state."""
    plan = state.get("plan")

    if plan is  None: 
        raise RuntimeError("tool_executor called without a plan; check graph wiring")


    existing_errors = list(state.get("errors", []))
    existing_calls = list(state.get("tool_calls", []))

    tools = await load_mcp_tools()
    tools_by_name = {t.name: t for t in tools}

    raw_results: dict[str, Any] = {}
    new_errors: list[str] = []

    for call in plan.calls:
        tool = tools_by_name.get(call.tool_name)
        if tool is None:
            new_errors.append(f"{call.id}: unknown tool {call.tool_name}")
            continue
        try:
            result = await tool.ainvoke(call.arguments)
            raw_results[call.id] = result
        except Exception as exc: 
            new_errors.append(f"{call.id}: {call.tool_name}: {exc}")

    return {
        "raw_results": raw_results,
        "errors": existing_errors + new_errors,
        "tool_calls": existing_calls + plan.calls,
    }