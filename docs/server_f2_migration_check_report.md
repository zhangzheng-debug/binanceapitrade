# F2 Migration Check Report

Generated UTC: `2026-06-20T13:45:53.522039+00:00`

Public endpoints only. No API keys, signed REST, orders, proxy, VPN, or tunnel behavior.

- Decision codes: `F2_MAINNET_REST_NO_GO, PUBLIC_WS_DRY_RUN_ONLY`

| Name | Env | Transport | OK | Status | Classification |
| --- | --- | --- | --- | --- | --- |
| mainnet_ping | mainnet | rest | False | 451 | rest_451_blocked_no_bypass |
| mainnet_time | mainnet | rest | False | 451 | rest_451_blocked_no_bypass |
| mainnet_exchangeInfo | mainnet | rest | False | 451 | rest_451_blocked_no_bypass |
| mainnet_bookTicker | mainnet | rest | False | 451 | rest_451_blocked_no_bypass |
| testnet_ping | testnet | rest | False | 451 | rest_451_blocked_no_bypass |
| testnet_time | testnet | rest | False | 451 | rest_451_blocked_no_bypass |
| testnet_exchangeInfo | testnet | rest | False | 451 | rest_451_blocked_no_bypass |
| testnet_bookTicker | testnet | rest | False | 451 | rest_451_blocked_no_bypass |
| mainnet_kline_ws | mainnet | websocket | True | None | ok |
| mainnet_bookticker_ws | mainnet | websocket | True | None | ok |

If mainnet REST returns 451, this server cannot be used for Binance Futures live. Do not bypass with proxy, VPN, or tunnel. Use a lawful server environment where Binance Futures REST is reachable.
