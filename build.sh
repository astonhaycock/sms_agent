#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-sms-agent}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Use one Docker invocation style everywhere (avoids sudo on ps but plain docker on stop).
if docker info >/dev/null 2>&1; then
  dk() { docker "$@"; }
elif sudo docker info >/dev/null 2>&1; then
  dk() { sudo docker "$@"; }
else
  echo "Docker is not available (tried docker and sudo docker)." >&2
  exit 1
fi

# Remove our named instance, then stop anything still bound to these ports (old unnamed / other runs).
dk rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
for port in 8080 8000; do
  while read -r id; do
    [ -z "$id" ] && continue
    dk stop "$id"
  done < <(dk ps -q --filter "publish=$port" 2>/dev/null || true)
done

dk build -f DOCKERFILE -t sms-agent . --no-cache

# Ensure the host-side DB path exists as a file before bind-mounting,
# so Docker doesn't auto-create it as a directory and break SQLite.
DB_FILE="$SCRIPT_DIR/offgrid_agent.db"
if [ ! -e "$DB_FILE" ]; then
  echo "Creating empty DB file at $DB_FILE."
  touch "$DB_FILE"
fi

# No --rm: it conflicts with --restart. Crash exits are retried; this script still replaces via rm -f above.
dk run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 8000:8000 \
  -v "$DB_FILE:/app/offgrid_agent.db" \
  --env-file .env \
  sms-agent

echo "Running as container: $CONTAINER_NAME"
