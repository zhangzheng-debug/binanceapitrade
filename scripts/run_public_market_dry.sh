#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export DRY_RUN=true
export LIVE_TRADING=false
export PUBLIC_MARKET_DRY_RUN=true
export PUBLIC_MARKET_DRY_RUN_SECONDS="${PUBLIC_MARKET_DRY_RUN_SECONDS:-20}"
export BINANCE_ENV=mainnet
export BINANCE_SYMBOL=ETHUSDC
export BINANCE_INTERVAL=15m
export LOG_LEVEL="${LOG_LEVEL:-DEBUG}"

if [[ -x .venv/bin/python ]]; then
  PYTHON=.venv/bin/python
else
  PYTHON=python
fi

"$PYTHON" -m bot.main
