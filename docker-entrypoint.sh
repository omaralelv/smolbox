#!/bin/sh
set -e

alembic upgrade head

if [ "${IMPORT_INITIAL_CATALOG:-false}" = "true" ]; then
    if [ -z "${INITIAL_CATALOG_PASSWORD:-}" ]; then
        echo "INITIAL_CATALOG_PASSWORD is required when IMPORT_INITIAL_CATALOG=true" >&2
        exit 1
    fi

    python -m app.scripts.import_initial_catalog --password "$INITIAL_CATALOG_PASSWORD"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
