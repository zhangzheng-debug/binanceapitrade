#!/usr/bin/env bash
set -euo pipefail

if [[ "${I_APPROVE_PHASE3B_6H_PREPARE:-}" != "YES" ]]; then
  echo "Refusing to prepare 6h observation. Set I_APPROVE_PHASE3B_6H_PREPARE=YES after explicit approval."
  exit 1
fi

UNIT_DIR="$HOME/.config/systemd/user/ethusdc-pivot-bot-dry-run.service.d"
OVERRIDE="$UNIT_DIR/override.conf"

mkdir -p "$UNIT_DIR"
cat > "$OVERRIDE" <<'EOF'
[Service]
Environment=PHASE3B_BOUNDED_RUNTIME_SECONDS=21600
RuntimeMaxSec=21700
EOF

systemctl --user daemon-reload

echo "Prepared a 6h dry-run override at $OVERRIDE."
echo "Not enabling boot autostart."
echo "Not starting the service."
echo "Start manually only after approval: systemctl --user start ethusdc-pivot-bot-dry-run.service"
