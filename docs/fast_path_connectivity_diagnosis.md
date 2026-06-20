# Fast Path Connectivity Diagnosis

Generated UTC: `2026-06-20T12:09:14.989787+00:00`

This diagnosis uses public endpoints only. It does not read API keys, sign requests, place orders, or bypass HTTP 451.

- REST 451 present: `True`
- Mainnet public REST ok: `False`
- Testnet public REST ok: `True`
- Gate F2 status: `blocked_rest_451_stop`
- Mainnet kline WebSocket ok: `True`
- Mainnet bookTicker WebSocket ok: `True`
- Fastest safe path: change to a lawful server/location with Binance Futures REST access, then rerun F2

| Name | Env | Transport | OK | Status | Classification | Action | Error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mainnet_ping | mainnet | rest | False | 451 | rest_451_blocked_no_bypass | stop_no_testnet_no_live | http_451 |
| mainnet_time | mainnet | rest | False | 451 | rest_451_blocked_no_bypass | stop_no_testnet_no_live | http_451 |
| mainnet_exchangeInfo | mainnet | rest | False | 451 | rest_451_blocked_no_bypass | stop_no_testnet_no_live | http_451 |
| mainnet_bookTicker | mainnet | rest | False | 451 | rest_451_blocked_no_bypass | stop_no_testnet_no_live | http_451 |
| testnet_ping | testnet | rest | True | 200 | ok | none |  |
| testnet_time | testnet | rest | True | 200 | ok | none |  |
| testnet_exchangeInfo | testnet | rest | True | 200 | ok | none |  |
| testnet_bookTicker | testnet | rest | True | 200 | ok | none |  |
| mainnet_kline_ws | mainnet | websocket | True | None | ok | none |  |
| mainnet_bookticker_ws | mainnet | websocket | True | None | ok | none |  |
| testnet_websocket | testnet | websocket | False | None | skipped_not_implemented | none | skipped_not_implemented |

REST 451 classification: `rest_451_blocked_no_bypass`. No proxy, VPN, tunnel, or other bypass is allowed.

Official API references checked for this gate:

- Binance USD-M Futures Exchange Information: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information
- Binance USD-M Futures New Order: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order
- Binance USD-M Futures Kline WebSocket stream: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Kline-Candlestick-Streams
- Binance USD-M Futures bookTicker WebSocket stream: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Individual-Symbol-Book-Ticker-Streams
