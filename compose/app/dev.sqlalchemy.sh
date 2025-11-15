#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="src:${PYTHONPATH:-}"

alembic upgrade head

APP_ENTRYPOINT=${ROBYN_APP_PATH:-src/app/server.py}

if [ $# -eq 0 ]; then
  exec python -m robyn "$APP_ENTRYPOINT" --dev
fi

exec "$@"
