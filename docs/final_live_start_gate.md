# Final Live Start Gate

Generated UTC: `2026-06-20T17:20:09.436093+00:00`

Final verdict: `FINAL_LIVE_START_GATE_NO_GO`
Approved for final live strategy start: `False`

## Checks

- final_human_approval: `False` (missing I_APPROVE_FINAL_LIVE_STRATEGY_START=YES)
- signed_readonly_preflight: `True` (SIGNED_READONLY_PREFLIGHT_GO)
- order_control_canary: `True` (LIVE_ORDER_CONTROL_CANARY_GO)
- live_strategy_capability: `True` (LIVE_STRATEGY_CAPABILITY_GO)
- final_readiness_gate: `True` (READY_FOR_FINAL_LIVE_STRATEGY_DECISION)
- one_way_position_mode_for_strategy: `True` (False)
- exchange_info_rest: `True` (EXCHANGE_INFO_REST)
- no_open_orders_after_canary: `True` (0)
- no_unexpected_fill: `True` (False)
- order_mode: `True` (account_equity_pct)
- position_size_pct: `True` (200)
- config_symbol: `True` (ETHUSDC)
- config_interval: `True` (15m)
- config_mainnet: `True` (mainnet)
- config_live_trading_false_until_start: `True` (False)
- api_credentials_present: `True` ({'has_api_key': True, 'has_api_secret': True})

Next required human instruction: `decide whether to start a tiny live strategy canary under a supervised service`
