# Multi-Symbol Pivot Bot

Dry-run-first Python project for Binance USD-M Futures pivot-reversal execution.

This repository is a sanitized handoff package. It contains source, tests,
systemd user units, runbooks, and reproduction notes. It does not contain API
keys, SSH private keys, `.env.live.readonly`, `.venv`, live logs, or SQLite
state.

This is not investment advice. Live derivatives trading can lose money through
leverage, liquidation, outages, latency, API failures, and software defects.

## Current Operational State

Snapshot: `2026-06-21`.

- Server: DigitalOcean Singapore `167.172.69.16`.
- Server project path: `/root/ethusdc-pivot-bot`.
- All live strategy services are currently stopped and disabled:
  - `ethusdc-pivot-bot-live-strategy.service`
  - `btcusdc-pivot-bot-live-strategy.service`
  - `xrpusdc-pivot-bot-live-strategy.service`
- Stop verification after shutdown:
  - ETHUSDC signed read-only preflight: `SIGNED_READONLY_PREFLIGHT_GO`
  - BTCUSDC signed read-only preflight: `SIGNED_READONLY_PREFLIGHT_GO`
  - XRPUSDC signed read-only preflight: `SIGNED_READONLY_PREFLIGHT_GO`
  - open orders: `0`
  - position quantity: `0`
  - order endpoint called by preflight: `false`
- Read-only monitor timers may remain installed; they are not trading
  strategies and must not place, modify, or cancel orders.

## Strategy Matrix

All live strategy wrappers use the same strategy core:

```text
STRATEGY_VARIANT=original_pivot_reversal
ORDER_MODE=account_equity_pct
POSITION_SIZE_PCT=100
STOP_LOSS_ENABLED=false
TAKE_PROFIT_ENABLED=false
```

Supported runtime pairs:

| Symbol | Interval | Strategy wrapper | State DB | Log dir |
| --- | --- | --- | --- | --- |
| `ETHUSDC` | `15m` | `scripts/run_final_live_strategy.sh` | `data/state_ETHUSDC_15m.sqlite3` | `logs/ETHUSDC_15m` |
| `BTCUSDC` | `1h` | `scripts/run_final_live_strategy_btcusdc_1h.sh` | `data/state_BTCUSDC_1h.sqlite3` | `logs/BTCUSDC_1h` |
| `XRPUSDC` | `1h` | `scripts/run_final_live_strategy_xrpusdc_1h.sh` | `data/state_XRPUSDC_1h.sqlite3` | `logs/XRPUSDC_1h` |

## Execution Rules

- Strategy core is TradingView original `Pivot Reversal Strategy`, not the
  older Safer variant.
- Pivot state updates only from closed candles for the configured interval.
- Unclosed kline and bookTicker updates may trigger pending Pine stop levels,
  but never update pivots.
- Pine `strategy.entry(..., stop=...)` maps to a local pending trigger plus
  maker-only chaser.
- Entry is maker-only `LIMIT` + `GTX`.
- `MARKET` entry and `STOP_MARKET` entry are forbidden.
- Add-on entries are blocked while the same symbol has an open position or
  active entry chase.
- The bot does not place an exchange-side `STOP_MARKET` protective order after
  entry.
- Stop logic first tries maker-only reduce-only exit, then may use
  `MARKET reduceOnly` only for the remaining position after timeout.

## Setup

Windows PowerShell:

```powershell
cd D:\quant\ETH15min\ethusdc-pivot-bot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Linux server:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

Keep `.env` and `.env.live.readonly` out of git. Default checked-in
configuration remains safe: `DRY_RUN=true`, `LIVE_TRADING=false`, and empty API
credentials.

## Validation

Run before packaging or deployment:

```bash
python -m pytest
python scripts/scan_secrets.py
python scripts/check_config.py
python scripts/replay_forced_original_pivot_trigger.py
```

For all three current live profiles:

```bash
BINANCE_SYMBOL=ETHUSDC BINANCE_INTERVAL=15m POSITION_SIZE_PCT=100 python scripts/check_config.py
BINANCE_SYMBOL=BTCUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 python scripts/check_config.py
BINANCE_SYMBOL=XRPUSDC BINANCE_INTERVAL=1h POSITION_SIZE_PCT=100 python scripts/check_config.py
```

## Start Here For Handoff

- `docs/CODEX_AUTOMATION_HANDOFF.md`
- `docs/REPRODUCIBLE_DEPLOYMENT_GUIDE.md`
- `docs/SERVER_CURRENT_STATE_SANITIZED.md`
- `docs/GITHUB_PACKAGE_MANIFEST.md`
- `docs/risk_rules.md`

Historical phase reports remain in `docs/` and `reports/` as evidence from
earlier gates. Treat the files listed above as the current source of truth.

## Common Server Commands

Check stopped strategy state:

```bash
systemctl --user show ethusdc-pivot-bot-live-strategy.service -p ActiveState -p UnitFileState --no-pager
systemctl --user show btcusdc-pivot-bot-live-strategy.service -p ActiveState -p UnitFileState --no-pager
systemctl --user show xrpusdc-pivot-bot-live-strategy.service -p ActiveState -p UnitFileState --no-pager
```

Start a strategy only after explicit approval in the current thread:

```bash
systemctl --user start ethusdc-pivot-bot-live-strategy.service
systemctl --user start btcusdc-pivot-bot-live-strategy.service
systemctl --user start xrpusdc-pivot-bot-live-strategy.service
```

Stop all strategies:

```bash
systemctl --user stop ethusdc-pivot-bot-live-strategy.service btcusdc-pivot-bot-live-strategy.service xrpusdc-pivot-bot-live-strategy.service
systemctl --user disable ethusdc-pivot-bot-live-strategy.service btcusdc-pivot-bot-live-strategy.service xrpusdc-pivot-bot-live-strategy.service
```

Stopping services does not itself cancel exchange orders or close exchange
positions. Run signed read-only preflight afterward and handle any residual
orders/positions deliberately.

## Layout

- `src/bot/config.py`: safety-gated configuration.
- `src/bot/strategy_pivot.py`: original Pine pivot state machine.
- `src/bot/trigger_monitor.py`: local Pine stop-trigger monitor.
- `src/bot/execution_maker_chaser.py`: maker entry and stop chasers.
- `src/bot/binance_client.py`: Binance USD-M REST adapter.
- `src/bot/market_data.py`: dynamic kline stream support.
- `src/bot/book_ticker_stream.py`: dynamic bookTicker stream support.
- `scripts/`: gates, preflight checks, live wrappers, monitor wrappers, bundles.
- `deploy/systemd/`: user-level systemd units and timers.
- `tests/`: safety, strategy, systemd, sizing, and preflight tests.
- `tools/f2_migration_checker/`: public REST/WebSocket migration checker.
