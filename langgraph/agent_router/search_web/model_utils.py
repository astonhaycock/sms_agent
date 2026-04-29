import smolagents
from pathlib import Path

########################################################################
import dotenv
import os

# .env is at project root (same level as langgraph/)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

g_dotenv_loaded = False


def getenv(variable: str) -> str:
    global g_dotenv_loaded
    if not g_dotenv_loaded:
        g_dotenv_loaded = True
        dotenv.load_dotenv(_PROJECT_ROOT / ".env")
    value = os.getenv(variable)
    return value

def get_api_key(key_name):
    api_key = getenv(key_name)
    if not api_key:
        msg = (f"{key_name} not set. "
               f"Be sure .env has {key_name}. "
               f"Be sure dotenv.load_dotenv() is called at initialization.")
        raise ValueError(msg)
    return api_key

########################################################################
from smolagents import OpenAIServerModel
def google_build_reasoning_model(model_id="gemini-2.5-flash"):
    key_name = "GEMINI_API_KEY"
    api_base = "https://generativelanguage.googleapis.com/v1beta/openai/"
    api_key = get_api_key(key_name)
    
    model = OpenAIServerModel(model_id=model_id,
                              api_base=api_base,
                              api_key=api_key,
                              client_kwargs={"max_retries": 8} 
                              )
    return model


def ollama_build_reasoning_model(model_id=None):
    if model_id is None:
        from agent_router.llm_setup import get_model_name
        model_id = get_model_name()
    base_url = getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
    api_base = base_url.rstrip("/") + "/v1"
    api_key = get_api_key("ollama_api_key")
    return OpenAIServerModel(
        model_id=model_id,
        api_base=api_base,
        api_key=api_key,
        client_kwargs={"max_retries": 15},
    )


