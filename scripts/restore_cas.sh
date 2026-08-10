#!/usr/bin/env bash
# Restore a CAS model store backup into cloud-cost/artifacts/model_bundle.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup.tar.gz>" >&2
  exit 1
fi

ARCHIVE="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST_PARENT="${CAS_DEST_PARENT:-$ROOT/cloud-cost/artifacts}"

if [[ ! -f "$ARCHIVE" ]]; then
  echo "Archive not found: $ARCHIVE" >&2
  exit 1
fi

if [[ -f "$ARCHIVE.sha256" ]]; then
  echo "Verifying checksum..."
  (cd "$(dirname "$ARCHIVE")" && sha256sum -c "$(basename "$ARCHIVE").sha256")
fi

mkdir -p "$DEST_PARENT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
tar -xzf "$ARCHIVE" -C "$TMP"

if [[ ! -d "$TMP/model_bundle" ]]; then
  echo "Archive does not contain model_bundle/" >&2
  exit 1
fi

rm -rf "$DEST_PARENT/model_bundle"
mv "$TMP/model_bundle" "$DEST_PARENT/model_bundle"
echo "Restored CAS store to $DEST_PARENT/model_bundle"
