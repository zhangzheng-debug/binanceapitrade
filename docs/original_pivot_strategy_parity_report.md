# Original Pivot Strategy Parity Report

## Why This Changed

The bot previously used a Safer interpretation that required `close <= hprice` for long arming and `close >= lprice` for short arming. The strategy core has now been changed back to TradingView's original Pivot Reversal Strategy semantics. The change is intentional because dry-run, testnet, and live gates should validate the strategy the bot is actually meant to run.

## Original Pine

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

## Python State Mapping

- `hprice` persists after the latest confirmed pivot high.
- `le=true` when a new pivot high is confirmed.
- Without a new pivot high, `le=false` only when `high > hprice`.
- `active_long_stop_price = hprice + tick` while `le=true`.
- `lprice` persists after the latest confirmed pivot low.
- `se=true` when a new pivot low is confirmed.
- Without a new pivot low, `se=false` only when `low < lprice`.
- `active_short_stop_price = lprice - tick` while `se=true`.

## Removed Safer Gates

The implementation no longer requires `close <= hprice` to maintain a long pending trigger. It no longer requires `close >= lprice` to maintain a short pending trigger.

## Pending Stop Trigger Mapping

Pine stop entries are local pending triggers:

- `PivRevLE`: long trigger at `hprice + tick`.
- `PivRevSE`: short trigger at `lprice - tick`.

These are not exchange orders. The bot does not place Binance `STOP` or `STOP_MARKET` entries.

## Realtime Trigger Flow

Pivot state updates only from closed 15m candles. Existing pending triggers may fire from:

- unclosed kline high/low/close,
- closed kline high/low/close before pivot update,
- bookTicker best ask/bid.

If both long and short triggers fire in the same live update, the bot records `ambiguous_dual_trigger_skipped` and does not start an entry chase.

## Maker Discipline

After a trigger, entry still goes through the maker-only chaser. It uses `LIMIT + GTX` and may give up after 60 seconds. It never downgrades an entry to `MARKET`, `STOP`, or `STOP_MARKET`.

## Differences From TradingView

- TradingView's broker emulator can reverse positions through `strategy.entry`; this bot does not reverse.
- TradingView simulated fills are not live exchange fills.
- The bot uses maker-only entry, so it can miss triggers that TradingView would fill.
- The bot allows only one active entry chase and one ETHUSDC net position.

## Test Result

Local pytest passed with 127 tests. Server pytest passed with 127 tests. The added original-Pine tests cover:

- strategy variant rejection for `safer_pivot_reversal`;
- `hprice/le/lprice/se` persistence and invalidation;
- removal of the Safer close gates;
- pending long/short trigger prices;
- unclosed kline and bookTicker trigger detection;
- ambiguous dual-trigger skip;
- active-chase and open-position blocking;
- missed closed-candle trigger logging;
- entry chaser remaining `LIMIT + GTX`;
- no `MARKET` or `STOP_MARKET` entry mapping;
- stop-loss fallback remaining `MARKET reduceOnly` only.

The server fast smoke completed in `1810.949` seconds with two closed 15m candles, 123286 bookTicker updates, zero pending trigger creations, zero trigger detections, zero entry chases, zero signed order calls, and zero real order attempts.

Because the real-market smoke had no breakout, `scripts/replay_forced_original_pivot_trigger.py` now validates the signal-present path synthetically. It confirms long and short pending triggers, unclosed-kline trigger detection, maker-only chaser startup, `LIMIT + GTX` dry-run orders, ambiguous trigger skip, active-chase blocking, position blocking, missed-trigger logging, no MARKET entry, no STOP_MARKET entry, no signed REST, and no real orders.

## Live Gate Impact

The strategy parity change does not make live trading GO. Mainnet REST 451 remains a hard live blocker. WS-only dry-run may be GO after tests and fast smoke; live canary and full live bot remain NO-GO while mainnet REST 451 persists.
