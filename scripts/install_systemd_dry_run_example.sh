#!/usr/bin/env bash
set -euo pipefail

echo "This script is a draft. Do not run without explicit human approval."

if [[ "${I_UNDERSTAND_THIS_INSTALLS_SYSTEMD_DRY_RUN:-}" != "YES" ]]; then
  echo "Refusing to install. Set I_UNDERSTAND_THIS_INSTALLS_SYSTEMD_DRY_RUN=YES only after explicit approval."
  exit 1
fi

if grep -q '^LIVE_TRADING=true' /home/dev/ethusdc-pivot-bot/.env 2>/dev/null; then
  echo "Refusing to install: LIVE_TRADING=true is not allowed for this dry-run service."
  exit 1
fi

sudo install -m 0644 \
  /home/dev/ethusdc-pivot-bot/deploy/systemd/ethusdc-pivot-bot-dry-run.service.example \
  /etc/systemd/system/ethusdc-pivot-bot-dry-run.service

sudo systemctl daemon-reload
echo "Installed dry-run service file only. Review and start manually after approval."
