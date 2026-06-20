#!/usr/bin/env bash
set -euo pipefail

if [[ "${I_APPROVE_FAST_SMOKE_USER_SERVICE:-}" != "YES" ]]; then
  echo "Refusing to install fast-smoke user service. Set I_APPROVE_FAST_SMOKE_USER_SERVICE=YES after explicit approval."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python."
  exit 1
fi

source .venv/bin/activate
python scripts/check_config.py >/dev/null
python scripts/scan_secrets.py

mkdir -p "$HOME/.config/systemd/user"
install -m 0644 \
  "$PROJECT_ROOT/deploy/systemd/ethusdc-pivot-bot-fast-smoke.user.service" \
  "$HOME/.config/systemd/user/ethusdc-pivot-bot-fast-smoke.service"

systemctl --user daemon-reload

echo "Installed user-level fast-smoke unit:"
echo "$HOME/.config/systemd/user/ethusdc-pivot-bot-fast-smoke.service"
echo "Not enabling boot autostart."
echo "Start manually with scripts/start_fast_smoke_user_service.sh."
