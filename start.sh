#!/usr/bin/env bash
# start.sh - Boot both ShelfPulse backend services in one container.
#
# The MCP server runs internally on 127.0.0.1:8001 (the agent's default
# target). The FastAPI app binds the public port the host assigns ($PORT,
# defaulting to 8000 for local Docker runs).
set -euo pipefail

MCP_HOST="${MCP_HOST:-127.0.0.1}"
MCP_PORT="${MCP_PORT:-8001}"
API_PORT="${PORT:-8000}"

echo "[start] launching MCP server on ${MCP_HOST}:${MCP_PORT} ..."
uv run python -m mcp_server.server &
MCP_PID=$!

# If the MCP server dies, take the whole container down so the host restarts it.
trap 'echo "[start] shutting down"; kill "$MCP_PID" 2>/dev/null || true' EXIT

echo "[start] waiting for MCP server to accept connections ..."
for i in $(seq 1 60); do
  if python -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('${MCP_HOST}', ${MCP_PORT}))==0 else 1)"; then
    echo "[start] MCP server is up."
    break
  fi
  if ! kill -0 "$MCP_PID" 2>/dev/null; then
    echo "[start] MCP server exited before becoming ready." >&2
    exit 1
  fi
  sleep 1
done

echo "[start] launching API on 0.0.0.0:${API_PORT} ..."
exec uv run uvicorn api.main:app --host 0.0.0.0 --port "${API_PORT}"
