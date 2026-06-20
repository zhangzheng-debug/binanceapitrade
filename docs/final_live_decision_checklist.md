# Final Live Decision Checklist

Current gate: `READY_FOR_FINAL_LIVE_STRATEGY_DECISION`

## Proven So Far

- Singapore server path: `/root/ethusdc-pivot-bot`
- Mainnet public REST: passed in F2 migration checker.
- Signed read-only preflight: `SIGNED_READONLY_PREFLIGHT_GO`.
- Exchange filters source: `EXCHANGE_INFO_REST`.
- Order mode: `account_equity_pct`.
- Position size pct: `200`.
- Live trading flag: `LIVE_TRADING=false`.
- Latest order-control canary: `LIVE_ORDER_CONTROL_CANARY_GO`.
- Latest order-control counts: real order attempts `2`, LIMIT GTX attempts `2`, modify attempts `2`, cancel attempts `2`.
- Latest order-control final open orders: `0`.
- Latest order-control unexpected fill: `False`.
- Current account position mode: One-way Mode.
- Live strategy capability audit: `LIVE_STRATEGY_CAPABILITY_GO`.
- Live strategy runner in `python -m bot.main`: implemented behind final approval gate.
- Live stop management: wired to maker stop chase plus One-way `MARKET reduceOnly` fallback.
- Final live user-service template: prepared, user-level only, not installed, not boot-enabled.
- Tiny strategy canary entry-fill cap: `LIVE_STRATEGY_MAX_ENTRY_FILLS=1`.
- Full live strategy position-mode requirement: One-way Mode, because strategy stop fallback requires `MARKET reduceOnly`.

## Not Yet Proven

- Final live strategy start approval: not given yet.
- Tiny live strategy canary: not started.
- Full live strategy under systemd: not approved and not started.
- Full live strategy in Hedge Mode: not allowed for this release.

## Next Human Choice Required

Choose whether to start the supervised tiny live strategy canary.

Final live strategy start remains blocked until `I_APPROVE_FINAL_LIVE_STRATEGY_START=YES` is explicitly set and `scripts/final_live_start_gate.py` reports `FINAL_LIVE_START_GATE_GO`.

Important: even if the Hedge Mode order-control canary is GO, final full strategy still requires switching to One-way Mode before live start. Hedge Mode is useful only to test order-control primitives under the current account mode.

## Prepared Commands After Choice

These commands are prepared but must not be run until the matching human choice is explicit.

Install the user-level one-shot order-control canary service:

```bash
cd /root/ethusdc-pivot-bot
export I_APPROVE_ORDER_CONTROL_CANARY_USER_SERVICE=YES
bash scripts/install_order_control_canary_user_service.sh
```

Run after switching the account to One-way Mode:

```bash
cd /root/ethusdc-pivot-bot
export I_APPROVE_ORDER_CONTROL_CANARY_START=YES
bash scripts/start_order_control_canary_user_service.sh
```

Run only if Hedge Mode is intentionally kept and explicitly approved:

```bash
cd /root/ethusdc-pivot-bot
export I_APPROVE_ORDER_CONTROL_CANARY_START=YES
export I_APPROVE_HEDGE_MODE_ORDER_CONTROL_CANARY=YES
bash scripts/start_order_control_canary_user_service.sh
```

Install the final live strategy user service after final approval:

```bash
cd /root/ethusdc-pivot-bot
export I_APPROVE_FINAL_LIVE_STRATEGY_USER_SERVICE=YES
bash scripts/install_final_live_strategy_user_service.sh
```

Start the final tiny live strategy canary only after the final live gate is GO:

```bash
cd /root/ethusdc-pivot-bot
export I_APPROVE_FINAL_LIVE_STRATEGY_START=YES
bash scripts/start_final_live_strategy_user_service.sh
```

## Hard Stops

- Do not set `LIVE_TRADING=true` for order-control canary.
- Do not start `python -m bot.main` as live strategy before order-control canary is GO.
- Do not enable boot autostart.
- Do not install a system-wide service.
- Do not use MARKET or STOP_MARKET for entry.
- Do not change `BINANCE_INTERVAL=15m`.
