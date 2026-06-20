# GitHub Package Manifest

This repository is a sanitized handoff package for the ETHUSDC Pivot Bot.

## Included

- `src/`: Python bot source code.
- `scripts/`: local, deployment, gate, preflight, monitor, and bundle scripts.
- `deploy/systemd/`: user-level systemd units and timers.
- `tests/`: unit tests for strategy, safety, live gates, monitor, and deployment assets.
- `tools/f2_migration_checker/`: Binance Futures public REST/WebSocket migration checker.
- `config/`: non-secret cached dry-run filter fixtures.
- `docs/`: architecture, runbooks, current sanitized server state, and Codex handoff instructions.
- `reports/`: generated validation reports that do not contain secrets.
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

Expected result: `scan_secrets=passed`.
