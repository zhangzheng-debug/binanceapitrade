# Phase 3A.5 REST 451 WebSocket-Only Fallback Report

Generated: 2026-06-20

## Why Phase 3A.5 Exists

Phase 3A proved the server can run the bot safely in public dry-run, but Binance public REST returned HTTP 451 from the server. REST 451 means the environment is not suitable for testnet signed order testing or live trading. Phase 3A.5 locks that risk into code, tests, docs, and runtime checks while allowing public WebSocket-only dry-run.

Core rule: REST 451 unresolved means public WebSocket-only dry-run only. No API key, no signed REST, no testnet order, no live.

## Phase 3A Summary

- Project path: `/home/dev/ethusdc-pivot-bot`
- Existing unrelated workload: `/home/dev/ai-rtl-studio` and a Python service on `127.0.0.1:18081`; untouched.
- Phase 3A server pytest: `43 passed`.
- Phase 3A server config: `ETHUSDC`, `15m`, `dry_run=true`, `live_trading=false`, no API key.
- Phase 3A server REST `exchangeInfo` and REST `bookTicker`: HTTP 451.
- Phase 3A server kline WebSocket: connected to `ethusdc@kline_15m`; unclosed updates received; no closed 15m candle inside the bounded window.
- No signed order, no live trading, no real order, no residual bot process.

## Local Validation

- Pytest: `72 passed`.
- `scripts/check_config.py`: passed with default local dry-run settings, `ETHUSDC`, `15m`, `dry_run=true`, `live_trading=false`, no API key.
- `scripts/scan_secrets.py`: passed, `findings_count=0`.
- `scripts/diagnose_binance_connectivity.py`: completed and wrote `reports/binance_connectivity_diagnosis.json`.

Local diagnosis:

- Mainnet public REST `ping`, `time`, `exchangeInfo`, and `bookTicker`: HTTP 451.
- HTTP 451 classification: `http_451_unavailable_for_legal_reasons_or_region_block`.
- HTTP 451 action: `report_only_no_bypass`.
- Testnet public REST `ping`, `time`, `exchangeInfo`, and `bookTicker`: HTTP 200.
- Mainnet kline WebSocket: local bounded check timed out during opening handshake.
- Mainnet bookTicker WebSocket: passed; parsed ETHUSDC bid/ask as `Decimal`.
- No API key was read and no signed/order endpoint was called.

## Server Validation

- Deployed bundle SHA256: `c36524a1b47f18db2edf08c743fd624eb0b12488626048e2be23926944d0d2f5`.
- Server backup created before final deployment: `/home/dev/ethusdc-pivot-bot-prev-phase3a5-20260620-094703`.
- Server pytest: `72 passed`.
- Server `scripts/check_config.py`: `dry_run=true`, `live_trading=false`, `public_market_dry_run=true`, `public_market_ws_only=true`, `allow_cached_exchange_filters_in_dry_run=true`, `ETHUSDC`, `15m`, no API key, no API secret.
- Server `scripts/scan_secrets.py`: passed, `findings_count=0`.
- Server diagnosis: REST 451 still present; kline WebSocket passed; bookTicker WebSocket passed.

Server bounded runtime:

- Clean bounded run: `PUBLIC_MARKET_DRY_RUN_SECONDS=90 timeout 120 bash scripts/run_public_market_ws_only_dry.sh`.
- Exit code: `0`.
- Runtime logged `ws_only_fallback_enabled`.
- Runtime logged `rest_451_detected` for REST `exchangeInfo`.
- Runtime loaded cached filters with `filter_source=CACHED_DRY_RUN_ONLY`, `safe_for_live=false`, `dry_run_only=true`.
- Kline WebSocket connected via `/market`: `wss://fstream.binance.com/market/stream?streams=ethusdc@kline_15m`.
- BookTicker WebSocket connected via `/public`: `ethusdc@bookTicker`.
- BookTicker bid/ask parsed: sample `best_bid=1725.94`, `best_ask=1725.95`.
- Maker price sample computed: `buy_maker_price=1725.94`, `sell_maker_price=1725.95`.
- Kline unclosed updates were received and ignored.
- No closed 15m candle was observed during the short clean bounded run; this is not a failure.
- No residual `ethusdc`, `pivot`, or `[p]ython.*bot` process remained.
- Forbidden log pattern scan found no `POST /fapi/v1/order`, `PUT /fapi/v1/order`, `DELETE /fapi/v1/order`, `LIVE_TRADING=true`, or `signed_order`.

An earlier 300-second external wrapper run produced kline and bookTicker evidence but exited with timeout code `124` because high-frequency bookTicker logging made shutdown noisy. The stream logging was then throttled, redeployed, and the clean bounded run above exited normally.

## Cached Filters

Cached filters are stored in `config/exchange_filters_ETHUSDC.json` and `config/exchange_filters_ETHUSDC.example.json`.

- `source=manual_example_not_for_live`
- `safe_for_live=false`
- `dry_run_only=true`
- `created_for=public_market_ws_only_dry_run`
- Note says they must be replaced by fresh `exchangeInfo` before testnet/live.

These filters are allowed only for public dry-run fallback after REST 451. They are rejected for live and rejected for default testnet signed order tests.

## Safety Results

- Live trading remains rejected by configuration and safety checks.
- Public WS-only mode requires dry-run and empty Binance credentials.
- Signed/account/order methods raise before signed requests can be built in dry-run.
- Public REST `exchangeInfo` and public REST `bookTicker` remain diagnostic only and do not sign requests.
- Entry remains maker-only; market entry remains forbidden.
- Stop fallback remains `MARKET reduceOnly` only for remaining position quantity after the maker stop window.
- No real order path was exercised.

## Phase Decisions

Phase 3A.5: GO for public WebSocket-only dry-run.

Phase 3B: CONDITIONAL GO only if the user explicitly approves installing a dry-run systemd service. It must be WS-only dry-run, no API key, no testnet order, no live.

Phase 3C testnet signed order: NO-GO while REST 451 exists or while signed REST is unvalidated.

Phase 4 live: NO-GO. Live requires resolved REST access, fresh `exchangeInfo`, signed REST validation, systemd dry-run stability, order lifecycle validation, alerts, manual exchange/account checks, and human approval.

## Next Minimal Safe Action

If approved, proceed only to Phase 3B WS-only systemd dry-run for observation windows of 1 hour, 6 hours, and 24 hours. Do not add API keys and do not start testnet signed order testing until REST 451 is resolved and signed REST validation is explicitly approved.
