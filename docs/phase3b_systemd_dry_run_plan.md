# Phase 3B Systemd Dry-Run Plan

Phase 3B can only be a WebSocket-only systemd dry-run while REST 451 remains unresolved. It is not testnet signed order testing and it is not live trading.

## Purpose

- Observe WebSocket kline stability.
- Observe WebSocket bookTicker stability.
- Observe reconnect behavior.
- Observe `logs/events.jsonl`, journal output, memory, disk, and CPU usage.
- Exercise process restart behavior without API keys or signed order calls.

## Entry Conditions

- Phase 3A.5 server pytest passes.
- `scripts/check_config.py` passes with `DRY_RUN=true`, `LIVE_TRADING=false`, `PUBLIC_MARKET_DRY_RUN=true`, and `PUBLIC_MARKET_WS_ONLY=true`.
- `scripts/scan_secrets.py` passes.
- WebSocket kline via `/market` passes.
- WebSocket bookTicker via `/public` passes.
- No signed order endpoint is called.
- No real order is sent.
- No bounded-run background process remains.
- User gives explicit approval to install a dry-run service.

## Run Durations

- First run: 1 hour.
- Second run: 6 hours.
- Third run: 24 hours.

Each stage checks `journalctl`, `logs/events.jsonl`, memory, disk, process state, WebSocket reconnect count, closed candle count, and bookTicker stale count.

## Non-Goals

- Phase 3B does not solve REST 451.
- Phase 3B does not validate signed REST.
- Phase 3B does not allow testnet orders.
- Phase 3B does not allow live trading.
- Phase 3B does not allow API keys.

REST 451 still blocks Phase 3C testnet signed order and Phase 4 live.
