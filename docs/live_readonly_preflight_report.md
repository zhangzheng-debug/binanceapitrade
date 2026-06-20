# Live Read-Only Preflight Report

Generated UTC: `2026-06-20T15:38:36.149328+00:00`

- Scope: Binance USD-M Futures mainnet signed read-only preflight.
- Order placement/modify/cancel endpoints are forbidden in this script.
- API key and secret are not printed in this report.

- Server public IP: `167.172.69.16`
- Expected whitelist IP: `167.172.69.16`
- IP match: `True`
- Symbol: `ETHUSDC`
- Interval: `15m`
- Strategy variant: `original_pivot_reversal`
- Order mode configured: `account_equity_pct`
- Position size pct configured: `200`

## Checks

- Server time OK: `True`
- Timestamp drift ms: `6`
- ExchangeInfo OK: `True`
- Filters source: `EXCHANGE_INFO_REST`
- Tick size: `0.01`
- Step size: `0.001`
- Min qty: `0.001`
- Min notional: `20`
- Signed account query OK: `True`
- Position query OK: `True`
- ETHUSDC position amount: `0`
- OpenOrders query OK: `True`
- ETHUSDC open orders count: `0`

## Safety

- Key/secret printed: `False`
- Order endpoint called: `False`
- Live trading started: `False`

Final verdict: `SIGNED_READONLY_PREFLIGHT_GO`
