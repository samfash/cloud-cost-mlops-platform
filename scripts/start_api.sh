#!/usr/bin/env bash
# Production start for Docker / Render. Honors $PORT (Render injects this).
set -euo pipefail

cd /app/cloud-cost
PORT="${PORT:-8080}"

exec gunicorn \
  --bind "0.0.0.0:${PORT}" \
  --workers 1 \
  --threads 8 \
  --timeout 60 \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --max-requests 1000 \
  --max-requests-jitter 100 \
  --access-logfile - \
  --error-logfile - \
  --capture-output \
  app:app
