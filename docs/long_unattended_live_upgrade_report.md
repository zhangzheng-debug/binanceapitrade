# Long Unattended Live Upgrade Report

Generated UTC: `2026-06-20T21:24:00Z`

## Scope

- Current live ETHUSDC position was not closed.
- No manual order, manual cancel, or manual reduce-only cleanup was performed.
- The live strategy service was upgraded from a bounded canary unit to a user service suitable for long-running operation.

## Code Changes

- Removed the `RuntimeMaxSec=86400` service cap from `deploy/systemd/ethusdc-pivot-bot-live-strategy.user.service`.
- Added `[Install] WantedBy=default.target` so the user service can be enabled for boot.
- Changed `scripts/run_final_live_strategy.sh` to use restart-safe runtime gates instead of historical final-start reports on every systemd restart.
- Added `LIVE_STRATEGY_RESUME_EXISTING_POSITION` and `LIVE_MANAGED_POSITION_MARKER_PATH`.
- Added `src/bot/live_position_state.py` to write and verify a managed-position marker.
- Changed `LIVE_STRATEGY_MAX_ENTRY_FILLS=0` semantics to mean unlimited entries after the account is flat, while still blocking add-ons during an open position.

## Remote Deployment Evidence

- Server: `root@167.172.69.16`
- Project path: `/root/ethusdc-pivot-bot`
- Bundle: `ethusdc-pivot-bot-long-unattended-live.tar.gz`
- Bundle SHA-256: `6791bf298f3c34aa2065963dab481b3c1ace7eb1331898172b35e2a2a6f254d7`
- Remote pre-upgrade backup: `/root/ethusdc-pivot-bot-pre-long-unattended-20260620T212027Z.tgz`
- Remote targeted tests: passed
- Remote full pytest: passed
- Remote forced original pivot replay: passed
- Remote scan_secrets: passed

## Runtime Evidence After Controlled Restart

- Service active: `active`
- Service enabled: `enabled`
- User linger: `yes`
- Restart policy: `on-failure`
- RuntimeMaxUSec: `infinity`
- MainPID after restart: `32768`
- NRestarts after restart: `0`
- Config in live process:
  - `LIVE_TRADING=true`
  - `DRY_RUN=false`
  - `BINANCE_SYMBOL=ETHUSDC`
  - `BINANCE_INTERVAL=15m`
  - `STRATEGY_VARIANT=original_pivot_reversal`
  - `POSITION_SIZE_PCT=200`
  - `LIVE_STRATEGY_MAX_ENTRY_FILLS=0`
  - `LIVE_STRATEGY_RESUME_EXISTING_POSITION=true`
- Managed marker:
  - side: `LONG`
  - quantity: `2.444`
  - entry price: `1728.88`
- Resume event observed: `live_strategy_resumed_managed_position`
- Market feeds after restart:
  - `book_ticker_ws_connected`
  - `websocket_connected` for `ethusdc@kline_15m`

## Signed Read-Only State After Restart

- Preflight verdict: `SIGNED_READONLY_PREFLIGHT_NO_GO`
- Reason: expected while live ETHUSDC position is open.
- ETHUSDC open orders: `0`
- ETHUSDC position amount: `2.444`
- Order endpoint called by preflight: `False`

## Remaining Operational Notes

- Add-on entries remain blocked while an ETHUSDC position is open.
- Opposite entries remain blocked while an ETHUSDC position is open.
- After the bot closes the position and the account is flat, the long-running service may take a later original-Pine signal again because `LIVE_STRATEGY_MAX_ENTRY_FILLS=0`.
- Manual `systemctl --user stop ethusdc-pivot-bot-live-strategy.service` remains the stop path when the strategy should no longer run.
