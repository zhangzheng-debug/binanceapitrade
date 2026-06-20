# Live Strategy Capability Audit

Generated UTC: `2026-06-20T17:20:08.466103+00:00`
Final verdict: `LIVE_STRATEGY_CAPABILITY_GO`
Live strategy runner implemented: `True`
Main path: `src/bot/main.py`
Live runner path: `src/bot/live_strategy_runner.py`

## Evidence

- Has live runner function: `True`
- Has one-shot live entry canary primitive: `True`
- Uses account-equity sizing: `True`
- Uses MakerChaser: `True`
- Has live stop management: `True`
- Has public dry-run runner: `True`
- LIVE_TRADING request is logged: `True`
- account_equity_pct is blocked in public dry-run path: `True`

## Blockers

- None
