#!/usr/bin/env bash
set -euo pipefail

systemctl --user status ethusdc-pivot-bot-fast-smoke.service --no-pager || true
journalctl --user -u ethusdc-pivot-bot-fast-smoke.service -n 200 --no-pager || true
ps aux | grep -i ethusdc-pivot-bot | grep -v grep || true
pgrep -af '[p]ython.*bot.main' || true
