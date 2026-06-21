# Operations Runbook

## Current Server

- Server: `root@167.172.69.16`
- Project: `/root/ethusdc-pivot-bot`
- SSH key path used by the operator: `C:\Users\MR\.ssh1\id_ed25519`
- Current strategy state: all strategy services stopped and disabled.

## Strategy Services

| Symbol | Interval | Service | Wrapper |
| --- | --- | --- | --- |
| `ETHUSDC` | `15m` | `ethusdc-pivot-bot-live-strategy.service` | `scripts/run_final_live_strategy.sh` |
| `BTCUSDC` | `1h` | `btcusdc-pivot-bot-live-strategy.service` | `scripts/run_final_live_strategy_btcusdc_1h.sh` |
| `XRPUSDC` | `1h` | `xrpusdc-pivot-bot-live-strategy.service` | `scripts/run_final_live_strategy_xrpusdc_1h.sh` |

All wrappers use `POSITION_SIZE_PCT=100` and
`STRATEGY_VARIANT=original_pivot_reversal`.

## Local Validation

```powershell
cd D:\quant\ETH15min\ethusdc-pivot-bot
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\scan_secrets.py
.\.venv\Scripts\python.exe scripts\replay_forced_original_pivot_trigger.py
```

Config checks:

```powershell
$env:BINANCE_SYMBOL='ETHUSDC'; $env:BINANCE_INTERVAL='15m'; $env:POSITION_SIZE_PCT='100'; .\.venv\Scripts\python.exe scripts\check_config.py
$env:BINANCE_SYMBOL='BTCUSDC'; $env:BINANCE_INTERVAL='1h'; $env:POSITION_SIZE_PCT='100'; .\.venv\Scripts\python.exe scripts\check_config.py
$env:BINANCE_SYMBOL='XRPUSDC'; $env:BINANCE_INTERVAL='1h'; $env:POSITION_SIZE_PCT='100'; .\.venv\Scripts\python.exe scripts\check_config.py
```

## Stop All Strategies

Stopping strategies is allowed when requested. It does not cancel exchange
orders and does not close exchange positions.

```bash
ssh -i C:\Users\MR\.ssh1\id_ed25519 root@167.172.69.16

systemctl --user stop \
  ethusdc-pivot-bot-live-strategy.service \
  btcusdc-pivot-bot-live-strategy.service \
  xrpusdc-pivot-bot-live-strategy.service

systemctl --user disable \
  ethusdc-pivot-bot-live-strategy.service \
  btcusdc-pivot-bot-live-strategy.service \
  xrpusdc-pivot-bot-live-strategy.service
```

Verify stopped state:

```bash
for u in \
  ethusdc-pivot-bot-live-strategy.service \
  btcusdc-pivot-bot-live-strategy.service \
  xrpusdc-pivot-bot-live-strategy.service
do
  systemctl --user show "$u" -p ActiveState -p SubState -p UnitFileState -p MainPID -p NRestarts --no-pager
done
```

Expected:

```text
ActiveState=inactive
SubState=dead
UnitFileState=disabled
MainPID=0
```

## Signed Read-Only Verification

Run after stop-all and before any future start. These commands must not call
order endpoints.

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
open_orders_count=0
position_amt=0
order_endpoint_called=False
live_trading_started=False
```

## Start Strategies

Start only after explicit current-thread approval and fresh signed read-only
preflight.

```bash
systemctl --user start ethusdc-pivot-bot-live-strategy.service
systemctl --user start btcusdc-pivot-bot-live-strategy.service
systemctl --user start xrpusdc-pivot-bot-live-strategy.service
```

Check status:

```bash
for u in \
  ethusdc-pivot-bot-live-strategy.service \
  btcusdc-pivot-bot-live-strategy.service \
  xrpusdc-pivot-bot-live-strategy.service
do
  systemctl --user show "$u" -p ActiveState -p SubState -p UnitFileState -p NRestarts -p RuntimeMaxUSec --no-pager
done
```

## Read-Only Monitors

Manual monitor run:

```bash
cd /root/ethusdc-pivot-bot
bash scripts/run_live_monitor_status.sh
bash scripts/run_live_monitor_status_btcusdc_1h.sh
bash scripts/run_live_monitor_status_xrpusdc_1h.sh
```

Report files:

```text
reports/live_monitor_status_ETHUSDC_15m.json
reports/live_monitor_status_BTCUSDC_1h.json
reports/live_monitor_status_XRPUSDC_1h.json
docs/live_monitor_status_ETHUSDC_15m.md
docs/live_monitor_status_BTCUSDC_1h.md
docs/live_monitor_status_XRPUSDC_1h.md
```

## F2 Migration Check

Before using a replacement server, copy `tools/f2_migration_checker/` and run:

```bash
cd tools/f2_migration_checker
bash run_f2_check.sh
cat f2_migration_check_result.json
```

If mainnet REST returns 451, that server is not suitable for Binance Futures
live. Do not use proxy, VPN, tunnel, firewall changes, or other bypass behavior.

## Public Market Dry-Run

Public dry-run does not require API keys and does not send signed order
requests. Set symbol and interval explicitly when testing non-default profiles.

```bash
BINANCE_SYMBOL=ETHUSDC BINANCE_INTERVAL=15m bash scripts/run_public_market_dry.sh
BINANCE_SYMBOL=BTCUSDC BINANCE_INTERVAL=1h bash scripts/run_public_market_dry.sh
BINANCE_SYMBOL=XRPUSDC BINANCE_INTERVAL=1h bash scripts/run_public_market_dry.sh
```

## Logs And State

- Human logs: `logs/<SYMBOL_INTERVAL>/bot.log`
- JSON events: `logs/<SYMBOL_INTERVAL>/events.jsonl`
- SQLite state: `data/state_<SYMBOL>_<INTERVAL>.sqlite3`

Do not commit logs or SQLite files.

## API Errors

- Post-only would take: retry maker-only path.
- Timestamp drift: sync server time and retry safely.
- Rate limit: back off.
- Network timeout: retry only idempotent reads automatically.
- Unknown order mutation result: reconcile before any further mutation.
- Unknown error: alert and stop live order flow.

## Calendar Reminder

Server or credit expiry: `2026-08-01`. This is a calendar item, not a current
development blocker.
