#!/usr/bin/env bash
set -euo pipefail

systemctl --user stop ethusdc-pivot-bot-live-strategy.service || true
systemctl --user status ethusdc-pivot-bot-live-strategy.service --no-pager || true
echo "Stopped user-level final live strategy service only."
