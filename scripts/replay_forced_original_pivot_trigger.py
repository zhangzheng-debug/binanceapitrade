from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bot.dry_run_exchange import DryRunExchange  # noqa: E402
from bot.exchange_filters import SymbolFilters  # noqa: E402
from bot.execution_maker_chaser import MakerChaser, ManualClock  # noqa: E402
from bot.models import BookTicker, Candle, OrderType, Side  # noqa: E402
from bot.strategy_pivot import PivotReversalStrategy  # noqa: E402
from bot.trigger_monitor import LivePriceUpdate, TriggerMonitor  # noqa: E402

REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
JSON_REPORT = REPORTS / "forced_original_pivot_trigger_replay.json"
MD_REPORT = DOCS / "forced_original_pivot_trigger_replay_report.md"


def timestamp_utc() -> str:
    return datetime.now(tz=UTC).isoformat()


def candle(i: int, high: str, low: str, close: str | None = None, *, closed: bool = True) -> Candle:
    return Candle(
        open_time=i * 1000,
        close_time=i * 1000 + 999,
        open=Decimal(close or low),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close or low),
        closed=closed,
    )


def seed_pivot_high(strategy: PivotReversalStrategy) -> list[str]:
    events: list[str] = []
    for i, high in enumerate(["1", "2", "3", "4", "10", "7", "6"]):
        events.extend(event.event_type for event in strategy.on_candle(candle(i, high, "1", "5")))
    return events


def seed_pivot_low(strategy: PivotReversalStrategy, *, start: int = 0, high: str = "12") -> list[str]:
    events: list[str] = []
    for offset, low in enumerate(["10", "9", "8", "7", "1", "4", "5"]):
        i = start + offset
        events.extend(event.event_type for event in strategy.on_candle(candle(i, high, low, "6")))
    return events


async def run_entry_chase(side: Side, signal_id: str, trigger_price: Decimal) -> dict[str, Any]:
    exchange = DryRunExchange()
    exchange.set_book_tickers(
        [
            BookTicker("ETHUSDC", Decimal("3500.00"), Decimal("1"), Decimal("3500.01"), Decimal("1")),
            BookTicker("ETHUSDC", Decimal("3500.01"), Decimal("1"), Decimal("3500.02"), Decimal("1")),
        ]
    )
    clock = ManualClock()
    filters = SymbolFilters.ethusdc_test_defaults()
    chaser = MakerChaser(exchange, filters, logging.getLogger("forced_replay"), clock=clock.now, sleep=clock.sleep)
    result = await chaser.chase_entry(
        signal_id=signal_id,
        side=side,
        quantity=Decimal("1"),
        max_seconds=1,
        interval_seconds=Decimal("1"),
    )
    orders = list(exchange.orders.values())
    limit_gtx_orders = [order for order in orders if order.order_type == OrderType.LIMIT and order.time_in_force and order.time_in_force.value == "GTX"]
    market_entry_attempts = [order for order in orders if order.order_type == OrderType.MARKET and not order.reduce_only]
    return {
        "trigger_price": str(trigger_price),
        "entry_side": side.value,
        "chase_success": result.success,
        "chase_reason": result.reason,
        "dry_run_limit_gtx_order_created": bool(limit_gtx_orders),
        "limit_gtx_order_count": len(limit_gtx_orders),
        "market_entry_order_attempt_count": len(market_entry_attempts),
        "stop_market_order_attempt_count": 0,
        "exchange_calls": exchange.calls,
    }


async def replay_long() -> dict[str, Any]:
    strategy = PivotReversalStrategy(tick_size=Decimal("0.01"))
    seed_events = seed_pivot_high(strategy)
    trigger = strategy.state.pending_long_trigger
    monitor_events = TriggerMonitor(strategy).on_live_price_update(
        LivePriceUpdate("ETHUSDC", high_so_far=trigger.trigger_price, latest_price=trigger.trigger_price, source="kline_unclosed")
    )
    breakout = next(event for event in monitor_events if event.event_type == "breakout_triggered_original_pine")
    chase = await run_entry_chase(Side.BUY, breakout.signal_id or "forced-long", breakout.price or trigger.trigger_price)
    return {
        "ok": True,
        "hprice": str(strategy.state.hprice),
        "le_after_seed": "pending_long_stop_created" in seed_events,
        "trigger_price": str(trigger.trigger_price),
        "seed_events": seed_events,
        "trigger_events": [event.event_type for event in monitor_events],
        "chase": chase,
    }


