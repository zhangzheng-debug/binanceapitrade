# Trading Rules

## Original Pine Pivot Reversal Semantics

The strategy core is the TradingView original Pine `Pivot Reversal Strategy`, not the previous Safer variant:

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

- `leftBars = 4`
- `rightBars = 2`
- `interval = 15m`; the initial release rejects all other intervals.
- TradingView symbol: `ETHUSDC.P`.
- Binance API symbol: `ETHUSDC`.
- Binance kline stream: `ethusdc@kline_15m`.
- Binance bookTicker stream for Phase 3A.5 public dry-run: `ethusdc@bookTicker`.
- Use closed 15m candles only.
- Pivot high is confirmed only after two right-side candles close.
- Pivot low is confirmed only after two right-side candles close.
- With `rightBars=2` on 15m candles, pivot confirmation is delayed by at least about 30 minutes.
- This delay is required to match TradingView Pine Script pivot semantics and is not a bug.
- The bot must not confirm pivots early.
- The bot must not use unclosed candles to create new pivots.
- The bot must not update pivot state from real-time intrabar high or low.
- On pivot high confirmation: set `hprice` and `le=true`.
- If no new pivot high and current `high > hprice`, set `le=false`.
- On pivot low confirmation: set `lprice` and `se=true`.
- If no new pivot low and current `low < lprice`, set `se=false`.
- Python mapping:
  - `hprice := swh_cond ? swh : hprice[1]`
  - `le := swh_cond ? true : (le[1] and high > hprice ? false : le[1])`
  - `lprice := swl_cond ? swl : lprice[1]`
  - `se := swl_cond ? true : (se[1] and low < lprice ? false : se[1])`
- The previous Safer `close <= hprice` / `close >= lprice` filter is not used as an entry gate.
- If `le=true`, create or maintain a local pending long stop trigger at `hprice + tick`.
- If `se=true`, create or maintain a local pending short stop trigger at `lprice - tick`.
- A pending trigger is local bot state, not a real exchange stop order.
- `k.x=false` unclosed kline updates never update pivots, but may trigger an existing pending stop level.
- `k.x=true` closed kline updates are first offered to the trigger monitor, then update pivot state.
- Trigger detection starts the maker-only entry chaser; it does not place MARKET, STOP, or STOP_MARKET entry orders.

## Entry

- LONG entry side: `BUY`
- SHORT entry side: `SELL`
- Order type: `LIMIT`
- Time in force: `GTX`
- Max chase: 60 seconds
- Market entry is forbidden.
- Non-GTX entry is forbidden.
- Crossing-limit entry is forbidden.
- Post-only rejection means maker protection worked; retry by refreshing the book, not by taking liquidity.
- In `PUBLIC_MARKET_WS_ONLY=true`, entry chase requires a fresh WebSocket bookTicker snapshot. If no snapshot exists or it is stale, do not start a new chase.

## Maker Prices

- BUY maker price: `min(best_bid + tick, best_ask - tick)`
- SELL maker price: `max(best_ask - tick, best_bid + tick)`
- One-tick spread:
  - BUY posts at `best_bid`
  - SELL posts at `best_ask`
- Never allow `BUY price >= best_ask`.
- Never allow `SELL price <= best_bid`.
- If bookTicker is stale beyond `BOOK_TICKER_STALE_SECONDS`, do not compute a new maker price.

## Stop

- No third-layer exchange hard stop.
- No pre-placed `STOP_MARKET` after entry.
- Stop logic is bot-executed.
- Long stop closes with `SELL LIMIT GTX reduceOnly`, then `MARKET reduceOnly` for remainder after 30 seconds.
- Short stop closes with `BUY LIMIT GTX reduceOnly`, then `MARKET reduceOnly` for remainder after 30 seconds.
- Market stop quantity must not exceed the current position and must never reverse the account.
- In dry-run, stop fallback may log simulated `MARKET reduceOnly`; live validation is still forbidden while REST 451 remains unresolved.

## Position Rules

- One-way mode assumption.
- Only ETHUSDC.
- One net position at a time.
- No add-on entries.
- No averaging down.
- No reversal logic in the initial release.
- No simultaneous long and short entry chases.
- No new entry while stop chase is active.
