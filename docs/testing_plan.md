# Testing Plan

## Unit Tests

The current suite covers:

- 15m interval lock and rejection of 1m, 5m, and 1h.
- Pivot high and pivot low delayed confirmation.
- Pine-style `hprice`, `lprice`, `le`, and `se` state transitions.
- Closed-candle-only pivot updates.
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
- Kline closed filtering: `k.x=false` does not call strategy update; `k.x=true` does.
- Locked stream name: `ethusdc@kline_15m`.
- Documentation check for the 30 minute pivot confirmation delay.

## Phase 2.5 Public Market Dry-Run

Goals:

- Observe real Binance public market data on `ethusdc@kline_15m`.
- Confirm unclosed 15m kline updates do not trigger strategy updates.
- Confirm a closed 15m candle is logged as `candle_closed_received` and then sent to the strategy.
- Confirm no signed order request is made.
- Confirm order behavior remains simulated through `DryRunExchange`.

If no 15m candle closes during a short local run, that is not a failure. The run should log that it is waiting or timed out without receiving a closed candle.

## Phase 3A.5 Tests

Additional coverage targets:

- REST 451 classification as `http_451_unavailable_for_legal_reasons_or_region_block`.
- Diagnosis target audit proving no signed endpoint and no `POST`, `PUT`, or `DELETE /fapi/v1/order`.
- WebSocket bookTicker parsing for `b`, `B`, `a`, and `A` as `Decimal`.
- Rejection of bad symbols and crossed books.
- WebSocket bookTicker provider waiting and stale snapshot rejection.
- Entry chaser refusal when no fresh bookTicker exists.
- Maker price calculation from WebSocket bookTicker for BUY and SELL.
- One-tick spread maker behavior.
- Cached filters allowed only for dry-run and rejected for live or default testnet signed order tests.
- Public WS-only safety guard and signed order method rejection.
- Kline `k.x=false` ignored; `k.x=true` updates strategy.
- Stop fallback remains `MARKET reduceOnly` only.
- Documentation gate for REST 451 no-testnet/no-live policy.

Phase 3A.5 validation commands:

```powershell
python -m pytest
python scripts/check_config.py
python scripts/scan_secrets.py
python scripts/diagnose_binance_connectivity.py
```

Connectivity diagnosis may report HTTP 451 or network failure. That is not a test failure; it is the risk gate that keeps the project in WebSocket-only public dry-run.

## Phase 3B Observation Plan

Phase 3B 1h observation GO conditions:

- User-level systemd unit installs without sudo.
- No system-wide unit is created.
- Boot autostart is not enabled.
- Service starts manually.
- Kline WebSocket and bookTicker WebSocket connect.
- Bid/ask and maker-price samples are recorded.
- `logs/phase3b_runtime_summary.json` is written.
- Signed order count is zero.
- Real order attempt count is zero.
- API keys are empty.
- No residual bot process remains after bounded runtime.

Phase 3B 6h observation is recommended only after 1h GO and explicit user approval. It remains dry-run, WebSocket-only, no API keys, and no signed orders.

Phase 3B 24h observation is recommended only after 6h GO. Closed candle count should match 15m expectations within normal connection tolerance; reconnects may occur but must not be continuous failures.

## Forced Original Pivot Trigger Replay

Real-market fast smoke can pass with `pending trigger events = 0`; that is not a failure because the market may not produce a breakout during a 20-30 minute window. Use the forced replay to validate the signal-present path without waiting for market conditions:

```powershell
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

## New Server F2 Migration Checker

Use the portable checker before spending time on a new server:

```powershell
python tools/f2_migration_checker/check_binance_futures_rest.py
python tools/f2_migration_checker/check_binance_futures_ws.py
```

Local REST 451 is allowed as a diagnostic result. The checker must not read keys, sign REST, or place orders. Live remains NO-GO unless mainnet public REST is reachable and later signed gates pass.

## Dry-Run Testing

Run:

```powershell
python -m pytest
python .\scripts\check_config.py
.\scripts\run_dry.ps1
```

## Later Testnet Plan

- Confirm ETHUSDC availability and filters from testnet `exchangeInfo`.
- Do not run testnet signed order tests while REST 451 exists or while cached filters are the only source.
- Run public market data only.
- Run dry-run using live market data but no order calls.
- Enable testnet API keys with tiny notional only after review.
- Verify order lifecycle events and reconciliation reports.

## Pre-Live Checklist

- Current Binance docs rechecked.
- Account mode confirmed as one-way.
- Margin mode and leverage manually confirmed.
- UFW, root cron, and auth logs reviewed on server.
- Systemd dry-run stable.
- State DB backup procedure tested.
- Alert path tested.
- Secret handling reviewed.
- Server or credit expiry reminder for 2026-08-01 acknowledged.