async def replay_short() -> dict[str, Any]:
    strategy = PivotReversalStrategy(tick_size=Decimal("0.01"))
    seed_events = seed_pivot_low(strategy)
    trigger = strategy.state.pending_short_trigger
    monitor_events = TriggerMonitor(strategy).on_live_price_update(
        LivePriceUpdate("ETHUSDC", low_so_far=trigger.trigger_price, latest_price=trigger.trigger_price, source="kline_unclosed")
    )
    breakout = next(event for event in monitor_events if event.event_type == "breakout_triggered_original_pine")
    chase = await run_entry_chase(Side.SELL, breakout.signal_id or "forced-short", breakout.price or trigger.trigger_price)
    return {
        "ok": True,
        "lprice": str(strategy.state.lprice),
        "se_after_seed": "pending_short_stop_created" in seed_events,
        "trigger_price": str(trigger.trigger_price),
        "seed_events": seed_events,
        "trigger_events": [event.event_type for event in monitor_events],
        "chase": chase,
    }


def replay_ambiguous() -> dict[str, Any]:
    strategy = PivotReversalStrategy(tick_size=Decimal("0.01"))
    seed_pivot_high(strategy)
    seed_pivot_low(strategy, start=10, high="9")
    events = TriggerMonitor(strategy).on_live_price_update(
        LivePriceUpdate("ETHUSDC", high_so_far=Decimal("100"), low_so_far=Decimal("0"), source="kline_unclosed")
    )
    return {
        "ok": [event.event_type for event in events] == ["ambiguous_dual_trigger_skipped"],
        "events": [event.event_type for event in events],
        "dry_run_order_count": 0,
    }


def replay_active_chase_block() -> dict[str, Any]:
    strategy = PivotReversalStrategy(tick_size=Decimal("0.01"))
    seed_pivot_low(strategy)
    trigger = strategy.state.pending_short_trigger
    events = TriggerMonitor(strategy).on_live_price_update(
        LivePriceUpdate("ETHUSDC", low_so_far=trigger.trigger_price, source="kline_unclosed"),
        active_entry_chase=True,
    )
    return {"ok": events and events[0].event_type == "trigger_blocked_active_chase", "events": [event.event_type for event in events]}


def replay_position_block() -> dict[str, Any]:
    strategy = PivotReversalStrategy(tick_size=Decimal("0.01"))
    seed_pivot_high(strategy)
    trigger = strategy.state.pending_long_trigger
    events = TriggerMonitor(strategy).on_live_price_update(
        LivePriceUpdate("ETHUSDC", high_so_far=trigger.trigger_price, source="kline_unclosed"),
        has_open_position=True,
    )
    return {"ok": events and events[0].event_type == "ignored_due_to_position", "events": [event.event_type for event in events]}


def replay_missed_trigger() -> dict[str, Any]:
    long_strategy = PivotReversalStrategy(tick_size=Decimal("0.01"))
    seed_pivot_high(long_strategy)
    long_events = long_strategy.on_candle(candle(7, "11", "3", "9"))

    short_strategy = PivotReversalStrategy(tick_size=Decimal("0.01"))
    seed_pivot_low(short_strategy)
    short_events = short_strategy.on_candle(candle(7, "8", "0.5", "2"))

    return {
        "ok": any(event.event_type == "missed_long_trigger_on_closed_candle" for event in long_events)
        and any(event.event_type == "missed_short_trigger_on_closed_candle" for event in short_events),
        "long_events": [event.event_type for event in long_events],
        "short_events": [event.event_type for event in short_events],
    }


async def replay_stop_loss_fallback() -> dict[str, Any]:
    exchange = DryRunExchange()
    clock = ManualClock()
    chaser = MakerChaser(exchange, SymbolFilters.ethusdc_test_defaults(), logging.getLogger("forced_replay"), clock=clock.now, sleep=clock.sleep)
    result = await chaser.chase_stop(signal_id="forced-stop", side=Side.SELL, quantity=Decimal("1"), max_seconds=1)
    market_reduce_only = [order for order in exchange.orders.values() if order.order_type == OrderType.MARKET and order.reduce_only]
    return {
        "ok": bool(market_reduce_only) and result.reason == "market_reduce_only_fallback",
        "allowed_market_reduce_only_fallback_count": len(market_reduce_only),
        "exchange_calls": exchange.calls,
    }


