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

if [ "${IMPORT_OPENING_CUTOFFS:-false}" = "true" ]; then
    if [ "${OPENING_CUTOFFS_UPDATE_EXISTING:-false}" = "true" ]; then
        python -m app.scripts.import_store_reimbursement_opening_cutoffs \
            --starts-on "${OPENING_CUTOFFS_STARTS_ON:-2026-07-01}" \
            --ends-on "${OPENING_CUTOFFS_ENDS_ON:-2026-07-31}" \
            --amount "${OPENING_CUTOFFS_AMOUNT:-0.00}" \
            --notes "${OPENING_CUTOFFS_NOTES:-Corte inicial migrado a Smolbox.}" \
            --update-existing
    else
        python -m app.scripts.import_store_reimbursement_opening_cutoffs \
            --starts-on "${OPENING_CUTOFFS_STARTS_ON:-2026-07-01}" \
            --ends-on "${OPENING_CUTOFFS_ENDS_ON:-2026-07-31}" \
            --amount "${OPENING_CUTOFFS_AMOUNT:-0.00}" \
            --notes "${OPENING_CUTOFFS_NOTES:-Corte inicial migrado a Smolbox.}"
    fi
fi

if [ "${IMPORT_SPENDING_BASELINES:-false}" = "true" ]; then
    python -m app.scripts.import_store_spending_baselines
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
