from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage

from agent_router.llm_setup import invoke_with_tools
from agent_router.weather.tools.weather_api import get_coordinates, get_weather, get_rain_stop_estimate


class WeatherState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


tools = [get_coordinates, get_weather, get_rain_stop_estimate]
tool_node = ToolNode(tools)

WEATHER_SYSTEM = SystemMessage(content=(
    "You are an SMS weather bot. "
    "ALWAYS call get_coordinates first to get lat/lon, then call get_weather. "
    "For rain-stop questions call get_rain_stop_estimate instead of get_weather. "
    "Never respond with text until you have tool results. "
    "Final reply: plain text, no markdown, no emojis, under 200 characters. "
    "Show today and tomorrow only. Example: St. George today 87/55F clear, tomorrow 80/52F cloudy."
))

_MAX_ITERATIONS = 6


def call_llm(state: WeatherState) -> WeatherState:
    messages = state["messages"]
    # Always lead with the weather system prompt. Other SystemMessages (e.g. carrier
    # location injected by the router) follow it as additional context.
    if not messages or messages[0] is not WEATHER_SYSTEM:
        messages = [WEATHER_SYSTEM] + [m for m in messages if m is not WEATHER_SYSTEM]

    # Force a tool call on the first LLM turn (no prior tool results in history)
    first_turn = not any(isinstance(m, ToolMessage) for m in messages)
    response = invoke_with_tools(messages, tools, require_tool=first_turn)
    return {"messages": [response]}


def should_continue(state: WeatherState) -> str:
    msgs = state["messages"]
    last = msgs[-1]
    if not last.tool_calls:
        return END
    # Safety cap — prevent infinite loops
    tool_calls_so_far = sum(1 for m in msgs if isinstance(m, ToolMessage))
    if tool_calls_so_far >= _MAX_ITERATIONS:
        return END
    return "tools"


graph_builder = StateGraph(WeatherState)
graph_builder.add_node("agent", call_llm)
graph_builder.add_node("tools", tool_node)
graph_builder.add_edge(START, "agent")
graph_builder.add_conditional_edges("agent", should_continue, ["tools", END])
graph_builder.add_edge("tools", "agent")

weather_agent = graph_builder.compile()
