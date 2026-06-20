# Risk Rules

## Fee Priority

Entry always prioritizes maker-only execution. Missing a signal is acceptable. Taking liquidity for entry is not.

## Timeframe Lock

The initial release only supports TradingView `ETHUSDC.P` mapped to Binance API symbol `ETHUSDC` on `15m`. The Binance kline stream is `ethusdc@kline_15m`. Closed 15m candles are the only input allowed to update pivot state; unclosed candles and intrabar high/low updates must not create pivots.

## Original Pine Strategy Risk

The strategy core now matches the TradingView original Pivot Reversal Strategy instead of the previous Safer variant. It no longer requires `close <= hprice` before maintaining a long pending stop trigger, and it no longer requires `close >= lprice` before maintaining a short pending stop trigger. This can create more trigger opportunities than the Safer variant.

The original Pine strategy can have long and short pending entry IDs at the same time. The bot still keeps live-risk constraints: one entry chase at a time, one net ETHUSDC position, no add-on entry, no averaging, and no reversal. If both directions trigger in the same live update, the bot skips the ambiguous dual trigger instead of guessing sequence.

TradingView may emulate reversals through `strategy.entry`; this bot intentionally does not reverse in the initial live design. The mapping is therefore Pine-state-equivalent for trigger creation, but not a promise to duplicate TradingView broker-emulator fills.

## Stop Priority

Stop logic tries maker-only first, but risk control has priority after 30 seconds. Remaining quantity is closed with `MARKET reduceOnly`.

## No Exchange Hard Stop

The initial design intentionally does not place a third-layer `STOP_MARKET`. This reduces exchange-side order exposure but creates operational risk if the bot, network, server, or API access fails during a position.

## Server Risk

The audited server is not clean. It already runs an AI RTL workload. Any future deployment must isolate the bot under `/home/dev/ethusdc-pivot-bot` and avoid existing tmux sessions, ports, and project directories.

## Network And API Risk

WebSocket disconnects, timestamp drift, rate limits, and unknown exchange errors must be treated as normal operational events. Repeated API failures should alert and stop live trading paths.

## Sizing

The default `FIXED_NOTIONAL=100` is for dry-run only. Live sizing must be manually reviewed against account equity, leverage, margin mode, liquidation distance, and exchange filters.

## REST 451 Gate

Current Phase 3A server evidence showed Binance public REST returning HTTP 451 while public WebSocket market data remained reachable. Until REST 451 is resolved or independently cleared, this project must not enter testnet signed order testing or live trading.

`PUBLIC_MARKET_WS_ONLY=true` is allowed only for public dry-run observation. It may use WebSocket kline and WebSocket bookTicker plus cached filters marked `dry_run_only=true` and `safe_for_live=false`. Cached filters must never be used for live trading and must not be the sole source for future testnet signed order tests without explicit human approval.

Live startup requires fresh REST `exchangeInfo`, signed REST validation, empty dry-run flags, explicit human approval, and manually supplied API credentials outside the repository. WebSocket availability alone does not prove REST order paths are usable.

No exchange-side `STOP_MARKET` is placed by design. Server outage, WebSocket staleness, network loss, REST 451, or process crashes can leave the bot unable to manage a position. Entry remains maker-only; stop fallback may use `MARKET reduceOnly` only for remaining position quantity after the maker stop window expires.

## Phase 3B Risk Boundary

Phase 3B only proves public WebSocket dry-run stability under a user-level service manager. It does not prove testnet or live readiness.

Systemd can restart or stop the process, but it does not solve REST 451, signed REST validation, account mode confirmation, leverage/margin setup, order reconciliation, or alerting. A stable dry-run must not be treated as permission to trade.

While REST 451 remains present, Phase 3C testnet signed order and Phase 4 live stay NO-GO. Cached filters remain dry-run only, and WebSocket market data cannot replace fresh REST `exchangeInfo` for signed trading.
