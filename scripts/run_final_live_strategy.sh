#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ "${I_APPROVE_FINAL_LIVE_STRATEGY_START:-}" != "YES" ]]; then
  echo "Refusing to run final live strategy. Missing I_APPROVE_FINAL_LIVE_STRATEGY_START=YES."
  exit 1
fi

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

python scripts/scan_secrets.py
python scripts/live_strategy_capability_audit.py
python scripts/check_config.py >/tmp/ethusdc-pivot-bot-check-config.json

export DRY_RUN=false
export LIVE_TRADING=true
export PUBLIC_MARKET_DRY_RUN=false
export PUBLIC_MARKET_WS_ONLY=false
export ALLOW_CACHED_EXCHANGE_FILTERS_IN_DRY_RUN=false
export BINANCE_ENV=mainnet
export BINANCE_SYMBOL=ETHUSDC
export BINANCE_INTERVAL=15m
export STRATEGY_VARIANT=original_pivot_reversal
export ORDER_MODE=account_equity_pct
export POSITION_SIZE_PCT=200
export LIVE_STRATEGY_MAX_ENTRY_FILLS="${LIVE_STRATEGY_MAX_ENTRY_FILLS:-0}"
export LIVE_STRATEGY_RESUME_EXISTING_POSITION="${LIVE_STRATEGY_RESUME_EXISTING_POSITION:-true}"
export LIVE_MANAGED_POSITION_MARKER_PATH="${LIVE_MANAGED_POSITION_MARKER_PATH:-./data/live_managed_position.json}"
export I_APPROVE_FINAL_LIVE_STRATEGY_START=YES

exec .venv/bin/python -m bot.main
