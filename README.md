# ETHUSDC Pivot Bot

Dry-run-first Python project for an ETHUSDC.P / Binance ETHUSDC USD-M Futures pivot reversal bot.

Current state:

- Singapore server `167.172.69.16` passed Binance USD-M Futures mainnet REST and WebSocket checks.
- The long-running live strategy is deployed at `/root/ethusdc-pivot-bot`.
- The live strategy user service is `active`, `enabled`, uses `Restart=on-failure`, and has `RuntimeMaxUSec=infinity`.
- A server-side read-only monitor timer is `active` and `enabled`; it writes `reports/live_monitor_status.json` and `docs/live_monitor_status.md` every 15 minutes.
- Default checked-in configuration remains safe: `DRY_RUN=true`, `LIVE_TRADING=false`, and empty API credentials.
- Current only supported timeframe is `BINANCE_INTERVAL=15m`.
- TradingView symbol is `ETHUSDC.P`; Binance API symbol is `ETHUSDC`.
- Binance kline stream is locked to `ethusdc@kline_15m`.
- Binance bookTicker WebSocket stream is locked to `ethusdc@bookTicker`.
- Strategy core is TradingView original `Pivot Reversal Strategy`, not the older Safer variant.
- Pivot state updates only from closed 15m candles. Unclosed kline updates may trigger pending Pine stop levels, but never update pivots.
- Pine `strategy.entry(..., stop=...)` maps to a local pending trigger plus maker-only chaser, not a Binance STOP or STOP_MARKET entry.
- Entry is maker-only `LIMIT` + `GTX`; `MARKET` entry and `STOP_MARKET` entry are forbidden.
- Add-on entries and reversals are blocked while an ETHUSDC position is open.
- No exchange-side `STOP_MARKET` protective order is placed after entry.
- Stop logic first tries maker-only reduce-only exit, then uses `MARKET reduceOnly` only for the remaining position after timeout.

This is not investment advice. Live derivatives trading can lose more than expected through leverage, liquidation, outages, latency, API failures, and software defects.

## Setup

```powershell
cd D:\quant\ETH15min\ethusdc-pivot-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
```

Keep `.env` out of git. Leave `DRY_RUN=true` unless live trading has been separately reviewed.

For the full reproducible handoff, start here:

- `docs/REPRODUCIBLE_DEPLOYMENT_GUIDE.md`
- `docs/CODEX_AUTOMATION_HANDOFF.md`
- `docs/GITHUB_PACKAGE_MANIFEST.md`
- `docs/SERVER_CURRENT_STATE_SANITIZED.md`

## Dry-Run

```powershell
.\scripts\run_dry.ps1
```

Or:

```bash
./scripts/run_dry.sh
```

## Public Market Dry-Run

This mode reads real Binance public market data, does not require API keys, does not send signed order requests, and still routes all order behavior through the dry-run exchange.

```powershell
.\scripts\run_public_market_dry.ps1
```

Linux/macOS:

```bash
bash scripts/run_public_market_dry.sh
```

The mode is for validating the 15m kline stream, closed-candle filtering, pivot state machine, and dry-run logs. It uses `ethusdc@kline_15m` on the Binance USD-M `/market` WebSocket routed path.

## Phase 3A.5 WS-Only Dry-Run

When REST is blocked with HTTP 451, use only bounded public WebSocket dry-run:

```bash
bash scripts/run_public_market_ws_only_dry.sh
```

This mode requires `DRY_RUN=true`, `LIVE_TRADING=false`, `PUBLIC_MARKET_DRY_RUN=true`, `PUBLIC_MARKET_WS_ONLY=true`, empty Binance API credentials, and cached filters that are marked dry-run-only. It connects kline via `/market` and bookTicker via `/public`, computes maker-price samples, and still forbids signed REST and real orders.

Run the public connectivity diagnosis with:

```powershell
python scripts/diagnose_binance_connectivity.py
```

Run the secret scanner before packaging or deployment:

```powershell
python scripts/scan_secrets.py
```

## Long-Running Server Monitor

The server-side monitor is a user-level systemd timer:

```bash
systemctl --user status ethusdc-pivot-bot-live-monitor.timer --no-pager
cat /root/ethusdc-pivot-bot/docs/live_monitor_status.md
```

It is read-only. It checks service state, systemd enablement, runtime cap, root linger, managed-position marker, open orders, position amount, market heartbeat, and abnormal events.

## Tests

```powershell
python -m pytest
```

The unit tests avoid external API calls.

## Logs

- Human-readable logs: `logs/bot.log`
- Structured JSON events: `logs/events.jsonl`

Secrets are not logged. `scripts/check_config.py` prints only a redacted safety summary.

## Layout

- `src/bot/config.py`: safety-gated configuration.
- `src/bot/strategy_pivot.py`: TradingView original pivot state machine using closed candles only.
- `src/bot/trigger_monitor.py`: local Pine stop-trigger monitor for unclosed kline/bookTicker updates.
- `src/bot/exchange_filters.py`: Decimal tick/step parsing, quantization, maker prices.
- `src/bot/execution_maker_chaser.py`: maker entry and stop chasers.
- `src/bot/dry_run_exchange.py`: simulated exchange for tests and dry-run.
- `src/bot/binance_client.py`: REST adapter skeleton, gated from real orders unless live mode is explicit.
- `src/bot/state_store.py`: SQLite schema and event persistence.
- `src/bot/live_position_state.py`: managed-position marker for safe restart/resume.
- `docs/`: architecture, trading rules, operations, deployment notes, API notes, and testing plan.
