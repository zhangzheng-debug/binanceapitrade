#!/usr/bin/env bash
set -euo pipefail

if [[ "${I_APPROVE_ORDER_CONTROL_CANARY_START:-}" != "YES" ]]; then
  echo "Refusing to start order-control canary. Set I_APPROVE_ORDER_CONTROL_CANARY_START=YES after explicit approval."
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
  echo "Refusing to start: LIVE_TRADING=true."
  exit 1
fi

if ! printf '%s\n' "$CONFIG_JSON" | grep -q '"has_api_key": true'; then
  echo "Refusing to start: BINANCE_API_KEY is empty."
  exit 1
fi

if ! printf '%s\n' "$CONFIG_JSON" | grep -q '"has_api_secret": true'; then
  echo "Refusing to start: BINANCE_API_SECRET is empty."
  exit 1
fi

if [[ "${I_APPROVE_HEDGE_MODE_ORDER_CONTROL_CANARY:-}" == "YES" ]]; then
  systemctl --user set-environment I_APPROVE_HEDGE_MODE_ORDER_CONTROL_CANARY=YES
else
  systemctl --user unset-environment I_APPROVE_HEDGE_MODE_ORDER_CONTROL_CANARY || true
fi

cleanup_manager_env() {
  systemctl --user unset-environment I_APPROVE_HEDGE_MODE_ORDER_CONTROL_CANARY || true
}
trap cleanup_manager_env EXIT

systemctl --user start ethusdc-pivot-bot-order-control-canary.service
systemctl --user status ethusdc-pivot-bot-order-control-canary.service --no-pager || true
python scripts/live_readiness_gate_report.py
echo "Order-control canary service run finished. It is not enabled for boot."
