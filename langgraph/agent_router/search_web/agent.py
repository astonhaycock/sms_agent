"""
Search-web agent: DuckDuckGo search + one-shot LLM summarisation.
Replaces the CodeAgent loop with a direct search → summarise pipeline
to eliminate multi-step LLM overhead and page-scraping latency.
"""
from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from datetime import date

from agent_router.llm_setup import get_llm
from agent_router.search_web.tools.web_tools import WebSearchTool

_search_tool = WebSearchTool()

_SUMMARISE_SYSTEM = SystemMessage(content=(
    "You are a concise SMS assistant. "
    "Answer the user's question using only the search results provided. "
    "Plain text only, no markdown, no emojis. "
    "Be direct and factual. Under 300 characters unless a list is required."
))


class SearchWebState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


def search_web_node(state: SearchWebState) -> SearchWebState:
    """Search DuckDuckGo then summarise with a small LLM — one round trip."""
    # Find the last HumanMessage — system messages (e.g. location hints) may come after it
    last_msg = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        state["messages"][-1],
    )
    query = getattr(last_msg, "content", "") or str(last_msg)

    # Step 1: fetch search snippets (fast, no LLM)
    try:
        snippets = _search_tool.forward(query)
    except Exception as e:
        snippets = f"Search unavailable: {e}"

    # Step 2: single LLM call to synthesise an SMS-friendly answer
    today = date.today().strftime("%B %d, %Y")
    prompt = (
        f"Today is {today}.\n"
        f"Question: {query}\n\n"
        f"Search results:\n{snippets}\n\n"
        f"Answer using only current, relevant results. "
        f"If results look outdated compared to today's date, say so. "
        f"Plain text, under 300 characters."
    )
    try:
        llm = get_llm()
        response = llm.invoke([_SUMMARISE_SYSTEM, HumanMessage(content=prompt)])
        answer = (response.content or "").strip()
    except Exception as e:
        answer = snippets[:300] if snippets else f"Search error: {e}"

    return {"messages": [AIMessage(content=answer)]}


graph_builder = StateGraph(SearchWebState)
graph_builder.add_node("agent", search_web_node)
graph_builder.add_edge(START, "agent")
graph_builder.add_edge("agent", END)

search_web_agent = graph_builder.compile()
