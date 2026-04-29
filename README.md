# Off-Grid AI Agent

SMS-based AI assistant for off-grid areas. Get instant answers via satellite SMS — weather, first aid, web search, trail info, Gmail, and more.

## Quick Start

### 1. Install Dependencies
```bash
uv sync
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your keys (Twilio required; LLM and other keys as needed)
```

### 3. Start the Server
```bash
uv run main.py
```

This starts two services:
- **Webapp** → http://localhost:8000
- **Agent router** → http://localhost:3002

### 4. Access the App
| Page | URL |
|------|-----|
| Landing | http://localhost:8000 |
| Login / Register | http://localhost:8000/login |
| Dashboard | http://localhost:8000/dashboard |
| Settings | http://localhost:8000/settings |
| Admin | http://localhost:8000/admin |
| API Docs | http://localhost:8000/docs |

## Docker

Build and run with one command:
```bash
./build.sh
```

This builds the image, stops any old containers, and starts fresh with `--restart unless-stopped`.

Default ports in Docker: webapp on **8080**, agent router on **8000**. Override with env vars `WEBAPP_PORT` and `AGENT_PORT`.

```bash
# Manual run (after build)
docker run -d --name sms-agent \
  -p 8080:8080 -p 8000:8000 \
  -v "$(pwd)/offgrid_agent.db:/app/offgrid_agent.db" \
  --env-file .env \
  sms-agent
```

## Project Overview

A uv workspace containing two packages:

| Package | Location | Purpose |
|---------|----------|---------|
| `webapp` | `webapp/` | FastAPI web app, auth, database, frontend |
| `agent` | `langgraph/` | LangGraph agent router, all AI agents |

### Agents

| Agent | Trigger |
|-------|---------|
| **Weather** | Weather/forecast questions |
| **First Aid** | Emergency/medical questions |
| **Web Search** | Prefixed with `google ` or general web queries |
| **Camping Advice** | Outdoor skills, knots, gear |
| **Trails** | Trail and hiking info |
| **Gmail** | Email summaries and notifications |
| **Human-in-the-Loop** | Clarification requests routed back to user |

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Uvicorn |
| AI / Agents | LangGraph, LangChain |
| LLM (local) | Ollama (default: `glm-4.7-flash`) |
| LLM (cloud) | Anthropic, OpenAI, Google Gemini (optional, per-user keys) |
| RAG | FAISS + PDF ingestion |
| Observability | Langfuse (optional) |
| SMS | Twilio |
| Database | SQLite (pysqlite3) |
| Frontend | HTML + Tailwind CSS + Datastar |
| Auth | JWT + bcrypt |

## Features

- **SMS-only interface** — works with satellite SMS (iPhone 14+)
- **Multi-provider LLM** — Ollama by default; users can supply Anthropic/OpenAI/Gemini keys via the web UI
- **Compressed responses** — optimized for satellite bandwidth
- **Human-in-the-loop** — agent asks for clarification when needed
- **Gmail integration** — email summaries delivered over SMS
- **RAG support** — FAISS-backed document retrieval for agent context
- **Langfuse observability** — optional tracing and monitoring
- **User accounts** — registration, JWT auth, phone number management
- **Usage tracking** — message history and stats per user
- **Rate limiting & account lockout** — 10 login/min, 5 register/hour, 15-min lockout after 5 failed attempts
- **Encrypted credential storage** — cloud API keys stored encrypted per user

## Project Structure

```
sms_agent/
├── main.py                     # Starts both servers (webapp :8000, agent :3002)
├── build.sh                    # Docker build + run script
├── DOCKERFILE                  # Docker image definition
├── docker/
│   └── entrypoint.sh           # Container startup (webapp :8080, agent :8000)
├── .env.example                # All supported environment variables
├── webapp/                     # Web application package
│   ├── api.py                  # FastAPI app (auth, SMS webhook, user management)
│   ├── database.py             # SQLite database layer
│   ├── hash_password.py        # Password hash utility
│   └── frontend/               # HTML pages + static assets
│       ├── index.html
│       ├── login.html
│       ├── dashboard.html
│       ├── settings.html
│       └── admin.html
└── langgraph/                  # Agent package
    ├── agent_router/
    │   ├── agent_router.py     # LangGraph router + Twilio webhook
    │   ├── llm_setup.py        # Multi-provider LLM setup
    │   ├── langfuse_setup.py   # Observability
    │   ├── rag_utils.py        # FAISS RAG helpers
    │   ├── weather/
    │   ├── firstAid/
    │   ├── search_web/
    │   ├── camping_advice/
    │   ├── trails/
    │   ├── gmail/
    │   └── human_in_the_loop/
    └── start.py
```

## Environment Variables

See `.env.example` for all options. Minimum required:

```env
SECRET_KEY=...              # JWT signing key
PASSWORD_HASHING_SALT=...
ENCRYPTION_SALT=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=...
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LOCAL_MODEL=glm-4.7-flash
```

Cloud LLM keys, Google OAuth (for Gmail), and Langfuse are all optional.

## Troubleshooting

**Port already in use:**
```bash
lsof -ti:8000 | xargs kill -9
lsof -ti:3002 | xargs kill -9
```

**Module not found:**
```bash
uv sync
```

**Regenerate a password hash:**
```bash
python webapp/hash_password.py your_password
```

## Senior Project
CS/SE 4600 — Aston Haycock
