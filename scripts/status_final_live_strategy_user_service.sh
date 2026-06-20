#!/usr/bin/env bash
set -euo pipefail

systemctl --user status ethusdc-pivot-bot-live-strategy.service --no-pager || true
journalctl --user -u ethusdc-pivot-bot-live-strategy.service -n 200 --no-pager || true
