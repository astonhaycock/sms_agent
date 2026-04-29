"""
First-aid agent: answers from the first-aid manual vector store (RAG).
No tools; retrieval is done inside the agent node.
"""
from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from agent_router.llm_setup import get_llm
from agent_router.firstAid.retriever import get_first_aid_retriever

# Retriever: k chunks per query
RETRIEVER_K = 6


class FirstAidState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


def _format_docs(docs):
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


def first_aid_agent_node(state: FirstAidState) -> FirstAidState:
    """Retrieve relevant first-aid chunks and answer using the LLM."""
    last_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        state["messages"][-1],
    )
    user_content = last_human.content
    if not isinstance(user_content, str):
        user_content = str(user_content)

    retriever = get_first_aid_retriever(k=RETRIEVER_K)
    try:
        docs = retriever.invoke(user_content)
    except Exception:
        docs = []

    disclaimer = "Not medical advice; seek professional help if in danger."

    if docs:
        context = _format_docs(docs)
        system = (
            "You are a first-aid assistant for people who are CAMPING or in the OUTDOORS with LIMITED resources. "
            "Answer ONLY based on the following excerpts from first-aid manuals. If the answer is not in the context, say so.\n\n"
            "IMPORTANT: Tailor your advice for someone who:\n"
            "- Has limited or basic supplies (maybe just water, cloth, tape, basic kit)\n"
            "- Cannot do complex procedures—focus on simple, practical steps they can do right there\n"
            "- May be far from help—say when they should try to get help, signal for rescue, or evacuate\n"
            "- Needs clear, short instructions (e.g. for SMS or high-stress situations)\n\n"
            "Prioritise: (1) what they can do now with what they have, (2) when to seek or signal for help, (3) what to avoid. "
            "Keep answers clear and concise. "
            f"End your reply with this exact line on its own: {disclaimer}"
        )
        prompt = f"{system}\n\n## Context from manuals\n\n{context}\n\n## User question\n\n{user_content}"
        messages = [HumanMessage(content=prompt)]
    else:
        messages = [
            SystemMessage(
                content=(
                    "You are a first-aid assistant for campers/outdoor users with limited resources. "
                    "No manual excerpts were found for this question. Give brief, practical advice if you can, "
                    "and always say when they should try to get help or signal for rescue. "
                    f"End your reply with this exact line on its own: {disclaimer}"
                )
            ),
            last_human,
        ]

    response = get_llm().invoke(messages)
    return {"messages": [response]}


graph_builder = StateGraph(FirstAidState)
graph_builder.add_node("agent", first_aid_agent_node)
graph_builder.add_edge(START, "agent")
graph_builder.add_edge("agent", END)

first_aid_agent = graph_builder.compile()
