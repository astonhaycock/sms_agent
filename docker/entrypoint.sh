#!/bin/sh
set -e

WEBAPP_PORT="${WEBAPP_PORT:-8080}"
AGENT_PORT="${AGENT_PORT:-8000}"

# Check if something is already listening on the webapp port (e.g. webapp already started)
port_in_use() {
  _port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -tlnp 2>/dev/null | grep -q ":${_port} " && return 0
  fi
  if command -v netstat >/dev/null 2>&1; then
    netstat -tln 2>/dev/null | grep -q ":${_port} " && return 0
  fi
  return 1
}

if ! port_in_use "$WEBAPP_PORT"; then
  echo "[entrypoint] Starting webapp on port $WEBAPP_PORT..."
  uv run uvicorn webapp.api:app --host 0.0.0.0 --port "$WEBAPP_PORT" &
  WEBAPP_PID=$!
  # Brief wait so webapp can bind before we start the agent
  sleep 2
else
  echo "[entrypoint] Port $WEBAPP_PORT already in use, skipping webapp."
  WEBAPP_PID=""
fi

echo "[entrypoint] Starting LangGraph agent router on port $AGENT_PORT..."
cd /app/langgraph && exec uv run uvicorn agent_router.agent_router:app --host 0.0.0.0 --port "$AGENT_PORT"
