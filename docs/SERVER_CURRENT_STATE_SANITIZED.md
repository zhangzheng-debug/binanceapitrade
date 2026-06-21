# Server Current State Sanitized

Snapshot UTC: `2026-06-21T11:11:26Z`

This file contains operational state only. It intentionally excludes API keys,
API secrets, SSH private keys, `.env.live.readonly`, raw logs, and SQLite data.

## Server

- Provider/location: DigitalOcean Singapore
- Public IPv4: `167.172.69.16`
- SSH user: `root`
- SSH key path used by the operator: `C:\Users\MR\.ssh1\id_ed25519`
- Project path: `/root/ethusdc-pivot-bot`

## Strategy Services

All live strategy services were stopped and disabled on `2026-06-21`.

```text
ethusdc-pivot-bot-live-strategy.service:
  ActiveState=inactive
  SubState=dead
  UnitFileState=disabled
  MainPID=0
  NRestarts=0

btcusdc-pivot-bot-live-strategy.service:
  ActiveState=inactive
  SubState=dead
  UnitFileState=disabled
  MainPID=0
  NRestarts=0

xrpusdc-pivot-bot-live-strategy.service:
  ActiveState=inactive
  SubState=dead
  UnitFileState=disabled
  MainPID=0
  NRestarts=0
```

## Read-Only Stop Verification

After stopping the strategies, signed read-only preflight was run for all three
symbols. The script permits only signed `GET` account/position/open-orders
queries and forbids order endpoints.

```text
ETHUSDC 15m:
  final_verdict=SIGNED_READONLY_PREFLIGHT_GO
  open_orders_count=0
  position_amt=0
  order_endpoint_called=False
  live_trading_started=False

BTCUSDC 1h:
  final_verdict=SIGNED_READONLY_PREFLIGHT_GO
  open_orders_count=0
  position_amt=0
  order_endpoint_called=False
  live_trading_started=False

XRPUSDC 1h:
  final_verdict=SIGNED_READONLY_PREFLIGHT_GO
  open_orders_count=0
  position_amt=0
  order_endpoint_called=False
  live_trading_started=False
```

## Current Live Profile Facts

These are the live wrapper profiles installed in the repository. They are not
currently running.

| Symbol | Interval | Service | Position size |
| --- | --- | --- | --- |
| `ETHUSDC` | `15m` | `ethusdc-pivot-bot-live-strategy.service` | `100%` account equity |
| `BTCUSDC` | `1h` | `btcusdc-pivot-bot-live-strategy.service` | `100%` account equity |
| `XRPUSDC` | `1h` | `xrpusdc-pivot-bot-live-strategy.service` | `100%` account equity |

Common live wrapper settings:

```text
DRY_RUN=false
LIVE_TRADING=true
BINANCE_ENV=mainnet
STRATEGY_VARIANT=original_pivot_reversal
ORDER_MODE=account_equity_pct
POSITION_SIZE_PCT=100
STOP_LOSS_ENABLED=false
TAKE_PROFIT_ENABLED=false
LIVE_STRATEGY_MAX_ENTRY_FILLS=0
LIVE_STRATEGY_RESUME_EXISTING_POSITION=true
```

## Monitor Timers

Read-only monitor timers may remain installed. They write JSON/Markdown status
reports and should not place, amend, cancel, or close orders.

Report paths:

```text
reports/live_monitor_status_ETHUSDC_15m.json
reports/live_monitor_status_BTCUSDC_1h.json
reports/live_monitor_status_XRPUSDC_1h.json
docs/live_monitor_status_ETHUSDC_15m.md
docs/live_monitor_status_BTCUSDC_1h.md
docs/live_monitor_status_XRPUSDC_1h.md
```

## Safety Note

Stopping strategy services does not itself cancel exchange orders or close
exchange positions. The stop verification above showed no open orders and no
positions at the time of this snapshot.
