# Fast Path Live Readiness Report

Generated: 2026-06-20 after the server F1 fast smoke and F2 connectivity diagnosis.

## Objective

Move toward live readiness quickly by removing meaningless long dry-runs and attacking the hard gates directly. The result is clear: log volume is fixed, user-level systemd smoke works, public WebSockets work, but mainnet Binance Futures REST is still blocked by HTTP 451.

## Validation

| Check | Result |
| --- | --- |
| Local pytest | Passed, 97 tests |
| Server pytest | Passed, 97 tests |
| Local `check_config.py` | Passed |
| Server `check_config.py` | Passed, `LIVE_TRADING=false`, empty API key/secret |
| Local `scan_secrets.py` | Passed, 0 findings |
| Server `scan_secrets.py` | Passed, 0 findings |
| Bundle | `dist/ethusdc-pivot-bot-fast-path-live-readiness.tar.gz` |
| Bundle SHA-256 | Recorded in `reports/deploy_bundle_fast_path.json` and `dist/ethusdc-pivot-bot-fast-path-live-readiness.tar.gz.sha256` after packaging |

After the original Pine strategy-core change:

| Check | Result |
| --- | --- |
| Local pytest | Passed, 127 tests |
| Server pytest | Passed, 127 tests |
| Local `scan_secrets.py` | Passed, 0 findings |
| Server `scan_secrets.py` | Passed, 0 findings |
| Bundle | `dist/ethusdc-pivot-bot-original-pivot-fast-smoke.tar.gz` |
| Bundle SHA-256 | Recorded in `reports/deploy_bundle_original_pivot.json` after packaging |

## F1 Result

User-level systemd fast smoke completed naturally.

| Field | Value |
| --- | --- |
| Service | `ethusdc-pivot-bot-fast-smoke.service` |
| Scope | user-level only |
| Boot enable | Not enabled, unit is `static` |
| Runtime | `1810.69` seconds |
| Final status | `completed` |
| kline WS connected | `1` |
| kline WS reconnects | `0` |
| bookTicker WS connected | `1` |
| bookTicker WS reconnects | `0` |
| Closed 15m candles | `2` |
| Unclosed kline updates | `719` |
| bookTicker updates | `103263` |
| bookTicker detail logs | `52` |
| bookTicker summaries | `30` |
| Latest bid/ask | `1726.49 / 1726.50` |
| Latest maker BUY/SELL | `1726.49 / 1726.50` |
| events log size | `0.03 MB` |
| bot log size | `0.006 MB` |
| Max memory | `46.24 MB` |
| API error count | `1`, expected mainnet REST `exchangeInfo` 451 |
| Signed order blocked count | `0` |
| Real order attempt count | `0` |
| Residual bot process | None after exit |

Pre-run logs were not copied from the previous deployment; the new deploy created an empty `logs/` directory before service start. The final event log stayed near 0.03 MB while processing 103,263 bookTicker updates.

## F2 Result

F2 diagnosis output:

- `reports/fast_path_connectivity_diagnosis.json`
- `docs/fast_path_connectivity_diagnosis.md`

| Endpoint group | Result |
| --- | --- |
| Mainnet public REST | Failed |
| Testnet public REST | OK |
| Mainnet REST 451 present | `True` |
| Testnet REST 451 present | `False` |
| kline WebSocket | OK |
| bookTicker WebSocket | OK |
| Gate status | `blocked_rest_451_stop` |

Mainnet public REST classifications:

| Endpoint | Status | Classification |
| --- | --- | --- |
| `mainnet_ping` | `451` | `rest_451_blocked_no_bypass` |
| `mainnet_time` | `451` | `rest_451_blocked_no_bypass` |
| `mainnet_exchangeInfo` | `451` | `rest_451_blocked_no_bypass` |
| `mainnet_bookTicker` | `451` | `rest_451_blocked_no_bypass` |

Testnet public REST classifications:

| Endpoint | Status | Classification |
| --- | --- | --- |
| `testnet_ping` | `200` | `ok` |
| `testnet_time` | `200` | `ok` |
| `testnet_exchangeInfo` | `200` | `ok` |
| `testnet_bookTicker` | `200` | `ok` |

Because mainnet REST 451 is still present, this run stopped at F2. No signed REST, testnet order lifecycle, live preflight, or live canary was executed.

## Fixed

