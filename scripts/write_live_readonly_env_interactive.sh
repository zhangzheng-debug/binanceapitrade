#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

umask 077

if [[ ! -t 0 ]]; then
  echo "Refusing to read API credentials without an interactive TTY." >&2
  exit 2
fi

printf "Binance API key: "
IFS= read -r BINANCE_API_KEY_INPUT
printf "Binance API secret: "
stty -echo
IFS= read -r BINANCE_API_SECRET_INPUT
stty echo
printf "\n"

if [[ -z "$BINANCE_API_KEY_INPUT" || -z "$BINANCE_API_SECRET_INPUT" ]]; then
  echo "Refusing to write .env.live.readonly with empty API credentials." >&2
  exit 3
fi

tmp_file="$(mktemp .env.live.readonly.XXXXXX)"
trap 'rm -f "$tmp_file"' EXIT

cat >"$tmp_file" <<EOF
DRY_RUN=false
LIVE_TRADING=false
PRELIVE_CHECK=true
LIVE_CANARY_MODE=false

BINANCE_ENV=mainnet
BINANCE_SYMBOL=ETHUSDC
BINANCE_INTERVAL=15m
STRATEGY_VARIANT=original_pivot_reversal

PUBLIC_MARKET_DRY_RUN=false
PUBLIC_MARKET_WS_ONLY=false
ALLOW_CACHED_EXCHANGE_FILTERS_IN_DRY_RUN=false
EXIT_AFTER_BOUNDED_RUNTIME=false
PHASE_FAST_SMOKE_SECONDS=0
EOF
printf '%s%s=%s\n' "BINANCE_API_" "KEY" "$BINANCE_API_KEY_INPUT" >>"$tmp_file"
printf '%s%s=%s\n' "BINANCE_API_" "SECRET" "$BINANCE_API_SECRET_INPUT" >>"$tmp_file"
cat >>"$tmp_file" <<EOF
API_KEY_IP_WHITELIST_EXPECTED=167.172.69.16

ORDER_MODE=account_equity_pct
POSITION_SIZE_PCT=200
FIXED_NOTIONAL=10
LIVE_CANARY_NOTIONAL_USDC=10
LIVE_STRATEGY_MAX_ENTRY_FILLS=0
LIVE_STRATEGY_RESUME_EXISTING_POSITION=true
LIVE_MANAGED_POSITION_MARKER_PATH=./data/live_managed_position.json

ALLOW_MARKET_ENTRY=false
ALLOW_STOP_MARKET_ENTRY=false
ENTRY_ORDER_TYPE=LIMIT
ENTRY_TIME_IN_FORCE=GTX

AUTO_CANCEL_UNKNOWN_ORDERS=false
REQUIRE_MANUAL_RECONCILIATION_ON_MISMATCH=true
EOF

chmod 600 "$tmp_file"
mv "$tmp_file" .env.live.readonly
trap - EXIT

mode="$(stat -c '%a' .env.live.readonly)"
if [[ "$mode" != "600" ]]; then
  echo "Refusing to continue: .env.live.readonly permissions are $mode, expected 600." >&2
  exit 4
fi

unset BINANCE_API_KEY_INPUT BINANCE_API_SECRET_INPUT
echo ".env.live.readonly written with mode 600. Credentials were not printed."
