#!/usr/bin/env bash
set -euo pipefail

cd /app/cloud-cost

# If a volume mounts over artifacts and is empty, restore the image seed (or train).
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

exec "$@"
