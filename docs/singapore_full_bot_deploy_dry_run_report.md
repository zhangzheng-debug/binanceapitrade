# Singapore Full Bot Deploy Dry-Run Report

Generated UTC: `2026-06-20T15:14:41.681192+00:00`

## Scope

- Server: `167.172.69.16`
- Login/user used: `root`
- Deployment path: `/root/ethusdc-pivot-bot`
- Reason path is under `/root`: no `dev` user existed on the fresh server.
- Full strategy live: `no`
- Systemd/autostart: `no`
- API key written: `no`
- Signed REST called: `no`
- Testnet order called: `no`
- Live order called: `no`
- Exposed chat/screenshot key used: `no`
- Position sizing / 200 percent request: not configured in this no-key dry-run gate; current dry-run uses fixed notional only.

## Deployment

- Bundle SHA256: `26ca0e8f9be1df6bc939d1040772f15cf1a5b7cdacfa1e21634d570c8c726908`
- Server Python: `Python 3.12.3`
- Venv: `/root/ethusdc-pivot-bot/.venv`
- Install command: `python -m pip install -e .[dev]`
- Dry-run `.env` permission: `600`

## Local Gates Before Bundle

- `pytest`: passed, 139 tests
- `scripts/scan_secrets.py`: passed, findings_count=0
- `scripts/check_config.py`: passed
- `scripts/replay_forced_original_pivot_trigger.py`: passed

## Server Gates

- `pytest`: passed, 139 tests
- `scan_secrets`: passed=`True`, findings_count=`0`
- `check_config`: dry_run=`True`, live_trading=`False`, api_key_empty=`True`, api_secret_empty=`True`
- Symbol/interval: `ETHUSDC` / `15m`
- Strategy variant: `original_pivot_reversal`
- Public market dry-run: `True`
- Public market WS-only: `False`
- Cached filters allowed: `False`

## Connectivity

- F2 gate status: `passed_public_rest_may_request_f3`
- REST 451 present: `False`
- Mainnet public REST all OK: `True`
- Testnet public REST all OK: `True`
- Mainnet kline WS OK: `True`
- Mainnet bookTicker WS OK: `True`

| Endpoint | OK | Status | Classification |
| --- | --- | --- | --- |
| `mainnet_ping` | `True` | `200` | `ok` |
| `mainnet_time` | `True` | `200` | `ok` |
| `mainnet_exchangeInfo` | `True` | `200` | `ok` |
| `mainnet_bookTicker` | `True` | `200` | `ok` |
| `testnet_ping` | `True` | `200` | `ok` |
| `testnet_time` | `True` | `200` | `ok` |
| `testnet_exchangeInfo` | `True` | `200` | `ok` |
| `testnet_bookTicker` | `True` | `200` | `ok` |
| `mainnet_kline_ws` | `True` | `None` | `ok` |
| `mainnet_bookticker_ws` | `True` | `None` | `ok` |

## REST Filters

- ExchangeInfo REST event present: `True`
- Filters source: `EXCHANGE_INFO_REST`
- Safe for live flag from parser: `True`
- Dry-run-only flag from parser: `False`
- Tick size: `0.01`
- Step size: `0.001`
- Min qty: `0.001`
- Min notional: `20`
- REST bookTicker loaded: `True`

## Forced Replay

- Passed: `True`
- Market entry attempts: `0`
- STOP_MARKET entry attempts: `0`
- Signed REST calls: `0`
- Real order attempts: `0`

## 20-Minute Public Market Dry-Run Smoke

- Final status: `completed`
- Runtime seconds: `1208.794`
- Kline WS connected count: `1`
- Kline WS reconnect count: `0`
- Kline unclosed count: `2227`
- Kline closed count: `1`
- BookTicker update count: `0`
- BookTicker update count note: smoke ran with `PUBLIC_MARKET_WS_ONLY=false`, so this count is expected to be `0`; REST bookTicker loaded once and bookTicker WS was validated by connectivity diagnosis.
- Strategy update count: `1`
- Pending trigger count: `0`
- Pine stop trigger count: `0`
- Breakout trigger count: `0`
- Entry chase count: `0`
- Simulated entry order count: `0`
- Signed REST count: `0`
- Real order attempt count: `0`
- API error count: `0`
- Max memory MB: `50.61`
- Events log size MB: `0.006`
- Bot log size MB: `0.002`
- Forbidden event types: `none`

## Recommendations

- This dry-run deployment gate: `GO`
- Signed read-only preflight: `GO only after leaked credentials are revoked and a new official Binance key is created, IP-whitelisted to 167.172.69.16, and supplied securely outside chat/screenshots`.
- Testnet order lifecycle: `NO-GO in this task`; next after signed read-only preflight passes and the user explicitly approves.
- Live canary: `NO-GO` until signed read-only and testnet lifecycle pass.
- Full live bot: `NO-GO`.

## Minimal Next Action

Revoke the exposed API key, create a new official Binance API key with only required permissions and trusted IP `167.172.69.16`, then run a signed read-only preflight that does not place orders.
