#!/usr/bin/env bash
set -euo pipefail

if [[ "${I_APPROVE_PHASE3B_USER_SYSTEMD_DRY_RUN:-}" != "YES" ]]; then
  echo "Refusing to install Phase 3B user service. Set I_APPROVE_PHASE3B_USER_SYSTEMD_DRY_RUN=YES after explicit approval."
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
python scripts/check_config.py
python scripts/scan_secrets.py

mkdir -p "$HOME/.config/systemd/user"
install -m 0644 \
  "$PROJECT_ROOT/deploy/systemd/ethusdc-pivot-bot-dry-run.user.service" \
  "$HOME/.config/systemd/user/ethusdc-pivot-bot-dry-run.service"

systemctl --user daemon-reload

echo "Installed user-level dry-run unit:"
echo "$HOME/.config/systemd/user/ethusdc-pivot-bot-dry-run.service"
echo "Not enabling boot autostart."
echo "Logs: journalctl --user -u ethusdc-pivot-bot-dry-run.service -f"

if [[ "${1:-}" == "--start-once" ]]; then
  systemctl --user start ethusdc-pivot-bot-dry-run.service
  echo "Started one manual dry-run observation."
fi
