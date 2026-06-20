# Phase 3A Server Public-Market Dry-Run Report

Run date: 2026-06-20 UTC

## Summary

Phase 3A deployed the local ETHUSDC Pivot Bot project to the server under an isolated directory and ran a bounded public-market dry-run. No API keys were configured, no signed order path was used, no real orders were sent, no systemd service was created, and no long-running bot process was left behind.

## Deployment

- Server: `dev@167.99.154.16`
- Hostname: `ubuntu-s-2vcpu-8gb-160gb-intel-nyc1`
- Deployment path: `/home/dev/ethusdc-pivot-bot`
- Bundle path uploaded on server: `/home/dev/ethusdc-pivot-bot-phase3a.tar.gz`
- Final deployed bundle SHA-256: `cab0cfbbaba58e568debaea2a6666d34f8bef6a28fb85323f513551ea4b2d011`
- Previous target directories were moved to timestamped backups under `/home/dev/ethusdc-pivot-bot-prev-*`; no unrelated directories were touched.
- Existing AI RTL process on `127.0.0.1:18081` was not stopped or modified.

## Server Environment

- Server Python: `Python 3.12.3`
- Python path: `/usr/bin/python3`
- Disk at deployment path: `/dev/vda1`, 154G size, 98G used, 57G available, 64% used
- Memory at check time: 7.8Gi total, about 7.0Gi available
- `python3 -m venv --help` succeeded, so no system package install was required.

## Venv And Install

- Venv path: `/home/dev/ethusdc-pivot-bot/.venv`
- pip version after upgrade: `pip 26.1.2`
- Install command used: `python -m pip install -e ".[dev]"`
- Install completed inside the project venv without sudo.
- `pytest` was available in the venv after install.

## Configuration

Server `.env` was created from `.env.example`, then set to public-market dry-run:

- `DRY_RUN=true`
- `LIVE_TRADING=false`
- `PUBLIC_MARKET_DRY_RUN=true`
- `PUBLIC_MARKET_DRY_RUN_SECONDS=180`
- `BINANCE_ENV=mainnet`
- `BINANCE_SYMBOL=ETHUSDC`
- `BINANCE_INTERVAL=15m`
- `BINANCE_API_KEY=`
- `BINANCE_API_SECRET=`

`chmod 600 .env` was applied.

`python scripts/check_config.py` result:

- `binance_symbol`: `ETHUSDC`
- `binance_interval`: `15m`
- `dry_run`: `true`
- `live_trading`: `false`
- `public_market_dry_run`: `true`
- `has_api_key`: `false`
- `has_api_secret`: `false`

## Tests

Server command:

```bash
cd /home/dev/ethusdc-pivot-bot
source .venv/bin/activate
python -m pytest
```

Result:

```text
43 passed in 0.45s
```

## Public REST Connectivity

The bounded server public-market dry-run attempted public REST calls:

- `GET https://fapi.binance.com/fapi/v1/exchangeInfo`
- `GET https://fapi.binance.com/fapi/v1/ticker/bookTicker?symbol=ETHUSDC`

Both returned HTTP 451 from Binance/CloudFront on this server network path.

Impact:

- Public REST connectivity is not usable from this server path at this time.
- This did not trigger any signed request.
- The run continued to WebSocket validation.

## WebSocket Connectivity

The bot attempted:

```text
wss://fstream.binance.com/market/stream?streams=ethusdc@kline_15m
```

Result:

- `websocket_connecting`: observed
- `websocket_connected`: observed
- Public WebSocket connectivity: successful
- Stream: `ethusdc@kline_15m`

## Kline Handling

During the 180-second bounded run:

- `kline_update_ignored_unclosed`: 103 observed
- `candle_closed_received`: 0 observed
- `public_market_dry_run_timeout`: observed with `closed_candles=0`
- `public_market_dry_run_finished`: observed

Interpretation:

- The server received live `ETHUSDC` `15m` kline updates from the public WebSocket.
- All received updates during the run were unclosed candles, `k.x=false`.
- The bot ignored those unclosed updates as required.
- No closed 15m candle arrived during this 180-second window; this is not a failure because a short run may not cross a 15m close.
- `k.x=true` strategy entry is covered by local and server pytest; it was not observed live during this short server run.

## Order Safety

Post-run log scan found no forbidden patterns:

- No `signed order`
- No `POST /fapi/v1/order`
- No `PUT /fapi/v1/order`
- No `DELETE /fapi/v1/order`
- No `MARKET order`
- No `LIVE_TRADING=true`

`.env` key check:

```text
BINANCE_API_KEY=
BINANCE_API_SECRET=
```

Conclusion: no real order path was used and no API key was present.

## Process Cleanup

Before deployment, only ETHUSDC bot residual processes were checked. None were found. The existing AI RTL process remained untouched.

After the bounded dry-run:

- `ps aux | grep -i ethusdc | grep -v grep`: no output
- `ps aux | grep -i bot | grep -v grep`: no output

Conclusion: no long-running ETHUSDC bot process was left behind.

## Issues

1. Local `.env.example` empty optional Decimal fields initially failed config parsing on the server. Fixed by treating empty optional Decimal values as `None`; local tests increased to 43 passed and the corrected bundle was redeployed.

2. Shell scripts arrived with Windows CRLF line endings. The server copy of `scripts/run_public_market_dry.sh` and `scripts/run_dry.sh` was normalized to Unix line endings before execution.

3. Binance public REST returned HTTP 451 from the server. WebSocket market data worked, but REST filter/ticker loading did not.

## Recommendation

Do not proceed to live or testnet trading yet.

Phase 3B systemd dry-run is reasonable only if its scope remains public-market/dry-run and explicitly avoids API keys and signed order calls. Before Phase 3B, decide whether HTTP 451 on public REST is acceptable for the dry-run objective or whether to route public REST through a network path that Binance allows.

