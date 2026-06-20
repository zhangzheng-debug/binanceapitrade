# Phase 3B WS-Only User Systemd Dry-Run Report

Generated: 2026-06-20

## 1. Phase 3B Goal

Phase 3B moved the ETHUSDC Pivot Bot from ad hoc bounded execution to a manually started user-level systemd dry-run observation. The purpose was to validate that the public WebSocket-only dry-run can be supervised, logged, stopped naturally, and observed without affecting existing server workloads.

This phase is not testnet signed order testing and is not live trading.

## 2. Why This Is Still Not Testnet Or Live

Binance mainnet public REST still returns HTTP 451 from the server. That keeps testnet signed order and live trading blocked. Phase 3B only validates public WebSocket market-data stability and process supervision.

No API key was written, read, or required. No signed REST endpoint was used. No real, testnet, or live order was sent.

## 3. REST 451 Status

Server connectivity diagnosis completed after deployment:

- REST 451 present: `true`
- kline WebSocket via `/market`: `ok`
- bookTicker WebSocket via `/public`: `ok`

REST 451 remains classified as `http_451_unavailable_for_legal_reasons_or_region_block` with action `report_only_no_bypass`.

## 4. Systemd Model

User-level systemd was used to avoid system-wide service installation and to keep ownership under the `dev` user.

- User unit path: `/home/dev/.config/systemd/user/ethusdc-pivot-bot-dry-run.service`
- Project path: `/home/dev/ethusdc-pivot-bot`
- System-wide unit installed: no
- Boot autostart enabled: no
- `systemctl --user is-enabled`: `disabled`
- Service after observation: `inactive`

## 5. Bundle And Deployment

- Bundle: `dist/ethusdc-pivot-bot-phase3b-dry-run.tar.gz`
- Bundle SHA256: `516e2d05af02261a82c904d760a09bf27d19e1829d1e3686d60f8e5a70da6698`
- Server backup before deploy: `/home/dev/ethusdc-pivot-bot-prev-phase3b-20260620-100628`
- Server Python: `Python 3.12.3`
- Venv install: completed with `python -m pip install -e ".[dev]"`
- `.env`: chmod `600`, dry-run only, empty `BINANCE_API_KEY=`, empty `BINANCE_API_SECRET=`

## 6. Validation Before Service Install

Local:

- `python -m pytest`: `87 passed`
- `python scripts/check_config.py`: passed
- `python scripts/scan_secrets.py`: passed, `findings_count=0`

Server:

- `python -m pytest`: `86 passed`
- `python scripts/check_config.py`: passed
- `python scripts/scan_secrets.py`: passed, `findings_count=0`
- `python scripts/diagnose_binance_connectivity.py`: REST 451 present, kline WS ok, bookTicker WS ok

## 7. Service Run

- Service start time: 2026-06-20 10:07:43 UTC
- Service stop time: 2026-06-20 11:07:53 UTC
- Runtime summary seconds: `3610.492`
- Exit mode: natural bounded runtime exit
- Manual stop used: no
- Final status: `completed`
- Systemd final state: `inactive (dead)`
- RuntimeMaxSec: `3700`

Shutdown events were logged:

- `bounded_runtime_reached`
- `bot_stopping`
- `websocket_closed`
- `final_runtime_summary`
- `public_market_dry_run_finished`

## 8. Runtime Summary

`logs/phase3b_runtime_summary.json`:

- `kline_ws_connected_count`: `1`
- `kline_ws_reconnect_count`: `0`
- `bookticker_ws_connected_count`: `1`
- `bookticker_ws_reconnect_count`: `0`
- `kline_unclosed_count`: `1100`
- `kline_closed_count`: `4`
- `bookticker_update_count`: `167493`
- `bookticker_stale_count`: `0`
- `strategy_update_count`: `4`
- `pivot_high_confirmed_count`: `0`
- `pivot_low_confirmed_count`: `0`
- `long_armed_count`: `0`
- `short_armed_count`: `0`
- `breakout_triggered_count`: `0`
- `entry_chase_started_count`: `0`
- `simulated_entry_order_count`: `0`
- `simulated_stop_order_count`: `0`
- `signed_order_blocked_count`: `0`
- `real_order_attempt_count`: `0`
- `api_error_count`: `1`
- `active_simulated_orders_cancelled_count`: `0`
- `max_memory_mb`: `46.11`

The API error count is the expected public REST `exchangeInfo` HTTP 451 fallback event.

## 9. Market Data Samples

Bid/ask sample:

- best bid: `1726.60`
- best ask: `1726.61`
- source: `websocket`

Maker-price sample:

- buy maker price: `1726.60`
- sell maker price: `1726.61`
- filter source: `CACHED_DRY_RUN_ONLY`

Closed candles were received during the 1-hour run. Four closed 15m candles are consistent with the observation length.

## 10. Safety Checks

- `LIVE_TRADING=false`: confirmed by `check_config.py`
- API key empty: `BINANCE_API_KEY=`
- API secret empty: `BINANCE_API_SECRET=`
- `POST /fapi/v1/order`: no match in logs
- `PUT /fapi/v1/order`: no match in logs
- `DELETE /fapi/v1/order`: no match in logs
- `real_order_attempt_count`: `0`
- `signed_order_blocked_count`: `0`
- MARKET entry: no evidence
- Testnet order: no evidence
- Live order: no evidence

No simulated orders were left open; no simulated shutdown cancel was needed.

## 11. Resource And Residue Checks

Systemd reported peak memory around `30.3M`; runtime summary reported process max RSS `46.11 MB`.

Server resource snapshot after the run:

- Root filesystem: `154G` size, `98G` used, `57G` available, `64%` used
- Memory: `7.8Gi` total, `781Mi` used, `7.0Gi` available

Background residue check after service exit:

- `ethusdc`: no residual process
- `pivot`: no residual process
- `[p]ython.*bot`: no residual process

Existing workload checks:

- `/home/dev/ai-rtl-studio`: still present
- `127.0.0.1:18081`: still listening
- No action was taken against `ai-rtl-studio` or the port `18081` service.

## 12. GO/NO-GO

Phase 3B 1h WS-only user systemd dry-run: GO.

Phase 3B 6h observation: GO only if the user explicitly approves another dry-run observation. It must remain user-level, WS-only, no API key, no signed order, no live, and no boot enable.

A guarded preparation script exists at `scripts/phase3b_prepare_6h_user_service.sh`. It writes a user-service drop-in for `PHASE3B_BOUNDED_RUNTIME_SECONDS=21600` and `RuntimeMaxSec=21700`, but it requires `I_APPROVE_PHASE3B_6H_PREPARE=YES` and does not start or enable the service.

Phase 3C testnet signed order: NO-GO while REST 451 exists and signed REST remains unvalidated.

Phase 4 live: NO-GO. Live still requires resolved REST access, testnet validation, order lifecycle validation, stop fallback validation, alerting, 24h dry-run stability, account-mode review, and explicit human approval.

## 13. Next Minimal Safe Action

The next safe action is a user-approved Phase 3B 6-hour WS-only dry-run observation using the same user-level service. Do not add API keys, do not enable autostart, do not start testnet signed order testing, and do not start live trading.
