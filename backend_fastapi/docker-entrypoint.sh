#!/bin/sh
set -e
cd /app
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  uv run alembic upgrade head
fi
exec uv run "$@"
