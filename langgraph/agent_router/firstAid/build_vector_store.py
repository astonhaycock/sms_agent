"""
Build the first-aid vector store from PDFs in firstAid/pdf/.
Uses Ollama nomic-embed-text:latest and persists a FAISS index to vector-database/.

Run from langgraph dir: uv run python -m agent_router.firstAid.build_vector_store
Or: cd agent_router/firstAid && python build_vector_store.py (with PYTHONPATH set)
"""
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

from agent_router.llm_setup import embeddings

# Paths relative to this file
FIRST_AID_DIR = Path(__file__).resolve().parent
PDF_DIR = FIRST_AID_DIR / "pdf"
VECTOR_DIR = FIRST_AID_DIR / "vector-database"
FAISS_INDEX = "first_aid_index"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def load_pdfs() -> list:
    """Load all PDFs from firstAid/pdf/ into LangChain documents."""
    docs = []
    if not PDF_DIR.exists():
        raise FileNotFoundError(f"PDF directory not found: {PDF_DIR}")
    for path in sorted(PDF_DIR.glob("*.pdf")):
        loader = PyPDFLoader(str(path))
        pages = loader.load()
        for d in pages:
            d.metadata["source_file"] = path.name
        docs.extend(pages)
    return docs


def main():
    print("Loading PDFs from", PDF_DIR)
    raw_docs = load_pdfs()
    print(f"Loaded {len(raw_docs)} pages")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(raw_docs)
    print(f"Split into {len(chunks)} chunks")

    print("Embedding with nomic-embed-text:latest and writing to FAISS...")
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    vector_store = FAISS.from_documents(
        documents=chunks,
        embedding=embeddings,
    )
    index_path = VECTOR_DIR / FAISS_INDEX
    vector_store.save_local(str(index_path))
    print("Done. Vector store saved to", index_path)


if __name__ == "__main__":
    main()
