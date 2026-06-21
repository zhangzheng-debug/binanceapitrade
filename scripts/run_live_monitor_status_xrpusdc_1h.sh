#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python."
  exit 1
fi

if [[ ! -f ".env.live.readonly" ]]; then
  echo "Missing .env.live.readonly."
  exit 1
fi

source .venv/bin/activate
set -a
source .env.live.readonly
set +a

export DRY_RUN=false
export LIVE_TRADING=true
export PUBLIC_MARKET_DRY_RUN=false
export PUBLIC_MARKET_WS_ONLY=false
export BINANCE_ENV=mainnet
export BINANCE_SYMBOL=XRPUSDC
export BINANCE_INTERVAL=1h
export STRATEGY_VARIANT=original_pivot_reversal
export ORDER_MODE=account_equity_pct
export POSITION_SIZE_PCT=100
export LIVE_STRATEGY_RESUME_EXISTING_POSITION="${LIVE_STRATEGY_RESUME_EXISTING_POSITION:-true}"
export LIVE_MANAGED_POSITION_MARKER_PATH="${LIVE_MANAGED_POSITION_MARKER_PATH:-./data/live_managed_position_XRPUSDC_1h.json}"
export STATE_DB_PATH="${STATE_DB_PATH:-./data/state_XRPUSDC_1h.sqlite3}"
export LOG_DIR="${LOG_DIR:-./logs/XRPUSDC_1h}"
export LIVE_STRATEGY_SERVICE_NAME="${LIVE_STRATEGY_SERVICE_NAME:-xrpusdc-pivot-bot-live-strategy.service}"
export LIVE_MONITOR_EVENTS_LOG="${LIVE_MONITOR_EVENTS_LOG:-./logs/XRPUSDC_1h/events.jsonl}"
export LIVE_MONITOR_JSON_REPORT="${LIVE_MONITOR_JSON_REPORT:-./reports/live_monitor_status_XRPUSDC_1h.json}"
export LIVE_MONITOR_MD_REPORT="${LIVE_MONITOR_MD_REPORT:-./docs/live_monitor_status_XRPUSDC_1h.md}"

exec .venv/bin/python scripts/live_monitor_status.py
