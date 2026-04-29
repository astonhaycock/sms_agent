"""
Trails agent — answers questions about hiking trails via SMS.
Fast paths handle the most common queries deterministically.
LLM agent handles anything more complex.
"""
import re
from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage, HumanMessage, AIMessage

from agent_router.llm_setup import invoke_with_tools
from agent_router.trails.data.registry import find_trail, list_trails, expand_path


TRAILS_SYSTEM = SystemMessage(content=(
    "You are a trail guide assistant over SMS. "
    "ALWAYS call a tool immediately — never respond with text alone. "
    "Call get_trail_overview for route lists, get_route_details for specific routes, "
    "get_trail_safety for safety info, get_trail_map for maps. "
    "Plain text only, no markdown, no emojis. Under 300 characters unless listing routes."
))

_MAX_ITERATIONS = 4


@tool
def get_trail_overview(trail_name: str) -> str:
    """Get an SMS-friendly overview of a trail with all route options listed.

    Args:
        trail_name: Name, alias, or park of the trail (e.g. 'Devils Garden', 'Zion Canyon').
    """
    trail = find_trail(trail_name)
    if not trail:
        names = ", ".join(t["name"] for t in list_trails())
        return f"Trail not found. Available: {names}"
    return trail["sms_overview"]


@tool
def get_route_details(trail_name: str, route: str) -> str:
    """Get details for a specific route on a trail.

    Args:
        trail_name: Name or alias of the trail.
        route: Route name, number (1-7), or keyword (e.g. 'landscape', 'double o', '3').
    """
    trail = find_trail(trail_name)
    if not trail:
        return f"Trail '{trail_name}' not found."

    routes = trail["routes"]
    r = route.strip().lower()

    if r.isdigit():
        idx = int(r) - 1
        matched = routes[idx] if 0 <= idx < len(routes) else None
    else:
        matched = next(
            (ro for ro in routes if r in ro["id"].lower() or r in ro["label"].lower()),
            None,
        )
    if not matched:
        return f"Route '{route}' not found. Ask for overview to see options."

    path_str = expand_path(trail, matched.get("path") or [])
    dist = matched.get("distance_note") or (
        f"{matched['distance_miles']} mi" if matched.get("distance_miles") else "varies"
    )
    avoid = ", ".join(matched["avoid_if"]) if matched.get("avoid_if") else "none"
    warnings = matched.get("warnings", [])

    lines = [f"{matched['label']} ({matched['route_type']})"]
    if path_str:
        lines.append(f"Path: {path_str}")
    lines.append(f"Dist: {dist} | {matched['difficulty']}")
    if matched.get("estimated_time"):
        lines.append(f"Time: {matched['estimated_time']}")
    lines.append(f"Avoid if: {avoid}")
    if warnings:
        lines.append(f"Warnings: {', '.join(warnings)}")
    if matched.get("summary"):
        lines.append(matched["summary"])

    return "\n".join(lines)


@tool
def get_trail_safety(trail_name: str) -> str:
    """Get safety tips for a trail.

    Args:
        trail_name: Name or alias of the trail.
    """
    trail = find_trail(trail_name)
    if not trail:
        return f"Trail '{trail_name}' not found."
    tips = trail.get("safety", [])
    return "\n".join(f"- {t}" for t in tips) if tips else "No safety info available."


@tool
def get_trail_map(trail_name: str) -> str:
    """Get an ASCII map of the trail system showing how paths connect.

    Args:
        trail_name: Name or alias of the trail.
    """
    trail = find_trail(trail_name)
    if not trail:
        return f"Trail '{trail_name}' not found."
    return trail.get("ascii_map", "No map available.")


@tool
def list_available_trails() -> str:
    """List all trails the agent knows about."""
    trails = list_trails()
    if not trails:
        return "No trail data available."
    lines = [f"- {t['name']} ({t.get('park', t['state'])})" for t in trails]
    return "Available trails:\n" + "\n".join(lines)


_tools = [get_trail_overview, get_route_details, get_trail_safety, get_trail_map, list_available_trails]
_tool_node = ToolNode(_tools)

# ---------------------------------------------------------------------------
# Fast-path intent detection
# ---------------------------------------------------------------------------

def _detect_intent(text: str):
    """
    Returns (action, trail) or None if no clear match.
    action: 'overview' | 'map' | 'safety' | None

    Returns None when the user is asking about a *specific* route (e.g. "route 3"),
    so the LLM agent can pick the right route via get_route_details.
    """
    t = text.lower()
    trail = find_trail(t)
    if not trail:
        return None

    if any(w in t for w in ("map", "ascii", "layout", "diagram")):
        return ("map", trail)
    if any(w in t for w in ("safety", "safe", "danger", "warning", "tips")):
        return ("safety", trail)
    # Specific-route phrasings (e.g. "route 3", "the landscape route") — let the LLM pick.
    if re.search(r"\broute\s+(?:\d+|[a-z]+)\b", t) or re.search(r"\b(?:route|hike|trail)\s+\d+\b", t):
        return None
    # Default for bare trail-name queries: overview
    return ("overview", trail)


def _direct_tool_result(action: str, trail: dict) -> str:
    if action == "map":
        return trail.get("ascii_map", "No map available.")
    if action == "safety":
        tips = trail.get("safety", [])
        return "\n".join(f"- {t}" for t in tips) if tips else "No safety info."
    return trail.get("sms_overview", "No overview available.")


# ---------------------------------------------------------------------------
# LangGraph agent (used when fast path doesn't apply)
# ---------------------------------------------------------------------------

class TrailsState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


def _call_llm(state: TrailsState) -> TrailsState:
    msgs = state["messages"]
    if not msgs or msgs[0] is not TRAILS_SYSTEM:
        msgs = [TRAILS_SYSTEM] + [m for m in msgs if m is not TRAILS_SYSTEM]
    first_turn = not any(isinstance(m, ToolMessage) for m in msgs)
    response = invoke_with_tools(msgs, _tools, require_tool=first_turn)
    return {"messages": [response]}


def _should_continue(state: TrailsState) -> str:
    msgs = state["messages"]
    if not msgs[-1].tool_calls:
        return END
    tool_calls_so_far = sum(1 for m in msgs if isinstance(m, ToolMessage))
    if tool_calls_so_far >= _MAX_ITERATIONS:
        return END
    return "tools"


graph_builder = StateGraph(TrailsState)
graph_builder.add_node("agent", _call_llm)
graph_builder.add_node("tools", _tool_node)
graph_builder.add_edge(START, "agent")
graph_builder.add_conditional_edges("agent", _should_continue, ["tools", END])
graph_builder.add_edge("tools", "agent")

trails_agent = graph_builder.compile()


def run_trails_agent(messages: list[BaseMessage]) -> dict:
    """Entry point called by the router. Fast path for common intents."""
    last_human = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )

    intent = _detect_intent(last_human)
    if intent:
        action, trail = intent
        result = _direct_tool_result(action, trail)
        return {"messages": [AIMessage(content=result)]}

    return trails_agent.invoke({"messages": messages})
