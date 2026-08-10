#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT:$ROOT/cloud-cost${PYTHONPATH:+:$PYTHONPATH}"
PY="${PYTHON:-python3}"
if [[ -x /tmp/cloud_uv/bin/python ]]; then
  PY=/tmp/cloud_uv/bin/python
  /home/samfash/.local/bin/uv pip install --python "$PY" -r requirements.txt -q
fi
"$PY" -m pytest tests/unit tests/integration -q --tb=short -m 'not slow'
