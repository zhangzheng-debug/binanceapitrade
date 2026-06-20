#!/usr/bin/env bash
set -euo pipefail

systemctl --user status ethusdc-pivot-bot-order-control-canary.service --no-pager || true

if [[ -f "reports/live_readiness_gate_summary.json" ]]; then
  .venv/bin/python scripts/live_readiness_gate_report.py >/dev/null
  cat reports/live_readiness_gate_summary.json
fi
