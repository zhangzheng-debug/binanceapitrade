# Binance API Notes

Docs checked on 2026-06-20.

## Official Links

- New Order: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api
- Modify Order: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Modify-Order
- Exchange Information: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information
- Symbol Order Book Ticker: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Symbol-Order-Book-Ticker
- Kline Streams: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Kline-Candlestick-Streams
- WebSocket Market Streams: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams

## New Order

USD-M Futures new order is `POST /fapi/v1/order`. `LIMIT` orders require `timeInForce`, `quantity`, and `price`. `MARKET` orders require `quantity`. `reduceOnly` is an order parameter but cannot be sent in Hedge Mode; this project assumes one-way mode.

## Modify Order

USD-M modify order is `PUT /fapi/v1/order`. It currently supports LIMIT order modification. `quantity` and `price` must both be sent. GTX order amendment can cancel the order if the new price would execute immediately. That is treated as maker-only protection, not a reason to downgrade to market entry.

## Exchange Info

Use `GET /fapi/v1/exchangeInfo` for live filters. Do not use `pricePrecision` as `tickSize`, and do not use `quantityPrecision` as `stepSize`. Parse `PRICE_FILTER`, `LOT_SIZE`, `MARKET_LOT_SIZE`, and `MIN_NOTIONAL` or `NOTIONAL`.

## Book Ticker

Use `GET /fapi/v1/ticker/bookTicker` for best bid and ask.

## Kline Streams

Binance USD-M kline streams support `15m`. This project locks the initial release to TradingView `ETHUSDC.P`, Binance API symbol `ETHUSDC`, and stream name `ethusdc@kline_15m`. Only events where `k.x == true` update pivot state. Unclosed `k.x == false` updates must not update pivots, but they may feed the local pending stop-trigger monitor.

## WebSocket Routing

Binance USD-M market streams use the routed `/market` endpoint. The public market dry-run uses `wss://fstream.binance.com/market/stream?streams=ethusdc@kline_15m` on mainnet, or the equivalent testnet market base URL. Connections can disconnect at 24 hours and require ping/pong handling. All stream symbols are lowercase.

Book ticker public WebSocket uses the routed `/public` endpoint with stream `ethusdc@bookTicker`. Phase 3A.5 uses this path for WebSocket-only public dry-run when REST bookTicker is unavailable.

## Exchange Filters

Use `exchangeInfo` to parse `tickSize`, `stepSize`, `minQty`, and `minNotional`. Do not use `pricePrecision` as `tickSize`, and do not use `quantityPrecision` as `stepSize`.

## Phase 3A.5 REST 451 Boundary

HTTP 451 from Binance REST is classified as `http_451_unavailable_for_legal_reasons_or_region_block` with action `report_only_no_bypass`. The bot must not attempt proxy, VPN, tunnel, or regional bypass behavior.

While REST 451 exists, only public WebSocket dry-run is allowed. Cached exchange filters may be loaded only when they are marked `dry_run_only=true` and `safe_for_live=false`. Before testnet signed order or live trading, REST `exchangeInfo` and signed REST connectivity must be validated without cached filters.

GTX maker-only order or amend behavior that would immediately execute must be rejected or canceled. The bot must not downgrade maker entry to `MARKET` or ordinary crossing `LIMIT`.

## TradingView Stop Entry Mapping

TradingView `strategy.entry(..., stop=...)` is treated as a pending activation level. In this bot, `stop=hprice + syminfo.mintick` and `stop=lprice - syminfo.mintick` create local pending triggers only. When a trigger fires from unclosed kline, closed kline, or bookTicker evidence, the entry path still uses `LIMIT + GTX` maker chasing.

The bot does not map Pine stop entries to Binance `STOP`, `STOP_MARKET`, `MARKET`, or crossing ordinary `LIMIT` entry orders. Stop-loss fallback remains separate: after a 30-second maker reduce-only stop chase, only the remaining position may be closed with `MARKET reduceOnly`.
