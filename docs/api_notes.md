# Binance API Notes

Docs last checked on `2026-06-20`.

## Official Links

- New Order: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api
- Modify Order: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Modify-Order
- Exchange Information: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information
- Symbol Order Book Ticker: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Symbol-Order-Book-Ticker
- Kline Streams: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Kline-Candlestick-Streams
- WebSocket Market Streams: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams

## Current Symbols And Streams

| Symbol | Interval | Kline stream | bookTicker stream |
| --- | --- | --- | --- |
| `ETHUSDC` | `15m` | `ethusdc@kline_15m` | `ethusdc@bookTicker` |
| `BTCUSDC` | `1h` | `btcusdc@kline_1h` | `btcusdc@bookTicker` |
| `XRPUSDC` | `1h` | `xrpusdc@kline_1h` | `xrpusdc@bookTicker` |

All stream symbols are lowercase in WebSocket URLs.

## New Order

USD-M Futures new order is `POST /fapi/v1/order`. `LIMIT` orders require
`timeInForce`, `quantity`, and `price`. `MARKET` orders require `quantity`.
`reduceOnly` is an order parameter but cannot be sent in Hedge Mode; this
project assumes One-way Mode.

Entry order constraints:

```text
type=LIMIT
timeInForce=GTX
reduceOnly=false
```

`MARKET`, `STOP`, and `STOP_MARKET` are forbidden for entry.

## Modify Order

USD-M modify order is `PUT /fapi/v1/order`. It supports LIMIT order
modification. `quantity` and `price` must both be sent. GTX order amendment can
cancel the order if the new price would execute immediately. That is treated as
maker-only protection, not a reason to downgrade to market entry.

## Exchange Info

Use `GET /fapi/v1/exchangeInfo` for live filters. Do not use `pricePrecision`
as `tickSize`, and do not use `quantityPrecision` as `stepSize`. Parse
`PRICE_FILTER`, `LOT_SIZE`, `MARKET_LOT_SIZE`, and `MIN_NOTIONAL` or
`NOTIONAL`.

Cached filters are dry-run-only and must not be used for live trading.

## Book Ticker

Use `GET /fapi/v1/ticker/bookTicker` for REST best bid/ask checks. The live
strategy uses WebSocket bookTicker snapshots for maker chaser pricing.

## Kline Streams

Only events where `k.x == true` update pivot state. Unclosed `k.x == false`
updates must not update pivots, but they may feed the local pending stop-trigger
monitor.

## WebSocket Routing

Binance USD-M market streams use the routed `/market` endpoint for kline in
this project. Book ticker public WebSocket uses the routed `/public` endpoint.
Connections can disconnect at 24 hours and require ping/pong handling.

## REST 451 Boundary

HTTP 451 from Binance REST is classified as
`http_451_unavailable_for_legal_reasons_or_region_block` with action
`report_only_no_bypass`. The bot must not attempt proxy, VPN, tunnel, or
regional bypass behavior.

Before testnet signed order or live trading, REST `exchangeInfo` and signed REST
connectivity must be validated without cached filters.

## TradingView Stop Entry Mapping

TradingView `strategy.entry(..., stop=...)` is treated as a pending activation
level. In this bot, `stop=hprice + syminfo.mintick` and
`stop=lprice - syminfo.mintick` create local pending triggers only. When a
trigger fires from unclosed kline, closed kline, or bookTicker evidence, the
entry path still uses `LIMIT + GTX` maker chasing.

The bot does not map Pine stop entries to Binance `STOP`, `STOP_MARKET`,
`MARKET`, or crossing ordinary `LIMIT` entry orders. Stop-loss fallback remains
separate: after a maker reduce-only stop chase times out, only the remaining
position may be closed with `MARKET reduceOnly`.
