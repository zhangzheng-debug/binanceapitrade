#!/usr/bin/env bash
set -euo pipefail

systemctl --user stop ethusdc-pivot-bot-fast-smoke.service || true
systemctl --user status ethusdc-pivot-bot-fast-smoke.service --no-pager || true
ps aux | grep -i ethusdc-pivot-bot | grep -v grep || true
pgrep -af '[p]ython.*bot.main' || true

echo "Stopped user-level fast-smoke service only. No system-wide units or other services were touched."
