# Phase 3A.5 Binance Connectivity Diagnosis

Generated UTC: `2026-06-20T09:37:28.216009+00:00`

This diagnosis uses public endpoints only. It does not read API keys, sign requests, place orders, or bypass HTTP 451.

- REST 451 present: `True`
- Mainnet kline WebSocket ok: `False`
- Mainnet bookTicker WebSocket ok: `True`

| Name | Env | Transport | OK | Status | Classification | Action | Error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mainnet_ping | mainnet | rest | False | 451 | http_451_unavailable_for_legal_reasons_or_region_block | report_only_no_bypass | http_451 |
| mainnet_time | mainnet | rest | False | 451 | http_451_unavailable_for_legal_reasons_or_region_block | report_only_no_bypass | http_451 |
| mainnet_exchangeInfo | mainnet | rest | False | 451 | http_451_unavailable_for_legal_reasons_or_region_block | report_only_no_bypass | http_451 |
| mainnet_bookTicker | mainnet | rest | False | 451 | http_451_unavailable_for_legal_reasons_or_region_block | report_only_no_bypass | http_451 |
| testnet_ping | testnet | rest | True | 200 | ok | none |  |
| testnet_time | testnet | rest | True | 200 | ok | none |  |
| testnet_exchangeInfo | testnet | rest | True | 200 | ok | none |  |
| testnet_bookTicker | testnet | rest | True | 200 | ok | none |  |
| mainnet_kline_ws | mainnet | websocket | False | None | websocket_error | report_only | TimeoutError |
| mainnet_bookticker_ws | mainnet | websocket | True | None | ok | none |  |
| testnet_websocket | testnet | websocket | False | None | skipped_not_implemented | none | skipped_not_implemented |

REST 451 classification: `http_451_unavailable_for_legal_reasons_or_region_block` with action `report_only_no_bypass`.
