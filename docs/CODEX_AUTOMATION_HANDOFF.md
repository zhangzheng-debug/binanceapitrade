# Codex Automation Handoff

Paste this file to Codex when you want it to reproduce, audit, deploy, monitor, or recover this project.

## Objective

Own the ETHUSDC Pivot Bot workflow end to end using the current repository as source of truth. Preserve safety gates, avoid secrets leakage, and verify every state transition with command output.

## Non-Negotiable Rules

- Never ask the user to paste an SSH private key or Binance API key into chat.
- Never commit `.env`, `.env.live.readonly`, `.venv`, logs, SQLite data, or private keys.
- Never place manual orders unless the user explicitly asks in the current thread.
- Never use `MARKET` entry.
- Never use `STOP_MARKET` entry.
- Never change `BINANCE_INTERVAL=15m`.
- Never restore the old Safer close gate.
- Use `LIMIT` + `GTX` maker entry only.
- Stop fallback may use `MARKET reduceOnly` only for remaining position quantity after maker stop chase timeout.

## Expected Repository Checks

Run these first:

```bash
python -m pytest -q
python scripts/scan_secrets.py
python scripts/check_config.py
python scripts/replay_forced_original_pivot_trigger.py
```

Expected:

```text
pytest passed
secret_scan=passed
forced replay passed
market_entry_order_attempt_count=0
stop_market_order_attempt_count=0
signed_rest_call_count=0
real_order_attempt_count=0
```

## Current Server Context

- Server: `root@167.172.69.16`
- Project path: `/root/ethusdc-pivot-bot`
- SSH key path used by the operator: `C:\Users\MR\.ssh1\id_ed25519`
- Live strategy service: `ethusdc-pivot-bot-live-strategy.service`
- Read-only monitor timer: `ethusdc-pivot-bot-live-monitor.timer`
- Monitor status files:
  - `/root/ethusdc-pivot-bot/reports/live_monitor_status.json`
  - `/root/ethusdc-pivot-bot/docs/live_monitor_status.md`

## Current Expected Runtime State

```text
live strategy service: active/enabled
monitor timer: active/enabled
RuntimeMaxUSec: infinity
root linger: yes
open_orders: 0
managed marker: ETHUSDC LONG 2.444 @ 1728.88
```

Do not treat the existing nonzero position as an alert by itself. Alert only if it changes, becomes flat unexpectedly, open orders become nonzero, the marker mismatches, the service/timer fails, or new order/stop/error events appear.

## Common Tasks

### Status Check

```bash
ssh -i C:\Users\MR\.ssh1\id_ed25519 root@167.172.69.16
cd /root/ethusdc-pivot-bot
systemctl --user is-active ethusdc-pivot-bot-live-strategy.service
systemctl --user is-enabled ethusdc-pivot-bot-live-strategy.service
systemctl --user is-active ethusdc-pivot-bot-live-monitor.timer
systemctl --user is-enabled ethusdc-pivot-bot-live-monitor.timer
cat docs/live_monitor_status.md
```

### Server Read-Only Monitor Run

```bash
cd /root/ethusdc-pivot-bot
bash scripts/run_live_monitor_status.sh
cat docs/live_monitor_status.md
```

### Refresh Code on Server

1. Run local tests and `scan_secrets`.
2. Make a deploy bundle with `scripts/make_deploy_bundle.py`.
3. Upload only the bundle.
4. Back up the server project before extracting.
5. Extract, run server tests, run `scan_secrets`, then restart only if the task requires it.

### Start Long Live Strategy From Flat

Only after all gates are GO and the user explicitly approves:

```bash
export I_APPROVE_FINAL_LIVE_STRATEGY_USER_SERVICE=YES
bash scripts/install_final_live_strategy_user_service.sh
export I_APPROVE_FINAL_LIVE_STRATEGY_START=YES
bash scripts/start_final_live_strategy_user_service.sh
bash scripts/install_live_monitor_user_timer.sh
```

## What To Report

Report concise evidence:

- service active/enabled
- timer active/enabled
- RuntimeMaxUSec
- NRestarts
- open orders
- position amount
- marker match
- latest market heartbeat
- abnormal events
- tests/gates run

Do not dump secrets or raw `.env.live.readonly`.
