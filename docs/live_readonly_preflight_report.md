# Live Read-Only Preflight Report

Snapshot UTC: `2026-06-21T11:11:26Z`

Scope: Binance USD-M Futures mainnet signed read-only preflight after stopping
all strategy services.

Order placement, modify, cancel, and close endpoints are forbidden in this
script. API key and secret are not printed in this report.

## Summary

| Symbol | Interval | Position size | Verdict | Open orders | Position amount |
| --- | --- | --- | --- | --- | --- |
| `ETHUSDC` | `15m` | `100%` | `SIGNED_READONLY_PREFLIGHT_GO` | `0` | `0` |
| `BTCUSDC` | `1h` | `100%` | `SIGNED_READONLY_PREFLIGHT_GO` | `0` | `0` |
| `XRPUSDC` | `1h` | `100%` | `SIGNED_READONLY_PREFLIGHT_GO` | `0` | `0` |

## Safety

```text
key_secret_printed=False
order_endpoint_called=False
live_trading_started=False
filters_source=EXCHANGE_INFO_REST
```

## Interpretation

At this snapshot, all live strategy services were stopped/disabled and no
tracked symbol had an open position or open order. This does not imply a future
start is safe without a fresh preflight.