- Strategy core is now TradingView original Pivot Reversal Strategy instead of the older Safer variant.
- The Safer `close <= hprice` / `close >= lprice` entry gates are removed from implementation.
- Pine stop entries now map to local pending triggers plus maker-only chaser, not Binance STOP/STOP_MARKET entry.
- bookTicker detail logging is sampled with `BOOKTICKER_LOG_EVERY_N=2000`.
- bookTicker summaries are emitted every 60 seconds.
- Raw market message logging defaults to `LOG_RAW_MARKET_MESSAGES=false`.
- Unclosed kline detail logging is sampled with `KLINE_LOG_UNCLOSED_EVERY_N=200`.
- Closed candles and strategy updates remain detailed.
- `logs/fast_smoke_runtime_summary.json` is written at shutdown.
- Fast-smoke user service is user-level only, bounded, and not boot-enabled.
- Log size fields and warning thresholds are included in runtime summary.

## Hard Blockers

- Mainnet REST 451 blocks live readiness.
- Mainnet `exchangeInfo` cannot be fetched from this server.
- Signed REST order/query/modify/cancel/position lifecycle is not validated.
- Cached filters remain dry-run only and cannot be used for live.
- API key injection flow is not approved or audited for signed tests/live.
- Testnet lifecycle and live canary were not executed because F2 stopped the path.

## Original Pivot Fast Smoke

The original-Pine deploy completed a second user-level fast smoke:

| Field | Value |
| --- | --- |
| Runtime | `1810.949` seconds |
| Final status | `completed` |
| kline closed | `2` |
| kline unclosed | `800` |
| bookTicker updates | `123286` |
| bookTicker detail logs | `62` |
| bookTicker summaries | `30` |
| pending long stop created | `0` |
| pending short stop created | `0` |
| pine stop triggers | `0` |
| breakout triggers | `0` |
| entry chases | `0` |
| simulated entry orders | `0` |
| real order attempts | `0` |
| signed order blocked count | `0` |
| events log size | `0.033 MB` |
| bot log size | `0.007 MB` |
| Max memory | `46.22 MB` |

No breakout was required or observed during this 30-minute smoke. The result verifies that the original-Pine state machine runs under WS-only systemd without changing live gates.

## Forced Trigger Replay

The real-market fast smoke did not produce pending-trigger events, which is not a failure. The forced replay validates the signal-present path without waiting for market conditions:

| Field | Value |
| --- | --- |
| Long replay | pending trigger created, `pine_stop_trigger_detected`, `breakout_triggered_original_pine`, BUY maker chaser, dry-run `LIMIT + GTX` |
| Short replay | pending trigger created, `pine_stop_trigger_detected`, `breakout_triggered_original_pine`, SELL maker chaser, dry-run `LIMIT + GTX` |
| Ambiguous dual trigger | `ambiguous_dual_trigger_skipped`, no order |
| Active chase blocking | `trigger_blocked_active_chase` |
| Position blocking | `ignored_due_to_position` |
| Missed trigger | `missed_long_trigger_on_closed_candle` and `missed_short_trigger_on_closed_candle` |
| MARKET entry attempts | `0` |
| STOP_MARKET entry attempts | `0` |
| Signed REST calls | `0` |
| Real order attempts | `0` |

Output files:

- `reports/forced_original_pivot_trigger_replay.json`
- `docs/forced_original_pivot_trigger_replay_report.md`

## GO/NO-GO

| Target | Decision |
| --- | --- |
| Full live bot | NO-GO |
| Testnet order lifecycle | NO-GO while REST 451 remains present in this gate |
| Live canary | NO-GO |
| WS-only dry-run smoke | GO, bounded user-level systemd only |

## Next Safe Action

Do not spend more time on 6h/24h dry-runs on this server. The fastest safe live path is to move to a lawful server environment where Binance Futures mainnet REST is reachable, then rerun F2 before requesting any signed/testnet/live approval.

## Official API Constraints

- Live/testnet filters must come from Binance USD-M Futures `GET /fapi/v1/exchangeInfo`; `pricePrecision` is not `tickSize`, and `quantityPrecision` is not `stepSize`.
- Maker entry must use `/fapi/v1/order` with `LIMIT` and `GTX`; stop-loss fallback may use `MARKET reduceOnly` only after the maker stop chase fails.
- Public WebSocket kline and bookTicker streams are suitable for market observation, but they do not prove REST order-path readiness.

References:

- https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information
- https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order
- https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Kline-Candlestick-Streams
- https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Individual-Symbol-Book-Ticker-Streams
