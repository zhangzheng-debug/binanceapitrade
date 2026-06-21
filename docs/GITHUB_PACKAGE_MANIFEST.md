# GitHub Package Manifest

This repository is a sanitized handoff package for the current multi-symbol
Pivot Bot.

Current strategy profiles:

- `ETHUSDC` `15m`, `POSITION_SIZE_PCT=100`
- `BTCUSDC` `1h`, `POSITION_SIZE_PCT=100`
- `XRPUSDC` `1h`, `POSITION_SIZE_PCT=100`

All strategy services were stopped and disabled before this package was
prepared. Signed read-only preflight showed open orders `0` and position amount
`0` for all three symbols.

## Included

- `src/`: Python bot source code.
- `scripts/`: local, deployment, gate, preflight, monitor, and bundle scripts.
- `deploy/systemd/`: user-level systemd units and timers.
- `tests/`: unit tests for strategy, safety, live gates, monitor, and deployment assets.
- `tools/f2_migration_checker/`: Binance Futures public REST/WebSocket migration checker.
- `config/`: non-secret cached dry-run filter fixtures.
- `docs/`: architecture, runbooks, current sanitized server state, and Codex handoff instructions.
- `reports/`: current generated validation reports that do not contain secrets,
  when included by the packaging step.
- `.env.example`: safe template with empty credentials.

## Excluded

- `.env`, `.env.live.readonly`, and any real API key files.
- SSH private keys.
- `.venv/`, Python caches, and local tool caches.
- `logs/*.log`, `logs/*.jsonl`.
- `data/*.sqlite3` and SQLite sidecar files.
- Deployment tarballs in `dist/`.
- Server backups such as `/root/ethusdc-pivot-bot-pre-long-unattended-*.tgz`.

## Secret Policy

Never paste API keys or SSH private keys into chat or GitHub. Use interactive scripts or pre-existing local files:

```bash
bash scripts/write_live_readonly_env_interactive.sh
chmod 600 .env.live.readonly
```

Before every upload:

```bash
python scripts/scan_secrets.py
rg -n "BINANCE_API_KEY=.+|BINANCE_API_SECRET=.+|PRIVATE KEY|gho_" . -S
```

Expected result: `secret_scan=passed`.

## Current Source Of Truth

Use these files first:

- `README.md`
- `docs/CODEX_AUTOMATION_HANDOFF.md`
- `docs/REPRODUCIBLE_DEPLOYMENT_GUIDE.md`
- `docs/SERVER_CURRENT_STATE_SANITIZED.md`
- `docs/risk_rules.md`

Superseded phase reports are intentionally omitted from the GitHub package.
Older local or server artifacts may mention ETH-only, 150%, 200%, or live
canary states; do not treat those as current operating instructions.
