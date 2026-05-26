"""agent/graph.py - Build and compile the ShelfPulse LangGraph.

Edges:
    router  --in_scope=false--> finalizer (refusal path)
    router  --in_scope=true--> planner
    planner --> tool_executor
    tool_executor --> validator
    validator --> insight_builder
    insight_builder --> action_planner
    action_planner --> finalizer
    finalizer --> END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from agent.nodes.action_planner import action_planner
from agent.nodes.finalizer import finalizer
from agent.nodes.insight_builder import insight_builder
from agent.nodes.planner import planner
from agent.nodes.router import route_after_router, router
from agent.nodes.tool_executor import tool_executor
from agent.nodes.validator import validator
from agent.state import AgentState
from api.storage import init_db

def build_graph():
    """Build, compile, and return the ShelfPulse agent graph."""
    init_db()

    g: StateGraph = StateGraph(AgentState)

    g.add_node("router", router)
    g.add_node("planner", planner)
    g.add_node("tool_executor", tool_executor)
    g.add_node("validator", validator)
    g.add_node("insight_builder", insight_builder)
    g.add_node("action_planner", action_planner)
    g.add_node("finalizer", finalizer)

    g.set_entry_point("router")

    g.add_conditional_edges(
        "router",
        route_after_router,
        {
            "planner": "planner",
            "finalizer": "finalizer"
        }
    )

    g.add_edge("planner", "tool_executor")
    g.add_edge("tool_executor", "validator")
    g.add_edge("validator", "insight_builder")
    g.add_edge("insight_builder", "action_planner")
    g.add_edge("action_planner", "finalizer")
    g.add_edge("finalizer", END)

    return g.compile()
    
    

