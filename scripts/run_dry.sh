#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo ".env not found; using process-level dry-run defaults. Copy .env.example to .env when ready."
fi

export DRY_RUN=true
export LIVE_TRADING=false
export PUBLIC_MARKET_DRY_RUN=false
if [[ -x .venv/bin/python ]]; then
  PYTHON=.venv/bin/python
else
  PYTHON=python
fi

"$PYTHON" -m bot.main
