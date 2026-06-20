#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python."
  exit 1
fi

if [[ ! -f ".env.live.readonly" ]]; then
  echo "Missing .env.live.readonly."
  exit 1
fi

mkdir -p "$HOME/.config/systemd/user"
install -m 0644 \
  "$PROJECT_ROOT/deploy/systemd/ethusdc-pivot-bot-live-monitor.user.service" \
  "$HOME/.config/systemd/user/ethusdc-pivot-bot-live-monitor.service"
install -m 0644 \
  "$PROJECT_ROOT/deploy/systemd/ethusdc-pivot-bot-live-monitor.user.timer" \
  "$HOME/.config/systemd/user/ethusdc-pivot-bot-live-monitor.timer"

systemctl --user daemon-reload
systemctl --user enable --now ethusdc-pivot-bot-live-monitor.timer

echo "Installed and started user-level read-only live monitor timer."
systemctl --user status ethusdc-pivot-bot-live-monitor.timer --no-pager || true
