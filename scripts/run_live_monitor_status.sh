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
export BINANCE_SYMBOL=ETHUSDC
export BINANCE_INTERVAL=15m
export STRATEGY_VARIANT=original_pivot_reversal
export ORDER_MODE=account_equity_pct
export POSITION_SIZE_PCT=200
export LIVE_STRATEGY_RESUME_EXISTING_POSITION="${LIVE_STRATEGY_RESUME_EXISTING_POSITION:-true}"
export LIVE_MANAGED_POSITION_MARKER_PATH="${LIVE_MANAGED_POSITION_MARKER_PATH:-./data/live_managed_position.json}"

exec .venv/bin/python scripts/live_monitor_status.py
