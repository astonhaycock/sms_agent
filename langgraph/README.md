# LangGraph Agents

AI agent logic for the Off-Grid AI Agent. Uses LangGraph to route incoming SMS messages to the appropriate specialized agent.

## Structure

```
langgraph/
├── agent_router/
│   ├── agent_router.py       # LangGraph router + Twilio webhook (FastAPI, port 3002 / 8000 in Docker)
│   ├── llm_setup.py          # Multi-provider LLM setup (Ollama, Anthropic, OpenAI, Gemini)
│   ├── langfuse_setup.py     # Langfuse observability integration
│   ├── rag_utils.py          # FAISS-based RAG helpers
│   ├── weather/              # Weather agent
│   ├── firstAid/             # First aid / emergency agent
│   ├── search_web/           # Web search agent (smolagents + DuckDuckGo)
│   ├── camping_advice/       # Camping and outdoor advice agent
│   ├── trails/               # Trail and hiking info agent
│   ├── gmail/                # Gmail summary agent
│   └── human_in_the_loop/    # Clarification / HITL agent
└── start.py
```

## How It Works

```
Twilio SMS
    |
    v
agent_router.py  (POST /sms)
    |
    v
classify()  -- LLM classifies intent into one of:
    weather | first_aid | search_web | camping_advice | trails | gmail | clarification
    |
    v
Agent (specialized)
    |
    v
Response compression  (fits SMS / satellite limits)
    |
    v
Twilio outbound SMS
```

## Agents

| Agent | Module | Description |
|-------|--------|-------------|
| Weather | `weather/` | Real-time forecasts; uses Twilio carrier location as fallback |
| First Aid | `firstAid/` | Emergency guidance, step-by-step instructions |
| Web Search | `search_web/` | DuckDuckGo search + AI summarization via smolagents |
| Camping Advice | `camping_advice/` | Outdoor skills, knots, gear, wildlife |
| Trails | `trails/` | Trail and hiking information |
| Gmail | `gmail/` | Email summaries delivered over SMS; requires Google OAuth |
| Human-in-the-Loop | `human_in_the_loop/` | Sends a clarifying question back to the user and waits for reply |

## LLM Providers

Configured in `llm_setup.py`. Default is Ollama (local). Users can supply cloud API keys via the web UI and those keys are used per-request.

| Provider | Env var | Notes |
|----------|---------|-------|
| Ollama (default) | `OLLAMA_BASE_URL`, `DEFAULT_LOCAL_MODEL` | Runs locally |
| Anthropic | `ANTHROPIC_API_KEY` | Optional |
| OpenAI | `OPENAI_API_KEY`, `DEFAULT_OPENAI_MODEL` | Optional |
| Google Gemini | `GEMINI_API_KEY` | Optional; also used by web search agent |

A lightweight model (`GMAIL_LLM_MODEL`, default `gemma3:4b`) is used for low-resource tasks like Gmail summaries.

## Observability

Langfuse tracing is enabled by default. Disable with `LANGFUSE_ENABLED=false`.

```env
LANGFUSE_ENABLED=true
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=http://localhost:3001
```

## Adding a New Agent

1. Create `agent_router/my_agent/agent.py` with an async function (e.g. `run_my_agent(state)`).
2. Import and register it in `agent_router.py`:
   - Add to the `classify()` output labels.
   - Add a node and edge in the `StateGraph`.
3. Test by posting to `POST /sms` on the agent router.

## Running

From the project root (recommended — starts both services):
```bash
uv run main.py
```

Agent router only:
```bash
cd langgraph && uvicorn agent_router.agent_router:app --reload --port 3002
```
