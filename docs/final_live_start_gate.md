# Final Live Start Gate

Snapshot UTC: `2026-06-21T11:11:26Z`

Final verdict: `FINAL_LIVE_START_GATE_NO_GO`

Reason: all strategy services were intentionally stopped and disabled before
packaging. A future live start requires explicit current-thread approval and a
fresh gate run.

## Current Strategy Profiles

| Symbol | Interval | Position size | Service state |
| --- | --- | --- | --- |
| `ETHUSDC` | `15m` | `100%` account equity | stopped/disabled |
| `BTCUSDC` | `1h` | `100%` account equity | stopped/disabled |
| `XRPUSDC` | `1h` | `100%` account equity | stopped/disabled |

## Last Stop Verification

Signed read-only preflight was run after stopping services.

```text
ETHUSDC: SIGNED_READONLY_PREFLIGHT_GO, open_orders=0, position_amt=0
BTCUSDC: SIGNED_READONLY_PREFLIGHT_GO, open_orders=0, position_amt=0
XRPUSDC: SIGNED_READONLY_PREFLIGHT_GO, open_orders=0, position_amt=0
```

Safety:

```text
order_endpoint_called=False
live_trading_started=False
key_secret_printed=False
```

## Required Before Any Future Start

```bash
python -m pytest
python scripts/scan_secrets.py
python scripts/replay_forced_original_pivot_trigger.py
```

Then run signed read-only preflight for every symbol and start services only
after explicit approval.
