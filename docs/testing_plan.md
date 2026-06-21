# Testing Plan

## Unit Tests

The current suite covers:

- Supported symbol/interval matrix:
  - `ETHUSDC` `15m`
  - `BTCUSDC` `1h`
  - `XRPUSDC` `1h`
- Rejection of unsupported symbols and unsupported intervals.
- Pivot high and pivot low delayed confirmation.
- Pine-style `hprice`, `lprice`, `le`, and `se` state transitions.
- Closed-candle-only pivot updates.
- Dynamic kline stream names for supported profiles.
- Dynamic bookTicker stream names for supported profiles.
- Maker price rules for one-tick and wider spreads.
- Decimal price and quantity quantization.
- `exchangeInfo` filter parsing.
- Entry timeout cancellation without market entry.
- Entry partial fill handling.
- Entry post-only rejection retry behavior.
- Stop maker fill without market fallback.
- Stop timeout market reduce-only fallback.
- Stop partial fill market reduce-only remainder.
- Risk blocks for open positions and active chases.
- Dry-run safety gates.
- Live config rejection without API keys.
- Reconciliation mismatch behavior.
- Public market dry-run config without API keys.
- Kline closed filtering: `k.x=false` does not call strategy update; `k.x=true`
  does.
- Final live service wrappers for ETHUSDC, BTCUSDC, and XRPUSDC.
- `POSITION_SIZE_PCT=100` current sizing behavior.

## Required Local Validation

```bash
python -m pytest
python scripts/scan_secrets.py
python scripts/check_config.py
python scripts/replay_forced_original_pivot_trigger.py
```

Profile-specific config checks:

```bash
BINANCE_SYMBOL=ETHUSDC BINANCE_INTERVAL=15m POSITION_SIZE_PCT=100 python scripts/check_config.py
BINANCE_SYMBOL=BTCUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 python scripts/check_config.py
BINANCE_SYMBOL=XRPUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 python scripts/check_config.py
```

## Forced Original Pivot Trigger Replay

Real-market fast smoke can pass with `pending trigger events = 0`; that is not a
failure because the market may not produce a breakout during a short window. Use
the forced replay to validate the signal-present path without waiting for market
conditions:

```bash
python scripts/replay_forced_original_pivot_trigger.py
```

This must prove:

- pending long and short triggers are created from original Pine state;
- unclosed kline updates can trigger those pending stops;
- maker chaser starts from the trigger event;
- dry-run entry orders are `LIMIT + GTX`;
- MARKET entry count is zero;
- STOP_MARKET entry count is zero;
- signed REST and real order counts are zero;
- ambiguous dual triggers are skipped;
- active chase and existing position block new entries;
- missed closed-candle trigger logging works.

Outputs:

- `reports/forced_original_pivot_trigger_replay.json`
- `docs/forced_original_pivot_trigger_replay_report.md`

## Public Market Dry-Run

Goals:

- Observe real Binance public market data for the selected symbol/interval.
- Confirm unclosed kline updates do not update strategy pivots.
- Confirm a closed candle is logged as `candle_closed_received` and then sent to
  the strategy.
- Confirm no signed order request is made.
- Confirm order behavior remains simulated through `DryRunExchange`.

If no candle closes during a short local run, that is not a failure. The run
should log that it is waiting or timed out without receiving a closed candle.

## F2 Migration Checker

Use the portable checker before spending time on a new server:

```bash
cd tools/f2_migration_checker
bash run_f2_check.sh
```

The checker must not read keys, sign REST, or place orders. Live remains NO-GO
unless mainnet public REST is reachable and later signed gates pass.

## Signed Read-Only Preflight

Run preflight for each active profile before starting any strategy and after
stopping strategies:

```bash
LIVE_TRADING=false DRY_RUN=true BINANCE_ENV=mainnet BINANCE_SYMBOL=ETHUSDC BINANCE_INTERVAL=15m POSITION_SIZE_PCT=100 python scripts/preflight_live_readonly.py
LIVE_TRADING=false DRY_RUN=true BINANCE_ENV=mainnet BINANCE_SYMBOL=BTCUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 python scripts/preflight_live_readonly.py
LIVE_TRADING=false DRY_RUN=true BINANCE_ENV=mainnet BINANCE_SYMBOL=XRPUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 python scripts/preflight_live_readonly.py
```

Expected:

```text
SIGNED_READONLY_PREFLIGHT_GO
open_orders_count=0
position_amt=0
order_endpoint_called=False
live_trading_started=False
```

## Pre-Live Checklist

- Current Binance docs rechecked.
- Account mode confirmed as One-way.
- Margin mode and leverage manually confirmed.
- API key IP whitelist confirmed.
- REST `exchangeInfo` source confirmed for each symbol.
- Signed read-only preflight GO for every symbol.
- Secret handling reviewed.
- Strategy services started only after explicit approval.
- Monitor report shows no unexpected orders, positions, restarts, or abnormal
  events.
