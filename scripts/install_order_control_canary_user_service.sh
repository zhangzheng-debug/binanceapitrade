#!/usr/bin/env bash
set -euo pipefail

if [[ "${I_APPROVE_ORDER_CONTROL_CANARY_USER_SERVICE:-}" != "YES" ]]; then
  echo "Refusing to install order-control canary user service. Set I_APPROVE_ORDER_CONTROL_CANARY_USER_SERVICE=YES after explicit approval."
  exit 1
fi

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

CONFIG_JSON="$(python scripts/check_config.py)"
python scripts/scan_secrets.py

if printf '%s\n' "$CONFIG_JSON" | grep -q '"live_trading": true'; then
  echo "Refusing to install: LIVE_TRADING=true."
  exit 1
fi

if ! printf '%s\n' "$CONFIG_JSON" | grep -q '"has_api_key": true'; then
  echo "Refusing to install: BINANCE_API_KEY is empty."
  exit 1
fi

if ! printf '%s\n' "$CONFIG_JSON" | grep -q '"has_api_secret": true'; then
  echo "Refusing to install: BINANCE_API_SECRET is empty."
  exit 1
fi

if ! printf '%s\n' "$CONFIG_JSON" | grep -q '"binance_env": "mainnet"'; then
  echo "Refusing to install: BINANCE_ENV must be mainnet."
  exit 1
fi

if ! printf '%s\n' "$CONFIG_JSON" | grep -q '"binance_symbol": "ETHUSDC"'; then
  echo "Refusing to install: BINANCE_SYMBOL must be ETHUSDC."
  exit 1
fi

if ! printf '%s\n' "$CONFIG_JSON" | grep -q '"binance_interval": "15m"'; then
  echo "Refusing to install: BINANCE_INTERVAL must be 15m."
  exit 1
fi

mkdir -p "$HOME/.config/systemd/user"
install -m 0644 \
  "$PROJECT_ROOT/deploy/systemd/ethusdc-pivot-bot-order-control-canary.user.service" \
  "$HOME/.config/systemd/user/ethusdc-pivot-bot-order-control-canary.service"

systemctl --user daemon-reload

echo "Installed user-level order-control canary unit:"
echo "$HOME/.config/systemd/user/ethusdc-pivot-bot-order-control-canary.service"
echo "Not enabling boot autostart."
echo "Start manually with scripts/start_order_control_canary_user_service.sh."
