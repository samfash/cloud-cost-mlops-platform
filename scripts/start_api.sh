#!/usr/bin/env bash
# Production start for Docker / Render. Honors $PORT (Render injects this).
set -euo pipefail

cd /app/cloud-cost
PORT="${PORT:-8080}"
# Free tier is 512MB — keep threads low (override with GUNICORN_THREADS).
THREADS="${GUNICORN_THREADS:-2}"
if [[ "${RENDER_SLIM_BUILD:-0}" == "1" ]]; then
  THREADS="${GUNICORN_THREADS:-2}"
fi

exec gunicorn \
  --bind "0.0.0.0:${PORT}" \
  --workers 1 \
  --threads "${THREADS}" \
  --timeout 120 \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --max-requests 500 \
  --max-requests-jitter 50 \
  --access-logfile - \
  --error-logfile - \
  --capture-output \
  app:app
