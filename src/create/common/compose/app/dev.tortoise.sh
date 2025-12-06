#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="src:${PYTHONPATH:-}"

if ! init_output=$(aerich init-db 2>&1); then
  if [[ "$init_output" != *"App 'models' is already initialized."* ]]; then
    printf '%s\n' "$init_output" >&2
    exit 1
  fi
  printf '%s\n' "$init_output"
fi

aerich upgrade

APP_ENTRYPOINT=${ROBYN_APP_PATH:-src/app/server.py}

if [ $# -eq 0 ]; then
  exec python -m robyn "$APP_ENTRYPOINT" --dev
fi

exec "$@"
