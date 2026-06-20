#!/usr/bin/env bash
set -euo pipefail

if [[ "${I_APPROVE_PHASE3B_USER_SYSTEMD_UNINSTALL:-}" != "YES" ]]; then
  echo "Refusing to uninstall Phase 3B user service. Set I_APPROVE_PHASE3B_USER_SYSTEMD_UNINSTALL=YES after explicit approval."
  exit 1
fi

UNIT="$HOME/.config/systemd/user/ethusdc-pivot-bot-dry-run.service"

systemctl --user stop ethusdc-pivot-bot-dry-run.service || true
systemctl --user disable ethusdc-pivot-bot-dry-run.service || true
rm -f "$UNIT"
systemctl --user daemon-reload

echo "Removed user-level dry-run unit only. No system-wide units or other projects were touched."
