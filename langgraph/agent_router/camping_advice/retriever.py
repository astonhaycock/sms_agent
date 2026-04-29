"""
First-aid vector store retriever. Loads the persisted FAISS index from vector-database/.
Ensure you have run build_vector_store.py once so the index exists.
"""
from pathlib import Path

from langchain_community.vectorstores import FAISS

from agent_router.llm_setup import embeddings

CAMPING_ADVICE_DIR = Path(__file__).resolve().parent
VECTOR_DIR = CAMPING_ADVICE_DIR / "vector-database"
FAISS_INDEX = "camping_advice_index"

# Lazy singleton so we don't hit disk on import
_vector_store = None


def get_vector_store() -> FAISS:
    """Return the FAISS vector store for camping and outdoors advice docs (persisted in vector-database/)."""
    global _vector_store
    if _vector_store is None:
        index_path = VECTOR_DIR / FAISS_INDEX
        if not index_path.exists():
            raise FileNotFoundError(
                f"Camping and outdoors advice vector index not found at {index_path}. "
                "Run: uv run python -m agent_router.camping_advice.build_vector_store"
            )
        _vector_store = FAISS.load_local(
            str(index_path),
            embeddings,
            allow_dangerous_deserialization=True,
        )
    return _vector_store


def get_camping_advice_retriever(k: int = 5):
    """Return a retriever over the camping and outdoors advice vector store. k = number of chunks per query."""
    return get_vector_store().as_retriever(search_kwargs={"k": k})
