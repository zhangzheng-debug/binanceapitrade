# Forced Original Pivot Trigger Replay Report

Generated UTC: `2026-06-21T13:09:21.529485+00:00`

This replay is fully synthetic. It does not read API keys, sign REST requests, place real orders, or require Binance network access.

- Passed: `True`
- Final gate: `GO_FOR_WS_ONLY_DRY_RUN_CHAIN_NO_GO_FOR_LIVE`
- Market entry attempts: `0`
- STOP_MARKET entry attempts: `0`
- Signed REST calls: `0`
- Real order attempts: `0`

## Replay Results

| Scenario | OK | Key events |
| --- | --- | --- |
| Long trigger | `True` | `pine_stop_trigger_detected, breakout_triggered_original_pine` |
| Short trigger | `True` | `pine_stop_trigger_detected, breakout_triggered_original_pine` |
| Ambiguous dual trigger | `True` | `ambiguous_dual_trigger_skipped` |
| Active chase blocks opposite | `True` | `trigger_blocked_active_chase` |
| Position blocks entry | `True` | `ignored_due_to_position` |
| Missed trigger logging | `True` | long `missed_long_trigger_on_closed_candle, pending_long_stop_invalidated` / short `missed_short_trigger_on_closed_candle, pending_short_stop_invalidated` |
| Stop-loss fallback | `True` | allowed MARKET reduceOnly fallback count `1` |

## Conclusion

The original Pine pending-trigger chain is validated for synthetic signal-present cases. This does not change the live gate: current mainnet REST 451 still keeps live canary and full live bot NO-GO.
