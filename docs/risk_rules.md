# Risk Rules

## Fee Priority

Entry always prioritizes maker-only execution. Missing a signal is acceptable.
Taking liquidity for entry is not.

## Current Symbol And Timeframe Matrix

The current configured live profiles are:

| Symbol | Interval | Position size |
| --- | --- | --- |
| `ETHUSDC` | `15m` | `100%` account equity |
| `BTCUSDC` | `1h` | `100%` account equity |
| `XRPUSDC` | `1h` | `100%` account equity |

Closed candles for the configured interval are the only input allowed to update
pivot state. Unclosed candles and bookTicker updates may trigger already-armed
pending stop levels, but must not create pivots.

## Original Pine Strategy Risk

The strategy core matches TradingView original Pivot Reversal Strategy instead
of the previous Safer variant. It does not require the removed Safer close gates
before maintaining pending stop triggers.

TradingView may emulate reversals through `strategy.entry`. This bot does not
promise broker-emulator parity because live entry is maker-only and can miss or
delay fills. The mapping is Pine-state-equivalent for trigger creation, not a
guarantee of TradingView fill behavior.

The original Pine strategy can have long and short pending entry IDs at the same
time. The bot keeps live-risk constraints: one active entry chase per process,
one net position per symbol process, no add-on entry while the same symbol is
open, and ambiguous dual triggers are skipped instead of guessed.

## Maker Queue Risk

Reversal-like behavior requires first closing any existing position and then
opening the new direction. With maker-only execution, both legs can fail to fill
or fill late. This can leave the bot flat after exit or still in the old
position if the exit does not fill. This is an expected tradeoff of forbidding
market entry.

## Stop Priority

Stop logic tries maker-only first. After the stop chase timeout, remaining
quantity may be closed with `MARKET reduceOnly`. That market fallback is for
risk reduction only and must not be used for entry.

## No Exchange Hard Stop

The design intentionally does not place a third-layer exchange-side
`STOP_MARKET`. This reduces exchange-side order exposure but creates operational
risk if the bot, network, server, or API access fails during a position.

## Server Risk

The Singapore server passed Binance Futures public REST and WebSocket checks.
That does not remove operational risk. Systemd can restart a process, but it
does not solve account funding, API permissions, Binance outages, exchange
filters changing, order reconciliation, liquidation risk, or strategy logic
errors.

## Network And API Risk

WebSocket disconnects, timestamp drift, rate limits, and exchange errors must be
treated as normal operational events. Repeated API failures should alert and
stop live trading paths.

## Sizing

Current live wrappers set `ORDER_MODE=account_equity_pct` and
`POSITION_SIZE_PCT=100`. This is not a recommendation. It must be reviewed
against account equity, leverage, margin mode, liquidation distance, symbol
filters, and the fact that ETHUSDC, BTCUSDC, and XRPUSDC can all signal at the
same time.

## REST Gate

Live startup requires fresh REST `exchangeInfo`, signed REST validation, empty
dry-run flags, explicit human approval, and manually supplied API credentials
outside the repository. WebSocket availability alone does not prove REST order
paths are usable.

Cached filters are dry-run-only. They must not be used for live trading.

If a server returns `REST 451`, testnet signed order testing and live trading
are both NO-GO on that server. Do not use proxy, VPN, tunnel, or regional bypass
behavior.

## Stop-All Boundary

Stopping strategy services prevents the bot from submitting new strategy orders.
It does not cancel existing exchange orders and does not close exchange
positions. After any stop-all action, run signed read-only preflight for all
configured symbols and handle residual orders or positions deliberately.
