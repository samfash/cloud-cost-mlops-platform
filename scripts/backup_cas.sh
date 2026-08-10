#!/usr/bin/env bash
# Backup the immutable CAS model store (and optional pipeline ledgers).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${CAS_SRC:-$ROOT/cloud-cost/artifacts/model_bundle}"
OUT_DIR="${BACKUP_DIR:-$ROOT/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$OUT_DIR/model_bundle_$STAMP.tar.gz"

if [[ ! -d "$SRC" ]]; then
  echo "CAS store not found: $SRC" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
tar -czf "$DEST" -C "$(dirname "$SRC")" "$(basename "$SRC")"
echo "Wrote $DEST"
sha256sum "$DEST" > "$DEST.sha256"
echo "Wrote $DEST.sha256"
