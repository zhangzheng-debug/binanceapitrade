# Trading Rules

## Original Pine Pivot Reversal Semantics

The strategy core is the TradingView original Pine `Pivot Reversal Strategy`,
not the previous Safer variant:

```pine
//@version=6
strategy("Pivot Reversal Strategy", overlay=true)
leftBars = input(4, "Pivot Lookback Left")
rightBars = input(2, "Pivot Lookback Right")
swh = ta.pivothigh(leftBars, rightBars)
swl = ta.pivotlow(leftBars, rightBars)
swh_cond = not na(swh)
hprice = 0.0
hprice := swh_cond ? swh : hprice[1]
le = false
le := swh_cond ? true : (le[1] and high > hprice ? false : le[1])
if (le)
    strategy.entry("PivRevLE", strategy.long, comment="PivRevLE", stop=hprice + syminfo.mintick)
swl_cond = not na(swl)
lprice = 0.0
lprice := swl_cond ? swl : lprice[1]
se = false
se := swl_cond ? true : (se[1] and low < lprice ? false : se[1])
if (se)
    strategy.entry("PivRevSE", strategy.short, comment="PivRevSE", stop=lprice - syminfo.mintick)
```

Parameters:

- `leftBars = 4`
- `rightBars = 2`
- `rightBars=2` means two right-side candles are required before a pivot is
  confirmed.
- On `15m`, that is at least about `30 minutes` of confirmation delay.
- The bot must not confirm pivots early.
- The bot must not confirm pivots early; in test wording, it `must not confirm
  pivots early`.
- previous Safer `close <= hprice` / `close >= lprice` gates are not used as an entry gate.

Current runtime matrix:

| Symbol | Interval | Kline stream | bookTicker stream |
| --- | --- | --- | --- |
| `ETHUSDC` | `15m` | `ethusdc@kline_15m` | `ethusdc@bookTicker` |
| `BTCUSDC` | `1h` | `btcusdc@kline_1h` | `btcusdc@bookTicker` |
| `XRPUSDC` | `1h` | `xrpusdc@kline_1h` | `xrpusdc@bookTicker` |

## Candle Rules

- Use closed candles for the configured interval only.
- Pivot high is confirmed only after two right-side candles close.
- Pivot low is confirmed only after two right-side candles close.
- The delay is required to match TradingView Pine Script pivot semantics.
- The bot must not confirm pivots early.
- The bot must not use unclosed candles to create new pivots.
- The bot must not update pivot state from real-time intrabar high or low.
- On pivot high confirmation: set `hprice` and `le=true`.
- If no new pivot high and current `high > hprice`, set `le=false`.
- On pivot low confirmation: set `lprice` and `se=true`.
- If no new pivot low and current `low < lprice`, set `se=false`.
- If `le=true`, create or maintain a local pending long stop trigger at
  `hprice + tick`.
- If `se=true`, create or maintain a local pending short stop trigger at
  `lprice - tick`.
- A pending trigger is local bot state, not a real exchange stop order.
- `k.x=false` unclosed kline updates never update pivots, but may trigger an
  existing pending stop level.
- `k.x=true` closed kline updates are first offered to the trigger monitor, then
  update pivot state.

## Entry

- LONG entry side: `BUY`
- SHORT entry side: `SELL`
- Order type: `LIMIT`
- Time in force: `GTX`
- Max chase: 60 seconds
- Market entry is forbidden.
- STOP or STOP_MARKET entry is forbidden.
- Non-GTX entry is forbidden.
- Crossing-limit entry is forbidden.
- Post-only rejection means maker protection worked; retry by refreshing the
  book, not by taking liquidity.
- Trigger detection starts the maker-only entry chaser; it does not place
  `MARKET`, `STOP`, or `STOP_MARKET` entry orders.

## Maker Prices

- BUY maker price: `min(best_bid + tick, best_ask - tick)`.
- SELL maker price: `max(best_ask - tick, best_bid + tick)`.
- One-tick spread:
  - BUY posts at `best_bid`.
  - SELL posts at `best_ask`.
- Never allow `BUY price >= best_ask`.
- Never allow `SELL price <= best_bid`.
- If bookTicker is stale beyond `BOOK_TICKER_STALE_SECONDS`, do not compute a
  new maker price.

## Stop

- No third-layer exchange hard stop.
- No pre-placed `STOP_MARKET` after entry.
- Stop logic is bot-executed.
- Long stop closes with `SELL LIMIT GTX reduceOnly`, then `MARKET reduceOnly`
  for remainder after timeout.
- Short stop closes with `BUY LIMIT GTX reduceOnly`, then `MARKET reduceOnly`
  for remainder after timeout.
- Market stop quantity must not exceed the current position and must never
  reverse the account.

## Position Rules

- One-way mode assumption.
- Current wrappers size entries as `100%` account equity per symbol.
- One net position per symbol process.
- No add-on entry while that symbol has an open position.
- No averaging down within a symbol process.
- No simultaneous long and short entry chases within a symbol process.
- No new entry while stop chase is active.
- ETHUSDC, BTCUSDC, and XRPUSDC are separate processes and can therefore
  produce independent signals.
