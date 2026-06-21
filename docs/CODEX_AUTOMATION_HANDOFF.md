# Codex Automation Handoff

Paste this file to Codex when you want it to reproduce, audit, deploy, monitor,
or recover this project.

## Objective

Operate the current multi-symbol Pivot Bot workflow using this repository as
the source of truth. Preserve safety gates, avoid secrets leakage, and verify
every state transition with command output.

## Current Strategy Set

All configured live strategy wrappers use:

```text
STRATEGY_VARIANT=original_pivot_reversal
ORDER_MODE=account_equity_pct
POSITION_SIZE_PCT=100
STOP_LOSS_ENABLED=false
TAKE_PROFIT_ENABLED=false
```

| Symbol | Interval | Strategy service | Monitor timer |
| --- | --- | --- | --- |
| `ETHUSDC` | `15m` | `ethusdc-pivot-bot-live-strategy.service` | `ethusdc-pivot-bot-live-monitor.timer` |
| `BTCUSDC` | `1h` | `btcusdc-pivot-bot-live-strategy.service` | `btcusdc-pivot-bot-live-monitor.timer` |
| `XRPUSDC` | `1h` | `xrpusdc-pivot-bot-live-strategy.service` | `xrpusdc-pivot-bot-live-monitor.timer` |

## Current Server State

Snapshot: `2026-06-21`.

- Server: `root@167.172.69.16`
- Project path: `/root/ethusdc-pivot-bot`
- SSH key path used by the operator: `C:\Users\MR\.ssh1\id_ed25519`
- Strategy services: stopped and disabled.
- Stop verification:
  - ETHUSDC signed read-only preflight: `SIGNED_READONLY_PREFLIGHT_GO`
  - BTCUSDC signed read-only preflight: `SIGNED_READONLY_PREFLIGHT_GO`
  - XRPUSDC signed read-only preflight: `SIGNED_READONLY_PREFLIGHT_GO`
  - open orders: `0`
  - position quantity: `0`
  - preflight order endpoint called: `false`

Read-only monitor timers may be installed. They are not trading strategies and
must not place, amend, cancel, or close orders.

## Non-Negotiable Rules

- Never ask the user to paste an SSH private key or Binance API key into chat.
- Never commit `.env`, `.env.live.readonly`, `.venv`, logs, SQLite data, or
  private keys.
- Never place manual orders unless the user explicitly asks in the current
  thread.
- Never use `MARKET` entry.
- Never use `STOP_MARKET` entry.
- Never restore the old Safer close gate.
- Use `LIMIT` + `GTX` maker entry only.
- Stop fallback may use `MARKET reduceOnly` only for remaining position
  quantity after maker stop chase timeout.
- Do not assume TradingView fills equal live maker fills.
- Do not start any strategy service unless the user explicitly asks in the
  current thread.

## Required Local Checks

Run these before packaging, server deploy, or GitHub publication:

```bash
python -m pytest
python scripts/scan_secrets.py
python scripts/check_config.py
python scripts/replay_forced_original_pivot_trigger.py
```

Run explicit config checks for each live profile:

```bash
BINANCE_SYMBOL=ETHUSDC BINANCE_INTERVAL=15m POSITION_SIZE_PCT=100 python scripts/check_config.py
BINANCE_SYMBOL=BTCUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 python scripts/check_config.py
BINANCE_SYMBOL=XRPUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 python scripts/check_config.py
```

Expected:

```text
pytest passed
secret_scan=passed
strategy_variant=original_pivot_reversal
position_size_pct=100
live_trading=false for config checks unless explicitly running a live wrapper
```

## Status Check Commands

```bash
ssh -i C:\Users\MR\.ssh1\id_ed25519 root@167.172.69.16
cd /root/ethusdc-pivot-bot

for u in \
  ethusdc-pivot-bot-live-strategy.service \
  btcusdc-pivot-bot-live-strategy.service \
  xrpusdc-pivot-bot-live-strategy.service
do
  systemctl --user show "$u" -p ActiveState -p SubState -p UnitFileState -p NRestarts -p RuntimeMaxUSec --no-pager
done
```

Expected stopped state:

```text
ActiveState=inactive
SubState=dead
UnitFileState=disabled
```

## Signed Read-Only Preflight

These commands read account state only. They must not call order endpoints.

```bash
cd /root/ethusdc-pivot-bot
set -a
. ./.env.live.readonly
set +a

LIVE_TRADING=false DRY_RUN=true BINANCE_ENV=mainnet BINANCE_SYMBOL=ETHUSDC BINANCE_INTERVAL=15m POSITION_SIZE_PCT=100 \
  LIVE_READONLY_PREFLIGHT_JSON_REPORT=reports/stop_all_preflight_ETHUSDC_15m.json \
  LIVE_READONLY_PREFLIGHT_MD_REPORT=docs/stop_all_preflight_ETHUSDC_15m.md \
  .venv/bin/python scripts/preflight_live_readonly.py

LIVE_TRADING=false DRY_RUN=true BINANCE_ENV=mainnet BINANCE_SYMBOL=BTCUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 \
  LIVE_READONLY_PREFLIGHT_JSON_REPORT=reports/stop_all_preflight_BTCUSDC_1h.json \
  LIVE_READONLY_PREFLIGHT_MD_REPORT=docs/stop_all_preflight_BTCUSDC_1h.md \
  .venv/bin/python scripts/preflight_live_readonly.py

LIVE_TRADING=false DRY_RUN=true BINANCE_ENV=mainnet BINANCE_SYMBOL=XRPUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 \
  LIVE_READONLY_PREFLIGHT_JSON_REPORT=reports/stop_all_preflight_XRPUSDC_1h.json \
  LIVE_READONLY_PREFLIGHT_MD_REPORT=docs/stop_all_preflight_XRPUSDC_1h.md \
  .venv/bin/python scripts/preflight_live_readonly.py
```

Expected:

```text
final_verdict=SIGNED_READONLY_PREFLIGHT_GO
order_endpoint_called=False
live_trading_started=False
open_orders_count=0
position_amt=0
```

## Stop All Strategies

Stopping strategies is allowed when requested. It does not cancel exchange
orders and does not close exchange positions.

```bash
systemctl --user stop \
  ethusdc-pivot-bot-live-strategy.service \
  btcusdc-pivot-bot-live-strategy.service \
  xrpusdc-pivot-bot-live-strategy.service

systemctl --user disable \
  ethusdc-pivot-bot-live-strategy.service \
  btcusdc-pivot-bot-live-strategy.service \
  xrpusdc-pivot-bot-live-strategy.service
```

After stopping, always run signed read-only preflight for all three symbols.

## Start Strategy Services

Only after explicit current-thread approval:

```bash
systemctl --user start ethusdc-pivot-bot-live-strategy.service
systemctl --user start btcusdc-pivot-bot-live-strategy.service
systemctl --user start xrpusdc-pivot-bot-live-strategy.service
```

Then immediately run monitor wrappers:

```bash
bash scripts/run_live_monitor_status.sh
bash scripts/run_live_monitor_status_btcusdc_1h.sh
bash scripts/run_live_monitor_status_xrpusdc_1h.sh
```

## What To Report

Report concise evidence:

- service active/inactive and enabled/disabled
- `RuntimeMaxUSec`
- `NRestarts`
- open orders
- position amount
- latest market heartbeat
- abnormal events
- tests and gates run
- whether any order endpoint was called by a check

Do not dump secrets or raw `.env.live.readonly`.
