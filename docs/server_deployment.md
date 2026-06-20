# Server Deployment Notes

Phase 3A deployed a dry-run project to `/home/dev/ethusdc-pivot-bot`. Phase 3A.5 may update that directory for bounded public WebSocket dry-run only. No live trading service has been installed.

The Phase 1 audit found:

- Existing AI RTL workload under `/home/dev/ai-rtl-studio`.
- Python service on `127.0.0.1:18081`.
- Docker and PM2 absent.
- UFW active, but rules require sudo password to inspect.

## Future Directory

Recommended isolated directory:

```text
/home/dev/ethusdc-pivot-bot
```

Do not deploy inside `/home/dev/ai-rtl-studio`.

## Process Manager

Use systemd rather than PM2. Docker is not recommended because it is not installed and would require system changes.

## Environment

Use a Python venv and a `.env` file with mode `600`:

```bash
chmod 600 /home/dev/ethusdc-pivot-bot/.env
```

## Service Draft

This is documentation only. Do not install without explicit approval. Phase 3B can only be a WebSocket-only systemd dry-run while REST 451 remains unresolved.

```ini
[Unit]
Description=ETHUSDC Pivot Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=dev
WorkingDirectory=/home/dev/ethusdc-pivot-bot
EnvironmentFile=/home/dev/ethusdc-pivot-bot/.env
ExecStart=/home/dev/ethusdc-pivot-bot/.venv/bin/python -m bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Pre-Deployment Confirmations

- Confirm this server remains the target.
- Confirm sudo access path for systemd installation.
- Confirm UFW rules and root cron.
- Confirm no interference with `127.0.0.1:18081` or existing tmux sessions.
- Run dry-run first; never enable live as part of install.
