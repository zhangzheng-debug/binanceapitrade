#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

python3 check_binance_futures_rest.py
python3 check_binance_futures_ws.py

echo "Result: $SCRIPT_DIR/f2_migration_check_result.json"
echo "Report: $SCRIPT_DIR/f2_migration_check_report.md"
