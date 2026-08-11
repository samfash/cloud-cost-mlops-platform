#!/usr/bin/env bash
set -euo pipefail

cd /app/cloud-cost

seed_artifacts() {
  if [[ ! -f artifacts/model_bundle/HEAD ]]; then
    if [[ -d /opt/seed/artifacts/model_bundle ]]; then
      echo "Seeding model artifacts from image..."
      mkdir -p artifacts
      cp -a /opt/seed/artifacts/. artifacts/
    else
      echo "No packaged model found; running training pipeline..."
      python main.py
    fi
  fi

  if [[ ! -d /app/model_lab/submission ]] || [[ ! -f /app/model_lab/submission/chosen.json ]]; then
    if [[ -d /opt/seed/model_lab/submission ]]; then
      mkdir -p /app/model_lab/submission
      cp -a /opt/seed/model_lab/submission/. /app/model_lab/submission/
    fi
  fi
}

drop_to_appuser() {
  if command -v runuser >/dev/null 2>&1; then
    exec runuser -u appuser -- "$@"
  fi
  if command -v setpriv >/dev/null 2>&1; then
    exec setpriv --reuid=appuser --regid=appuser --init-groups -- "$@"
  fi
  # Last resort (some slim images).
  exec su -s /bin/bash appuser -c 'exec "$@"' -- "$@"
}

seed_artifacts

# When started as root (default image), ensure volume ownership then drop privileges.
if [[ "$(id -u)" -eq 0 ]]; then
  mkdir -p artifacts logs
  chown -R appuser:appuser artifacts logs /app/model_lab/submission 2>/dev/null || true
  drop_to_appuser "$@"
fi

exec "$@"
