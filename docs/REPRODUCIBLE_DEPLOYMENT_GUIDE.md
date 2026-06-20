# Reproducible Deployment Guide

This guide rebuilds the ETHUSDC Pivot Bot environment without using any committed secrets.

## Hard Rules

- Do not commit `.env`, `.env.live.readonly`, API keys, API secrets, or SSH private keys.
- Do not paste API keys or SSH private keys into chat.
- Do not use `MARKET` entry.
- Do not use `STOP_MARKET` entry.
- Do not change `BINANCE_INTERVAL=15m`.
- Do not restore the old Safer close gate.
- Live mode requires Binance Futures One-way Mode.
- Add-on entries and reversals remain blocked while a position is open.

## Local Setup

Windows PowerShell:

```powershell
git clone https://github.com/zhangzheng-debug/binanceapitrade.git
cd binanceapitrade
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\scan_secrets.py
.\.venv\Scripts\python.exe scripts\check_config.py
.\.venv\Scripts\python.exe scripts\replay_forced_original_pivot_trigger.py
```

Linux server:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/scan_secrets.py
python scripts/check_config.py
python scripts/replay_forced_original_pivot_trigger.py
```

## New Server Gate Sequence

1. Run the F2 migration checker first. Live deployment is allowed only if Binance Futures mainnet public REST returns HTTP 200 for ping, time, exchangeInfo, and ETHUSDC bookTicker.

```bash
cd tools/f2_migration_checker
bash run_f2_check.sh
```

Required verdict:

```text
F2_MAINNET_REST_GO
```

2. Deploy project files to the server. Do not upload `.env`, `.venv`, logs, SQLite data, or secrets.

3. Create the server venv and run gates:

```bash
cd /root/ethusdc-pivot-bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/scan_secrets.py
python scripts/check_config.py
python scripts/replay_forced_original_pivot_trigger.py
```

4. Write `.env.live.readonly` interactively on the server. The file must stay mode `600`.

```bash
bash scripts/write_live_readonly_env_interactive.sh
```

5. Run signed read-only preflight and order-control gates before any strategy start.

```bash
source .venv/bin/activate
python scripts/preflight_live_readonly.py
python scripts/live_strategy_capability_audit.py
python scripts/live_readiness_gate_report.py
I_APPROVE_FINAL_LIVE_STRATEGY_START=YES python scripts/final_live_start_gate.py
```

6. Install user-level live strategy service after explicit approval.

```bash
export I_APPROVE_FINAL_LIVE_STRATEGY_USER_SERVICE=YES
bash scripts/install_final_live_strategy_user_service.sh
```

7. Start live strategy only after final approval.

```bash
export I_APPROVE_FINAL_LIVE_STRATEGY_START=YES
bash scripts/start_final_live_strategy_user_service.sh
```

8. Install the server-side read-only monitor timer.

```bash
bash scripts/install_live_monitor_user_timer.sh
```

## Existing Singapore Server Status Commands

```bash
ssh -i C:\Users\MR\.ssh1\id_ed25519 root@167.172.69.16
cd /root/ethusdc-pivot-bot
systemctl --user status ethusdc-pivot-bot-live-strategy.service --no-pager
systemctl --user status ethusdc-pivot-bot-live-monitor.timer --no-pager
cat docs/live_monitor_status.md
```

## Stop Commands

Stopping the bot does not necessarily close a live exchange position.

```bash
cd /root/ethusdc-pivot-bot
bash scripts/stop_final_live_strategy_user_service.sh
```

Manual position cleanup must be handled deliberately; do not hide it inside deployment scripts.
