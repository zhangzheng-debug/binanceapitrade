# Reproducible Deployment Guide

This guide rebuilds the current multi-symbol Pivot Bot environment without
using any committed secrets.

## Hard Rules

- Do not commit `.env`, `.env.live.readonly`, API keys, API secrets, SSH private
  keys, logs, SQLite state, or `.venv`.
- Do not paste API keys or SSH private keys into chat.
- Do not use `MARKET` entry.
- Do not use `STOP_MARKET` entry.
- Do not restore the old Safer close gate.
- Live mode requires Binance Futures One-way Mode.
- Start no strategy service unless explicitly approved in the current thread.
- Stopping a strategy service does not cancel exchange orders or close exchange
  positions; verify with signed read-only preflight.

## Current Profiles

| Symbol | Interval | Position size | Service |
| --- | --- | --- | --- |
| `ETHUSDC` | `15m` | `100%` account equity | `ethusdc-pivot-bot-live-strategy.service` |
| `BTCUSDC` | `1h` | `100%` account equity | `btcusdc-pivot-bot-live-strategy.service` |
| `XRPUSDC` | `1h` | `100%` account equity | `xrpusdc-pivot-bot-live-strategy.service` |

All use `STRATEGY_VARIANT=original_pivot_reversal`.

## Local Setup

Windows PowerShell:

```powershell
git clone https://github.com/zhangzheng-debug/binanceapitrade.git
cd binanceapitrade
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
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
python -m pytest
python scripts/scan_secrets.py
python scripts/check_config.py
python scripts/replay_forced_original_pivot_trigger.py
```

## Config Checks For Current Profiles

```bash
BINANCE_SYMBOL=ETHUSDC BINANCE_INTERVAL=15m POSITION_SIZE_PCT=100 python scripts/check_config.py
BINANCE_SYMBOL=BTCUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 python scripts/check_config.py
BINANCE_SYMBOL=XRPUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 python scripts/check_config.py
```

Required facts in each output:

```text
strategy_variant=original_pivot_reversal
position_size_pct=100
has_api_key=false unless explicitly loading a private env file
has_api_secret=false unless explicitly loading a private env file
```

## New Server Gate Sequence

1. Run the F2 migration checker first. Live deployment is allowed only if
   Binance Futures mainnet public REST returns HTTP 200 for ping, time,
   exchangeInfo, and bookTicker.

```bash
cd tools/f2_migration_checker
bash run_f2_check.sh
```

Required verdict:

```text
F2_MAINNET_REST_GO
```

2. Deploy project files to the server. Do not upload `.env`, `.venv`, logs,
   SQLite data, or secrets.

3. Create the server venv and run gates:

```bash
cd /root/ethusdc-pivot-bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python scripts/scan_secrets.py
python scripts/replay_forced_original_pivot_trigger.py
```

4. Write `.env.live.readonly` interactively on the server. The file must stay
   mode `600`.

```bash
bash scripts/write_live_readonly_env_interactive.sh
chmod 600 .env.live.readonly
```

5. Run signed read-only preflight for each profile before any strategy start.

```bash
set -a
. ./.env.live.readonly
set +a

LIVE_TRADING=false DRY_RUN=true BINANCE_ENV=mainnet BINANCE_SYMBOL=ETHUSDC BINANCE_INTERVAL=15m POSITION_SIZE_PCT=100 .venv/bin/python scripts/preflight_live_readonly.py
LIVE_TRADING=false DRY_RUN=true BINANCE_ENV=mainnet BINANCE_SYMBOL=BTCUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 .venv/bin/python scripts/preflight_live_readonly.py
LIVE_TRADING=false DRY_RUN=true BINANCE_ENV=mainnet BINANCE_SYMBOL=XRPUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 .venv/bin/python scripts/preflight_live_readonly.py
```

Required:

```text
SIGNED_READONLY_PREFLIGHT_GO
open_orders_count=0
position_amt=0
order_endpoint_called=False
live_trading_started=False
```

6. Install user-level service units only after explicit approval.

```bash
mkdir -p ~/.config/systemd/user
install -m 0644 deploy/systemd/ethusdc-pivot-bot-live-strategy.user.service ~/.config/systemd/user/ethusdc-pivot-bot-live-strategy.service
install -m 0644 deploy/systemd/btcusdc-pivot-bot-live-strategy.user.service ~/.config/systemd/user/btcusdc-pivot-bot-live-strategy.service
install -m 0644 deploy/systemd/xrpusdc-pivot-bot-live-strategy.user.service ~/.config/systemd/user/xrpusdc-pivot-bot-live-strategy.service
systemctl --user daemon-reload
```

7. Start live strategies only after final explicit approval.

```bash
systemctl --user start ethusdc-pivot-bot-live-strategy.service
systemctl --user start btcusdc-pivot-bot-live-strategy.service
systemctl --user start xrpusdc-pivot-bot-live-strategy.service
```

8. Install or run read-only monitors if requested.

```bash
install -m 0644 deploy/systemd/ethusdc-pivot-bot-live-monitor.user.service ~/.config/systemd/user/ethusdc-pivot-bot-live-monitor.service
install -m 0644 deploy/systemd/ethusdc-pivot-bot-live-monitor.user.timer ~/.config/systemd/user/ethusdc-pivot-bot-live-monitor.timer
install -m 0644 deploy/systemd/btcusdc-pivot-bot-live-monitor.user.service ~/.config/systemd/user/btcusdc-pivot-bot-live-monitor.service
install -m 0644 deploy/systemd/btcusdc-pivot-bot-live-monitor.user.timer ~/.config/systemd/user/btcusdc-pivot-bot-live-monitor.timer
install -m 0644 deploy/systemd/xrpusdc-pivot-bot-live-monitor.user.service ~/.config/systemd/user/xrpusdc-pivot-bot-live-monitor.service
install -m 0644 deploy/systemd/xrpusdc-pivot-bot-live-monitor.user.timer ~/.config/systemd/user/xrpusdc-pivot-bot-live-monitor.timer
systemctl --user daemon-reload
systemctl --user enable --now ethusdc-pivot-bot-live-monitor.timer btcusdc-pivot-bot-live-monitor.timer xrpusdc-pivot-bot-live-monitor.timer
```

## Existing Singapore Server Status Commands

```bash
ssh -i C:\Users\MR\.ssh1\id_ed25519 root@167.172.69.16
cd /root/ethusdc-pivot-bot
for u in ethusdc-pivot-bot-live-strategy.service btcusdc-pivot-bot-live-strategy.service xrpusdc-pivot-bot-live-strategy.service; do
  systemctl --user show "$u" -p ActiveState -p SubState -p UnitFileState -p NRestarts -p RuntimeMaxUSec --no-pager
done
```

Expected current state:

```text
ActiveState=inactive
SubState=dead
UnitFileState=disabled
```

## Stop All Strategies

```bash
systemctl --user stop ethusdc-pivot-bot-live-strategy.service btcusdc-pivot-bot-live-strategy.service xrpusdc-pivot-bot-live-strategy.service
systemctl --user disable ethusdc-pivot-bot-live-strategy.service btcusdc-pivot-bot-live-strategy.service xrpusdc-pivot-bot-live-strategy.service
```

Then run the signed read-only preflight commands above for all three symbols.
