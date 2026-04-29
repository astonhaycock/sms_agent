"""
Shared utilities for RAG agents that load PDFs into a FAISS index and serve
answers via a LangGraph node.  Used by camping_advice and firstAid (and any
future domain that follows the same pattern).
"""
from pathlib import Path
from typing import Annotated
import operator

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

from agent_router.llm_setup import embeddings, get_llm

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


# ---------------------------------------------------------------------------
# Vector-store builder
# ---------------------------------------------------------------------------

def build_faiss_index(
    pdf_dir: Path,
    vector_dir: Path,
    index_name: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> None:
    """Load all PDFs from pdf_dir, embed them, and persist a FAISS index."""
    if not pdf_dir.exists():
        raise FileNotFoundError(f"PDF directory not found: {pdf_dir}")

    print("Loading PDFs from", pdf_dir)
    docs = []
    for path in sorted(pdf_dir.glob("*.pdf")):
        loader = PyPDFLoader(str(path))
        pages = loader.load()
        for d in pages:
            d.metadata["source_file"] = path.name
        docs.extend(pages)
    print(f"Loaded {len(docs)} pages")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    print(f"Split into {len(chunks)} chunks")

    print("Embedding with nomic-embed-text:latest and writing to FAISS...")
    vector_dir.mkdir(parents=True, exist_ok=True)
    store = FAISS.from_documents(documents=chunks, embedding=embeddings)
    index_path = vector_dir / index_name
    store.save_local(str(index_path))
    print("Done. Vector store saved to", index_path)


# ---------------------------------------------------------------------------
# Retriever factory
# ---------------------------------------------------------------------------

def make_retriever_factory(vector_dir: Path, index_name: str, run_hint: str):
    """Return a get_retriever(k) function that lazily loads the FAISS index.

    Example:
        get_retriever = make_retriever_factory(VECTOR_DIR, "my_index", "uv run ...")
        retriever = get_retriever(k=5)
    """
    _store: list[FAISS | None] = [None]

    def get_retriever(k: int = 5):
        if _store[0] is None:
            index_path = vector_dir / index_name
            if not index_path.exists():
                raise FileNotFoundError(
                    f"Vector index not found at {index_path}. Run: {run_hint}"
                )
            _store[0] = FAISS.load_local(
                str(index_path),
                embeddings,
                allow_dangerous_deserialization=True,
            )
        return _store[0].as_retriever(search_kwargs={"k": k})

    return get_retriever


# ---------------------------------------------------------------------------
# LangGraph RAG agent builder
# ---------------------------------------------------------------------------

class _RAGState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


def _format_docs(docs) -> str:
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


def build_rag_graph(
    get_retriever,
    system_with_docs: str,
    system_no_docs: str,
    retriever_k: int = 6,
):
    """Build and compile a single-node RAG LangGraph.

    Args:
        get_retriever:    A callable(k) that returns a LangChain retriever.
        system_with_docs: System prompt used when context docs are found.
                          The docs are appended as a '## Context' section.
        system_no_docs:   System prompt used when no docs are found.
        retriever_k:      Number of chunks to retrieve per query.
    """

    def agent_node(state: _RAGState) -> _RAGState:
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            state["messages"][-1],
        )
        user_content = last_human.content
        if not isinstance(user_content, str):
            user_content = str(user_content)

        try:
            docs = get_retriever(k=retriever_k).invoke(user_content)
        except Exception:
            docs = []

        if docs:
            context = _format_docs(docs)
            prompt = (
                f"{system_with_docs}\n\n"
                f"## Context from manuals\n\n{context}\n\n"
                f"## User question\n\n{user_content}"
            )
            messages = [HumanMessage(content=prompt)]
        else:
            messages = [SystemMessage(content=system_no_docs), last_human]

        response = get_llm().invoke(messages)
        return {"messages": [response]}

    graph_builder = StateGraph(_RAGState)
    graph_builder.add_node("agent", agent_node)
    graph_builder.add_edge(START, "agent")
    graph_builder.add_edge("agent", END)
    return graph_builder.compile()
