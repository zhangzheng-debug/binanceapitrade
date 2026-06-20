#!/usr/bin/env bash
set -euo pipefail

systemctl --user status ethusdc-pivot-bot-dry-run.service --no-pager || true
journalctl --user -u ethusdc-pivot-bot-dry-run.service -n 200 --no-pager || true
ps aux | grep -i ethusdc | grep -v grep || true
ps aux | grep -i pivot | grep -v grep || true
pgrep -af '[p]ython.*bot' || true
