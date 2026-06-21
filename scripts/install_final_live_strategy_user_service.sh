#!/usr/bin/env bash
set -euo pipefail

if [[ "${I_APPROVE_FINAL_LIVE_STRATEGY_USER_SERVICE:-}" != "YES" ]]; then
  echo "Refusing to install final live strategy user service. Set I_APPROVE_FINAL_LIVE_STRATEGY_USER_SERVICE=YES after explicit approval."
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
  echo "Refusing to install: .env.live.readonly must keep LIVE_TRADING=false before final start."
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

if ! printf '%s\n' "$CONFIG_JSON" | grep -q '"order_mode": "account_equity_pct"'; then
  echo "Refusing to install: ORDER_MODE must be account_equity_pct."
  exit 1
fi

if ! printf '%s\n' "$CONFIG_JSON" | grep -q '"position_size_pct": "100"'; then
  echo "Refusing to install: POSITION_SIZE_PCT must be 100."
  exit 1
fi

mkdir -p "$HOME/.config/systemd/user"
install -m 0644 \
  "$PROJECT_ROOT/deploy/systemd/ethusdc-pivot-bot-live-strategy.user.service" \
  "$HOME/.config/systemd/user/ethusdc-pivot-bot-live-strategy.service"

systemctl --user daemon-reload
systemctl --user enable ethusdc-pivot-bot-live-strategy.service

echo "Installed user-level final live strategy unit:"
echo "$HOME/.config/systemd/user/ethusdc-pivot-bot-live-strategy.service"
echo "Enabled user-level boot autostart."
echo "Start manually only with scripts/start_final_live_strategy_user_service.sh."
