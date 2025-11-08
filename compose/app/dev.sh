#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="src:${PYTHONPATH:-}"

alembic upgrade head

if [ $# -eq 0 ]; then
  exec python -m robyn src/app/server.py --dev
fi

exec "$@"
