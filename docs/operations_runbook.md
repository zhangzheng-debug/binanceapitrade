# Operations Runbook

## Local Dry-Run

```powershell
cd D:\quant\ETH15min\ethusdc-pivot-bot
.\.venv\Scripts\Activate.ps1
.\scripts\run_dry.ps1
```

Confirm the configuration reports `binance_interval` as `15m` before relying on any run.

## Public Market Dry-Run

This mode connects to Binance public market data only. It uses TradingView `ETHUSDC.P`, Binance API symbol `ETHUSDC`, and kline stream `ethusdc@kline_15m`. It does not require API keys and does not send signed order requests.

```powershell
.\scripts\run_public_market_dry.ps1
```

Linux/macOS:

```bash
bash scripts/run_public_market_dry.sh
```

Stop it with `Ctrl+C`, or let the configured `PUBLIC_MARKET_DRY_RUN_SECONDS` timeout expire. Check `logs/events.jsonl` for `websocket_connecting`, `websocket_connected`, `kline_update_ignored_unclosed`, and `candle_closed_received`. If no 15m candle closes during the observation window, `public_market_dry_run_timeout` is not a failure.

To confirm no real orders were sent, verify the config has `DRY_RUN=true`, `LIVE_TRADING=false`, and `PUBLIC_MARKET_DRY_RUN=true`, then check logs for dry-run events only. No API key is required for this mode.

## Server Public Market Dry-Run

Phase 3A server run, after bundle deployment only:

```bash
ssh -i C:\Users\MR\.ssh1\id_ed25519 dev@167.99.154.16
cd /home/dev/ethusdc-pivot-bot
source .venv/bin/activate
python scripts/check_config.py
PUBLIC_MARKET_DRY_RUN_SECONDS=180 timeout 190 bash scripts/run_public_market_dry.sh
tail -200 logs/events.jsonl
```

Stop an interactive run with `Ctrl+C`. Do not create systemd, do not leave the bot running in the background, and do not add API keys. After the bounded run, check that no process remains:

```bash
ps aux | grep -i ethusdc | grep -v grep || true
ps aux | grep -i bot | grep -v grep || true
```

If there is an `ethusdc-pivot-bot` residual from a bounded run, investigate that process only. Do not kill unrelated server processes and do not touch `ai-rtl-studio` or `127.0.0.1:18081`.

## Phase 3A.5 WS-Only Dry-Run

Use this path while REST 451 remains unresolved:

```bash
python scripts/check_config.py
python scripts/scan_secrets.py
python scripts/diagnose_binance_connectivity.py
PUBLIC_MARKET_DRY_RUN_SECONDS=300 timeout 310 bash scripts/run_public_market_ws_only_dry.sh
```

Expected logs:

- `ws_only_fallback_enabled`
- `rest_451_detected` if REST `exchangeInfo` still returns HTTP 451
- `exchange_info_loaded_from_cache` with `dry_run_only=true`
- `websocket_connected` for kline via `/market`
- `book_ticker_ws_connected` for bookTicker via `/public`
- `book_ticker_update_parsed`
- `maker_price_sample`
- `kline_update_ignored_unclosed` for `k.x=false` updates
- `candle_closed_received` only if a 15m candle closes during the bounded window

To confirm no signed order path was reached:

```bash
grep -R "POST /fapi/v1/order\|PUT /fapi/v1/order\|DELETE /fapi/v1/order\|signed_order\|LIVE_TRADING=true" logs docs reports 2>/dev/null || true
```

To confirm the 15m lock:

```bash
python scripts/check_config.py | grep '"binance_interval": "15m"'
```

Rollback is directory-based. Keep the previous deployment as `/home/dev/ethusdc-pivot-bot-prev-phase3a5-YYYYmmdd-HHMMSS`, then restore that directory manually only after stopping any bounded `ethusdc-pivot-bot` process from the same run.

## Phase 3B User Service Dry-Run

Phase 3B uses a user-level systemd unit only. It is not system-wide, not enabled for boot autostart, not testnet, and not live.

Install the user unit after server checks pass:

```bash
cd /home/dev/ethusdc-pivot-bot
source .venv/bin/activate
python -m pytest
python scripts/check_config.py
python scripts/scan_secrets.py
python scripts/diagnose_binance_connectivity.py
export I_APPROVE_PHASE3B_USER_SYSTEMD_DRY_RUN=YES
bash scripts/install_user_systemd_dry_run.sh
```

