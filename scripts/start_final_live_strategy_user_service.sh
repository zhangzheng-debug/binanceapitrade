#!/usr/bin/env bash
set -euo pipefail

if [[ "${I_APPROVE_FINAL_LIVE_STRATEGY_START:-}" != "YES" ]]; then
  echo "Refusing to start final live strategy. Set I_APPROVE_FINAL_LIVE_STRATEGY_START=YES after explicit final approval."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -f "$HOME/.config/systemd/user/ethusdc-pivot-bot-live-strategy.service" ]]; then
  echo "Missing user service. Install first with scripts/install_final_live_strategy_user_service.sh."
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
python scripts/live_readiness_gate_report.py
I_APPROVE_FINAL_LIVE_STRATEGY_START=YES python scripts/final_live_start_gate.py

systemctl --user start ethusdc-pivot-bot-live-strategy.service
systemctl --user status ethusdc-pivot-bot-live-strategy.service --no-pager || true
echo "Started user-level final live strategy."
