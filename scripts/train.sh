#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../cloud-cost"
python main.py
