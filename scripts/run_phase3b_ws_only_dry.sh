#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python. Create the project venv before running Phase 3B."
  exit 1
fi

source .venv/bin/activate

export DRY_RUN=true
export LIVE_TRADING=false
export PUBLIC_MARKET_DRY_RUN=true
export PUBLIC_MARKET_WS_ONLY=true
export ALLOW_CACHED_EXCHANGE_FILTERS_IN_DRY_RUN=true
export CACHED_EXCHANGE_FILTERS_PATH="${CACHED_EXCHANGE_FILTERS_PATH:-./config/exchange_filters_ETHUSDC.json}"
export REQUIRE_REST_EXCHANGE_INFO_FOR_LIVE=true
export REQUIRE_SIGNED_REST_VALIDATION_FOR_TESTNET=true
export TESTNET_ORDER_TEST=false
export BINANCE_SYMBOL=ETHUSDC
export BINANCE_INTERVAL=15m
export BINANCE_ENV="${BINANCE_ENV:-mainnet}"
export EXIT_AFTER_BOUNDED_RUNTIME=true
export PHASE3B_BOUNDED_RUNTIME_SECONDS="${PHASE3B_BOUNDED_RUNTIME_SECONDS:-3600}"
export PUBLIC_MARKET_DRY_RUN_SECONDS="$PHASE3B_BOUNDED_RUNTIME_SECONDS"
export BINANCE_API_KEY=
export BINANCE_API_SECRET=
export LOG_LEVEL="${LOG_LEVEL:-DEBUG}"

python -m bot.main