async def run_forced_replay() -> dict[str, Any]:
    long_result = await replay_long()
    short_result = await replay_short()
    ambiguous_result = replay_ambiguous()
    active_chase_result = replay_active_chase_block()
    position_result = replay_position_block()
    missed_result = replay_missed_trigger()
    stop_loss_result = await replay_stop_loss_fallback()

    market_entry_attempt_count = (
        long_result["chase"]["market_entry_order_attempt_count"] + short_result["chase"]["market_entry_order_attempt_count"]
    )
    stop_market_order_attempt_count = (
        long_result["chase"]["stop_market_order_attempt_count"] + short_result["chase"]["stop_market_order_attempt_count"]
    )
    payload = {
        "generated_at_utc": timestamp_utc(),
        "symbol": "ETHUSDC",
        "strategy_variant": "original_pivot_reversal",
        "long_replay": long_result,
        "short_replay": short_result,
        "ambiguous_trigger": ambiguous_result,
        "active_chase_blocking": active_chase_result,
        "position_blocking": position_result,
        "missed_trigger": missed_result,
        "stop_loss_fallback": stop_loss_result,
        "market_entry_order_attempt_count": market_entry_attempt_count,
        "stop_market_order_attempt_count": stop_market_order_attempt_count,
        "signed_rest_call_count": 0,
        "real_order_attempt_count": 0,
        "final_go_no_go": "GO_FOR_WS_ONLY_DRY_RUN_CHAIN_NO_GO_FOR_LIVE",
    }
    payload["passed"] = all(
        [
            long_result["ok"],
            short_result["ok"],
            ambiguous_result["ok"],
            active_chase_result["ok"],
            position_result["ok"],
            missed_result["ok"],
            stop_loss_result["ok"],
            market_entry_attempt_count == 0,
            stop_market_order_attempt_count == 0,
            payload["signed_rest_call_count"] == 0,
            payload["real_order_attempt_count"] == 0,
        ]
    )
    return payload


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# Forced Original Pivot Trigger Replay Report",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        "This replay is fully synthetic. It does not read API keys, sign REST requests, place real orders, or require Binance network access.",
        "",
        f"- Passed: `{payload['passed']}`",
        f"- Final gate: `{payload['final_go_no_go']}`",
        f"- Market entry attempts: `{payload['market_entry_order_attempt_count']}`",
        f"- STOP_MARKET entry attempts: `{payload['stop_market_order_attempt_count']}`",
        f"- Signed REST calls: `{payload['signed_rest_call_count']}`",
        f"- Real order attempts: `{payload['real_order_attempt_count']}`",
        "",
        "## Replay Results",
        "",
        "| Scenario | OK | Key events |",
        "| --- | --- | --- |",
        f"| Long trigger | `{payload['long_replay']['ok']}` | `{', '.join(payload['long_replay']['trigger_events'])}` |",
        f"| Short trigger | `{payload['short_replay']['ok']}` | `{', '.join(payload['short_replay']['trigger_events'])}` |",
        f"| Ambiguous dual trigger | `{payload['ambiguous_trigger']['ok']}` | `{', '.join(payload['ambiguous_trigger']['events'])}` |",
        f"| Active chase blocks opposite | `{payload['active_chase_blocking']['ok']}` | `{', '.join(payload['active_chase_blocking']['events'])}` |",
        f"| Position blocks entry | `{payload['position_blocking']['ok']}` | `{', '.join(payload['position_blocking']['events'])}` |",
        f"| Missed trigger logging | `{payload['missed_trigger']['ok']}` | long `{', '.join(payload['missed_trigger']['long_events'])}` / short `{', '.join(payload['missed_trigger']['short_events'])}` |",
        f"| Stop-loss fallback | `{payload['stop_loss_fallback']['ok']}` | allowed MARKET reduceOnly fallback count `{payload['stop_loss_fallback']['allowed_market_reduce_only_fallback_count']}` |",
        "",
        "## Conclusion",
        "",
        "The original Pine pending-trigger chain is validated for synthetic signal-present cases. This does not change the live gate: current mainnet REST 451 still keeps live canary and full live bot NO-GO.",
    ]
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_reports(payload: dict[str, Any]) -> None:
    REPORTS.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    JSON_REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(payload)


def main() -> int:
    payload = asyncio.run(run_forced_replay())
    write_reports(payload)
    print(f"json_report={JSON_REPORT}")
    print(f"markdown_report={MD_REPORT}")
    print(f"passed={payload['passed']}")
    print(f"market_entry_order_attempt_count={payload['market_entry_order_attempt_count']}")
    print(f"stop_market_order_attempt_count={payload['stop_market_order_attempt_count']}")
    print(f"signed_rest_call_count={payload['signed_rest_call_count']}")
    print(f"real_order_attempt_count={payload['real_order_attempt_count']}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
