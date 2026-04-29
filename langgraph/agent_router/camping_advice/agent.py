"""
Camping and outdoors advice agent: answers from the camping and outdoors advice manual vector store (RAG).
No tools; retrieval is done inside the agent node.
"""
from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from agent_router.llm_setup import get_llm
from agent_router.camping_advice.retriever import get_camping_advice_retriever

# Retriever: k chunks per query
RETRIEVER_K = 6


class CampingAdviceState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


def _format_docs(docs):
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


def camping_advice_agent_node(state: CampingAdviceState) -> CampingAdviceState:
    """Retrieve relevant camping and outdoors advice chunks and answer using the LLM."""
    last_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        state["messages"][-1],
    )
    user_content = last_human.content
    if not isinstance(user_content, str):
        user_content = str(user_content)

    retriever = get_camping_advice_retriever(k=RETRIEVER_K)
    try:
        docs = retriever.invoke(user_content)
    except Exception:
        docs = []

    if docs:
        context = _format_docs(docs)
        system = (
            "You are a camping and outdoors advice assistant. Answer based on the following excerpts from camping and outdoors manuals. If the answer is not in the context, say so.\n\n"
            "Give clear, practical how-to steps. Assume the user is asking for normal camping skills (e.g. starting a fire, setting up camp, using a stove)—answer with straightforward instructions. "
            "Do NOT suggest signaling for help, calling for rescue, or evacuating unless the question is clearly about an emergency, injury, or dangerous situation.\n\n"
            "Keep answers clear and concise."
        )
        prompt = f"{system}\n\n## Context from manuals\n\n{context}\n\n## User question\n\n{user_content}"
        messages = [HumanMessage(content=prompt)]
    else:
        messages = [
            SystemMessage(
                content=(
                    "You are a camping and outdoors advice assistant for campers/outdoor users with limited resources. "
                    "No manual excerpts were found for this question. Give brief, practical advice if you can."
                )
            ),
            last_human,
        ]

    response = get_llm().invoke(messages)
    return {"messages": [response]}


graph_builder = StateGraph(CampingAdviceState)
graph_builder.add_node("agent", camping_advice_agent_node)
graph_builder.add_edge(START, "agent")
graph_builder.add_edge("agent", END)

camping_advice_agent = graph_builder.compile()
