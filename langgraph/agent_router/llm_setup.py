import os
import threading
from pathlib import Path
import dotenv

dotenv.load_dotenv()

from langchain_ollama import ChatOllama, OllamaEmbeddings

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
print(f"OLLAMA_BASE_URL: {OLLAMA_BASE_URL}")

# Smaller model used for lightweight tasks (e.g. Gmail summaries / tool calls)
_GMAIL_MODEL = os.getenv("GMAIL_LLM_MODEL", "gemma3:4b")

# Persist model selection so it survives StatReload restarts
_MODEL_FILE = Path(__file__).resolve().parents[2] / ".sms_agent_model"
_DEFAULT_MODEL = "glm-4.7-flash"

# Thread-local storage: allows per-request LLM without a global swap
_request_ctx = threading.local()


def _load_persisted_model() -> str:
    try:
        if _MODEL_FILE.exists():
            return _MODEL_FILE.read_text().strip() or _DEFAULT_MODEL
    except OSError:
        pass
    return _DEFAULT_MODEL


def _save_persisted_model(model: str) -> None:
    try:
        _MODEL_FILE.write_text(model)
    except OSError:
        pass


llm = None
_model_name = _load_persisted_model()


def get_llm():
    """Return per-request LLM if set (cloud provider), else global Ollama default."""
    return getattr(_request_ctx, "llm", None) or llm


def get_small_llm():
    """Return a lightweight Ollama model for low-resource tasks like Gmail summaries."""
    return ChatOllama(
        model=_GMAIL_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.3,
    )


def invoke_with_tools(messages, tools, require_tool: bool = False):
    """Invoke the current LLM with tools.

    - Falls back to the default local model if the selected model doesn't support tools.
    - If require_tool=True and the model responds with text instead of a tool call,
      nudges it once to force a tool call (handles models that chat on the first turn).
    """
    from langchain_core.messages import HumanMessage as _HM

    def _call(msgs):
        try:
            return get_llm().bind_tools(tools).invoke(msgs)
        except Exception as e:
            if "does not support tools" in str(e) or "status code: 400" in str(e):
                print(f"[llm_setup] '{_model_name}' does not support tools — falling back to {_DEFAULT_MODEL}")
                fallback = ChatOllama(model=_DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.3)
                return fallback.bind_tools(tools).invoke(msgs)
            raise

    response = _call(messages)

    if require_tool and not getattr(response, "tool_calls", None):
        tool_names = ", ".join(t.name for t in tools)
        nudge = _HM(content=f"You must call one of your tools now: {tool_names}. Do not respond with text.")
        response = _call(list(messages) + [response, nudge])

    return response


def get_model_name() -> str:
    return _model_name


def update_model(model: str):
    global llm, _model_name
    _model_name = model
    _save_persisted_model(model)
    llm = ChatOllama(
        model=model,
        base_url=OLLAMA_BASE_URL,
        temperature=0.3,
    )
    print(f"Model updated to {model}")


def set_request_llm(llm_instance) -> None:
    """Bind an LLM to the current thread for this request."""
    _request_ctx.llm = llm_instance


def clear_request_llm() -> None:
    """Remove any per-request LLM override."""
    _request_ctx.llm = None


# Default cloud model names (users can override via active_model setting)
_CLOUD_DEFAULTS = {
    "claude": "claude-3-5-haiku-20241022",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
}


def _default_provider() -> str:
    """Pick the default provider when a user has no `active_provider` setting."""
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "local"


def create_llm_for_user(user_id: int, db_ref):
    """Return the appropriate LLM for a user based on their active_provider setting."""
    if user_id is None:
        return llm

    provider = db_ref.get_user_setting(user_id, "active_provider") or _default_provider()

    if provider == "local":
        # Check if the user has picked a specific local model
        user_model = db_ref.get_user_setting(user_id, "local_model")
        if user_model and user_model != _model_name:
            return ChatOllama(
                model=user_model,
                base_url=OLLAMA_BASE_URL,
                temperature=0.3,
            )
        return llm  # global Ollama

    api_key = None
    key_data = db_ref.get_llm_api_key(user_id, provider)
    if key_data:
        try:
            from webapp.database import decrypt_value
            api_key = decrypt_value(key_data["encrypted_key"])
        except Exception as e:
            print(f"[llm_setup] Failed to decrypt key for {provider}: {e}")

    if not api_key:
        # Fall back to env-configured shared key (lets the deployment supply a default)
        env_key_var = {"openai": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}.get(provider)
        if env_key_var:
            api_key = os.getenv(env_key_var)

    if not api_key:
        print(f"[llm_setup] No API key for provider '{provider}' (user {user_id}), falling back to local")
        return llm

    model = (
        db_ref.get_user_setting(user_id, "active_model")
        or os.getenv("DEFAULT_OPENAI_MODEL" if provider == "openai" else "")
        or os.getenv("DEFAULT_LOCAL_MODEL")  # historical name in this project — also used as cloud default
        or _CLOUD_DEFAULTS.get(provider, "")
    )

    try:
        if provider == "claude":
            from langchain_anthropic import ChatAnthropic
            cloud_llm = ChatAnthropic(model=model, api_key=api_key, max_tokens=1024)
        elif provider == "openai":
            from langchain_openai import ChatOpenAI
            cloud_llm = ChatOpenAI(model=model, api_key=api_key)
        elif provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            cloud_llm = ChatGoogleGenerativeAI(model=model, google_api_key=api_key)
        else:
            return llm
        # Wrap with local Ollama as fallback so quota/auth errors don't drop the request
        print(f"[llm_setup] Using {provider}/{model} with local fallback")
        return cloud_llm.with_fallbacks(
            [llm],
            exceptions_to_handle=(Exception,),
        )
    except Exception as e:
        print(f"[llm_setup] Failed to create {provider} LLM: {e}, falling back to local")

    return llm


if llm is None:
    update_model(_model_name)


# For first-aid RAG: nomic-embed-text via Ollama
embeddings = OllamaEmbeddings(
    model="nomic-embed-text:latest",
    base_url=OLLAMA_BASE_URL,
)
