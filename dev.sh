#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  echo "Backend не настроен. Сначала создай .venv и установи backend/requirements.txt."
  exit 1
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm не найден. Установи Node.js и pnpm."
  exit 1
fi

if [[ -z "${OBS_WEBSOCKET_PASSWORD:-}" ]]; then
  read -r -s -p "Пароль OBS WebSocket: " OBS_WEBSOCKET_PASSWORD || exit 1
  printf '\n'
  export OBS_WEBSOCKET_PASSWORD
fi

"$PROJECT_DIR/.venv/bin/python" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
pnpm dev &
FRONTEND_PID=$!

stop_servers() {
  trap - INT TERM EXIT
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap stop_servers INT TERM EXIT
set +e
wait -n "$BACKEND_PID" "$FRONTEND_PID"
STATUS=$?
set -e
stop_servers
exit "$STATUS"
