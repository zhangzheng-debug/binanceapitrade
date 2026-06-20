# Architecture

## Strategy Layer

`PivotReversalStrategy` consumes only closed candles. It preserves the Pine state fields `hprice`, `lprice`, `le`, and `se`, and confirms pivots only after `rightBars` candles have closed.

## Execution Layer

`MakerChaser` handles entry and stop chasing. Entry uses `LIMIT GTX` only and never falls back to `MARKET`. Stop chasing uses `LIMIT GTX reduceOnly` first, then `MARKET reduceOnly` after timeout for the remaining quantity.

## Risk Layer

`RiskManager` blocks add-ons, averaging down, reversals, parallel entry chases, and entries during stop chases. The initial stop trigger supports a fixed percentage setting.

## State Persistence

`StateStore` creates SQLite tables for bot state, strategy state, candles, orders, position snapshots, reconciliation reports, and events. API secrets are never stored.

## Binance API Adapter

`BinanceClient` has public market-data helpers and signed REST method skeletons for orders, modify, cancel, query, open orders, position, and market reduce-only. Real order paths are guarded by `LIVE_TRADING=true` and `DRY_RUN=false`.

## Dry-Run Adapter

`DryRunExchange` simulates order placement, modification, cancellation, fills, post-only rejection, and market reduce-only close events without sending real Binance orders.

## Reconciliation

`reconcile` trusts local state in dry-run. In live mode it compares local and exchange positions plus open orders; mismatches stop startup by default and produce a report.

