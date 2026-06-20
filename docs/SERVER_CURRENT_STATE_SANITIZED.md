# Server Current State Sanitized

Snapshot UTC: `2026-06-20T21:48:31Z`

This file contains operational state only. It intentionally excludes API keys, API secrets, SSH private keys, `.env.live.readonly`, raw logs, and SQLite data.

## Server

- Provider/location: DigitalOcean Singapore
- Public IPv4: `167.172.69.16`
- SSH user: `root`
- SSH key path used by the operator: `C:\Users\MR\.ssh1\id_ed25519`
- Hostname: `ubuntu-s-2vcpu-2gb-sgp1`
- Project path: `/root/ethusdc-pivot-bot`

## Live Strategy Service

```text
systemctl --user is-active ethusdc-pivot-bot-live-strategy.service -> active
systemctl --user is-enabled ethusdc-pivot-bot-live-strategy.service -> enabled
RuntimeMaxUSec=infinity
MainPID=32768
NRestarts=0
ActiveState=active
SubState=running
loginctl show-user root -p Linger --value -> yes
```

## Read-Only Monitor Timer

```text
systemctl --user is-active ethusdc-pivot-bot-live-monitor.timer -> active
systemctl --user is-enabled ethusdc-pivot-bot-live-monitor.timer -> enabled
Timer schedule -> every 15 minutes via OnCalendar=*:0/15
```

Monitor output paths:

```text
/root/ethusdc-pivot-bot/reports/live_monitor_status.json
/root/ethusdc-pivot-bot/docs/live_monitor_status.md
```

Latest manual monitor check before packaging:

```text
status=OK
open_orders=0
position=LONG 2.444
marker_matches=True
```

## Live Configuration Facts

- `DRY_RUN=false`
- `LIVE_TRADING=true`
- `BINANCE_ENV=mainnet`
- `BINANCE_SYMBOL=ETHUSDC`
- `BINANCE_INTERVAL=15m`
- `STRATEGY_VARIANT=original_pivot_reversal`
- `ORDER_MODE=account_equity_pct`
- `POSITION_SIZE_PCT=200`
- `LIVE_STRATEGY_MAX_ENTRY_FILLS=0`
- `LIVE_STRATEGY_RESUME_EXISTING_POSITION=true`
- `LIVE_MANAGED_POSITION_MARKER_PATH=data/live_managed_position.json`

## Current Managed Position

The live managed-position marker on the server records:

```text
symbol=ETHUSDC
side=LONG
quantity=2.444
entry_price=1728.88
```

This is not a recommendation to open a position. It is only the sanitized state at the time this package was prepared.
