#!/usr/bin/env bash
set -euo pipefail

if [[ "${I_APPROVE_FAST_SMOKE_START:-}" != "YES" ]]; then
  echo "Refusing to start fast smoke. Set I_APPROVE_FAST_SMOKE_START=YES after explicit approval."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python."
  exit 1
fi

export DRY_RUN=true
export LIVE_TRADING=false
export PUBLIC_MARKET_DRY_RUN=true
export PUBLIC_MARKET_WS_ONLY=true
export ALLOW_CACHED_EXCHANGE_FILTERS_IN_DRY_RUN=true
export BINANCE_SYMBOL=ETHUSDC
export BINANCE_INTERVAL=15m
export EXIT_AFTER_BOUNDED_RUNTIME=true
export PHASE_FAST_SMOKE_SECONDS=1800
export BOOKTICKER_LOG_MODE=summary
export BOOKTICKER_LOG_EVERY_N=2000
export BOOKTICKER_SUMMARY_INTERVAL_SECONDS=60
export KLINE_LOG_UNCLOSED_EVERY_N=200
export LOG_RAW_MARKET_MESSAGES=false
export MAX_EVENTS_LOG_MB=100
export WARN_EVENTS_LOG_MB=50
export MAX_BOT_LOG_MB=100
export WARN_BOT_LOG_MB=50
export BINANCE_ENV=mainnet
export BINANCE_API_KEY=
export BINANCE_API_SECRET=

source .venv/bin/activate
CONFIG_JSON="$(python scripts/check_config.py)"
python scripts/scan_secrets.py

if printf '%s\n' "$CONFIG_JSON" | grep -q '"live_trading": true'; then
  echo "Refusing to start: LIVE_TRADING=true."
  exit 1
fi

if printf '%s\n' "$CONFIG_JSON" | grep -q '"has_api_key": true'; then
  echo "Refusing to start: BINANCE_API_KEY is nonempty."
  exit 1
fi

if printf '%s\n' "$CONFIG_JSON" | grep -q '"has_api_secret": true'; then
  echo "Refusing to start: BINANCE_API_SECRET is nonempty."
  exit 1
fi

systemctl --user start ethusdc-pivot-bot-fast-smoke.service
echo "Started user-level fast-smoke service once. It is not enabled for boot."
