import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (one level up from langgraph/)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Only enable Langfuse when configured and enabled (avoids connection refused when no Langfuse server, e.g. in Docker)
_langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
_langfuse_host = (os.getenv("LANGFUSE_HOST") or "").strip()
if _langfuse_enabled and _langfuse_host:
    from langfuse.langchain import CallbackHandler
    langfuse_handler = CallbackHandler()
else:
    langfuse_handler = None
