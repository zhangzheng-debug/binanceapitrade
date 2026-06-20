#!/usr/bin/env bash
set -euo pipefail

systemctl --user stop ethusdc-pivot-bot-dry-run.service || true
systemctl --user status ethusdc-pivot-bot-dry-run.service --no-pager || true
ps aux | grep -i ethusdc | grep -v grep || true
ps aux | grep -i pivot | grep -v grep || true
pgrep -af '[p]ython.*bot' || true

echo "If a residual process appears, report it first. Do not terminate anything without confirming it belongs to ethusdc-pivot-bot and has user approval."
