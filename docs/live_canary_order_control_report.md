# Live Order-Control Canary Report

Generated UTC: `2026-06-20T16:02:37.586854+00:00`

- Scope: direct ETHUSDC order-control canary only; full strategy was not started.
- Entry order type: `LIMIT + GTX` only.
- MARKET is forbidden for entry. Emergency cleanup is reduceOnly in One-way Mode; in Hedge Mode it requires explicit approval and exact `positionSide` close orders because Binance disallows reduceOnly there.

- Server public IP: `167.172.69.16`
- Expected whitelist IP: `167.172.69.16`
- IP match: `True`
- ExchangeInfo source: `EXCHANGE_INFO_REST`
- Position mode dual-side: `True`
- Hedge Mode approval env present: `False`
- Account can trade: `None`
- Initial open orders count: `0`
- Final open orders count: `0`
- Final position rows: `[]`

## Orders

- BUY result: `None`
- SELL result: `None`

## Safety Counters

- Real order attempts: `0`
- LIMIT GTX order attempts: `0`
- Modify attempts: `0`
- Cancel attempts: `0`
- Market entry attempts: `0`
- STOP_MARKET entry attempts: `0`
- reduceOnly MARKET cleanup count: `0`
- Hedge Mode non-reduceOnly MARKET cleanup count: `0`
- Unexpected fill: `False`
- Emergency cleanup triggered: `False`
- Full strategy started: `False`
- Live trading started by bot.main: `False`
- Key/secret printed: `False`

Final verdict: `LIVE_ORDER_CONTROL_CANARY_NO_GO`

## Error

`hedge mode account detected; set I_APPROVE_HEDGE_MODE_ORDER_CONTROL_CANARY=YES to explicitly approve the Hedge Mode order-control canary. Without that second gate this script only performs signed read-only checks.`
