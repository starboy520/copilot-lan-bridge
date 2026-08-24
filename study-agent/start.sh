#!/usr/bin/env sh
set -eu

APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$APP_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

exec python3 -m server.app \
  --host "${STUDY_AGENT_HOST:-0.0.0.0}" \
  --port "${STUDY_AGENT_PORT:-8765}" \
  --data-dir "${STUDY_AGENT_DATA_DIR:-$APP_DIR/data}"