Start one manual observation:

```bash
systemctl --user start ethusdc-pivot-bot-dry-run.service
```

Status and logs:

```bash
bash scripts/phase3b_user_service_status.sh
journalctl --user -u ethusdc-pivot-bot-dry-run.service -f
```

Stop:

```bash
bash scripts/phase3b_user_service_stop.sh
```

Uninstall the user unit only:

```bash
export I_APPROVE_PHASE3B_USER_SYSTEMD_UNINSTALL=YES
bash scripts/phase3b_user_service_uninstall.sh
```

Prepare, but do not start, a 6-hour user-service observation after 1h GO and explicit approval:

```bash
export I_APPROVE_PHASE3B_6H_PREPARE=YES
bash scripts/phase3b_prepare_6h_user_service.sh
```

This writes a user-service drop-in with `PHASE3B_BOUNDED_RUNTIME_SECONDS=21600` and `RuntimeMaxSec=21700`, reloads the user manager, and does not start or enable the service.

Rollback:

```bash
cd /home/dev
mv ethusdc-pivot-bot ethusdc-pivot-bot-bad-phase3b-YYYYmmdd-HHMMSS
mv ethusdc-pivot-bot-prev-phase3b-YYYYmmdd-HHMMSS ethusdc-pivot-bot
```

Verify no live:

```bash
python scripts/check_config.py
grep -R -F 'LIVE_TRADING=true' .env logs 2>/dev/null || true
```

Verify no signed order:

```bash
grep -R -F 'POST /fapi/v1/order' logs 2>/dev/null || true
grep -R -F 'PUT /fapi/v1/order' logs 2>/dev/null || true
grep -R -F 'DELETE /fapi/v1/order' logs 2>/dev/null || true
```

Verify no background residue:

```bash
ps aux | grep -i ethusdc | grep -v grep || true
ps aux | grep -i pivot | grep -v grep || true
pgrep -af '[p]ython.*bot' || true
```

## Forced Trigger Replay

Run this when the real-market smoke has not produced pending-trigger events:

```bash
cd /home/dev/ethusdc-pivot-bot
source .venv/bin/activate
python scripts/replay_forced_original_pivot_trigger.py
cat reports/forced_original_pivot_trigger_replay.json
```

This is synthetic and offline. It does not require API keys, signed REST, testnet, live, or systemd. It verifies that a signal-present original-Pine path creates a pending trigger, detects the trigger from live-style data, starts maker-only entry chasing, creates a dry-run `LIMIT + GTX` order, and avoids MARKET/STOP_MARKET entry.

## New Server F2 Migration Check

Before running the full bot on a replacement server, copy `tools/f2_migration_checker/` and run:

```bash
cd tools/f2_migration_checker
bash run_f2_check.sh
cat f2_migration_check_result.json
```

If mainnet REST returns 451, that server is not suitable for Binance Futures live. Do not use proxy, VPN, tunnel, firewall changes, or other bypass behavior. Choose a lawful environment where Binance Futures REST is reachable.

## Configuration Check

```powershell
python .\scripts\check_config.py
```

This prints a redacted safety summary and does not print secrets.

## Logs

- `logs/bot.log`
- `logs/events.jsonl`

## State Backup

Stop the bot first, then copy `data/state.sqlite3` to a timestamped backup path. Do not edit the database while the bot is running.

## State Mismatch

Dry-run mismatch only prints a reconciliation summary. Live mismatch must stop startup by default. Do not blindly cancel unknown orders unless `AUTO_CANCEL_UNKNOWN_ORDERS=true` has been deliberately reviewed.

## API Errors

- Post-only would take: retry maker-only path.
- Timestamp drift: sync server time and retry safely.
- Rate limit: back off.
- Network timeout: retry only idempotent reads automatically; order mutations need careful status reconciliation.
- Unknown error: alert and stop live order flow.

## Stop Bot

Local dry-run: press `Ctrl+C`.

Future systemd deployment, after approval only:

```bash
sudo systemctl stop ethusdc-pivot-bot.service
```

## Calendar Reminder

Server or credit expiry: 2026-08-01. This is a calendar item, not a current development blocker.
