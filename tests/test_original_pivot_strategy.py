import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bot.config import Settings
from bot.dry_run_exchange import DryRunExchange, ExchangeFilterFailure
from bot.exchange_filters import SymbolFilters
from bot.execution_maker_chaser import MakerChaser, ManualClock
from bot.models import (
    BookTickerSnapshot,
    Candle,
    OrderRequest,
    OrderType,
    Side,
    StrategySignalSide,
    TimeInForce,
)
from bot.strategy_pivot import PivotReversalStrategy
from bot.trigger_monitor import LivePriceUpdate, TriggerMonitor


def run(coro):
    return asyncio.run(coro)


def c(i: int, high: str, low: str, close: str | None = None, closed: bool = True) -> Candle:
    return Candle(
        open_time=i * 1000,
        close_time=i * 1000 + 999,
        open=Decimal(close or low),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close or low),
        closed=closed,
    )


def seed_pivot_high(strategy: PivotReversalStrategy) -> list:
    events = []
    for i, high in enumerate(["1", "2", "3", "4", "10", "7", "6"]):
        events.extend(strategy.on_candle(c(i, high, "1", "5")))
    return events


def seed_pivot_low(strategy: PivotReversalStrategy) -> list:
    events = []
    for i, low in enumerate(["10", "9", "8", "7", "1", "4", "5"]):
        events.extend(strategy.on_candle(c(i, "12", low, "6")))
    return events


def snapshot(bid: str = "3500.00", ask: str = "3500.01") -> BookTickerSnapshot:
    return BookTickerSnapshot(
        symbol="ETHUSDC",
        best_bid_price=Decimal(bid),
        best_bid_qty=Decimal("1"),
        best_ask_price=Decimal(ask),
        best_ask_qty=Decimal("1"),
        event_time=1,
        received_at=datetime.now(tz=UTC),
        source="websocket",
    )


def test_original_strategy_variant_only() -> None:
    assert Settings(STRATEGY_VARIANT="original_pivot_reversal", _env_file=None).strategy_variant == "original_pivot_reversal"
    with pytest.raises(Exception):
        Settings(STRATEGY_VARIANT="safer_pivot_reversal", _env_file=None)


def test_original_pine_hprice_persists() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_high(strategy)
    assert strategy.state.hprice == Decimal("10")
    strategy.on_candle(c(7, "9", "2", "8"))
    assert strategy.state.hprice == Decimal("10")


def test_original_pine_lprice_persists() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_low(strategy)
    assert strategy.state.lprice == Decimal("1")
    strategy.on_candle(c(7, "8", "2", "3"))
    assert strategy.state.lprice == Decimal("1")


def test_original_pine_le_true_on_pivot_high() -> None:
    strategy = PivotReversalStrategy()
    events = seed_pivot_high(strategy)
    assert strategy.state.le is True
    assert any(event.event_type == "pending_long_stop_created" for event in events)


def test_original_pine_le_false_when_high_crosses_hprice() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_high(strategy)
    strategy.on_candle(c(7, "10.01", "3", "9"))
    assert strategy.state.le is False
    assert strategy.state.pending_long_trigger.active is False


def test_original_pine_le_remains_true_without_high_cross() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_high(strategy)
    strategy.on_candle(c(7, "10", "3", "10"))
    assert strategy.state.le is True
    assert strategy.state.pending_long_trigger.active is True


def test_original_pine_no_close_gate_for_long() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_high(strategy)
    strategy.on_candle(c(7, "10", "3", "10.50"))
    assert strategy.state.le is True
    assert strategy.state.pending_long_trigger.active is True


def test_original_pine_se_true_on_pivot_low() -> None:
    strategy = PivotReversalStrategy()
    events = seed_pivot_low(strategy)
    assert strategy.state.se is True
    assert any(event.event_type == "pending_short_stop_created" for event in events)


def test_original_pine_se_false_when_low_crosses_lprice() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_low(strategy)
    strategy.on_candle(c(7, "8", "0.99", "2"))
    assert strategy.state.se is False
    assert strategy.state.pending_short_trigger.active is False


def test_original_pine_no_close_gate_for_short() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_low(strategy)
    strategy.on_candle(c(7, "8", "1", "0.50"))
    assert strategy.state.se is True
    assert strategy.state.pending_short_trigger.active is True


def test_pending_long_stop_price() -> None:
    strategy = PivotReversalStrategy(tick_size=Decimal("0.01"))
    seed_pivot_high(strategy)
    assert strategy.state.active_long_stop_price == Decimal("10.01")
    assert strategy.state.pending_long_trigger.trigger_price == Decimal("10.01")


def test_pending_short_stop_price() -> None:
    strategy = PivotReversalStrategy(tick_size=Decimal("0.01"))
    seed_pivot_low(strategy)
    assert strategy.state.active_short_stop_price == Decimal("0.99")
    assert strategy.state.pending_short_trigger.trigger_price == Decimal("0.99")


def test_unclosed_kline_does_not_update_pivot() -> None:
    strategy = PivotReversalStrategy()
    for i, high in enumerate(["1", "2", "3", "4", "10", "7"]):
        strategy.on_candle(c(i, high, "1", "5"))
    strategy.on_candle(c(6, "6", "1", "5", closed=False))
    assert strategy.state.hprice is None


def test_unclosed_kline_can_trigger_pending_long() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_high(strategy)
    events = TriggerMonitor(strategy).on_live_price_update(
        LivePriceUpdate("ETHUSDC", high_so_far=Decimal("10.01"), source="kline_unclosed")
    )
    assert any(event.event_type == "breakout_triggered_original_pine" and event.side == StrategySignalSide.LONG for event in events)


def test_unclosed_kline_can_trigger_pending_short() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_low(strategy)
    events = TriggerMonitor(strategy).on_live_price_update(
        LivePriceUpdate("ETHUSDC", low_so_far=Decimal("0.99"), source="kline_unclosed")
    )
    assert any(event.event_type == "breakout_triggered_original_pine" and event.side == StrategySignalSide.SHORT for event in events)


def test_bookticker_can_trigger_long() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_high(strategy)
    events = TriggerMonitor(strategy).on_live_price_update(
        LivePriceUpdate("ETHUSDC", best_ask=Decimal("10.01"), source="bookTicker")
    )
    assert any(event.event_type == "pine_stop_trigger_detected" and event.side == StrategySignalSide.LONG for event in events)


def test_bookticker_can_trigger_short() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_low(strategy)
    events = TriggerMonitor(strategy).on_live_price_update(
        LivePriceUpdate("ETHUSDC", best_bid=Decimal("0.99"), source="bookTicker")
    )
    assert any(event.event_type == "pine_stop_trigger_detected" and event.side == StrategySignalSide.SHORT for event in events)


def test_trigger_starts_maker_chaser_not_market() -> None:
    exchange = DryRunExchange()
    clock = ManualClock()
    chaser = MakerChaser(exchange, SymbolFilters.ethusdc_test_defaults(), logging.getLogger("test"), clock=clock.now, sleep=clock.sleep)
    result = run(chaser.chase_entry(signal_id="sig-long", side=Side.BUY, quantity=Decimal("1"), max_seconds=1))
    assert result.reason == "timeout_no_fill"
    assert "would_place_order" in exchange.calls
    assert "would_market_reduce_only" not in exchange.calls


def test_long_trigger_entry_side_buy() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_high(strategy)
    event = next(event for event in TriggerMonitor(strategy).on_live_price_update(LivePriceUpdate("ETHUSDC", high_so_far=Decimal("11"))) if event.event_type == "breakout_triggered_original_pine")
    assert event.side == StrategySignalSide.LONG
    assert (Side.BUY if event.side == StrategySignalSide.LONG else Side.SELL) == Side.BUY


def test_short_trigger_entry_side_sell() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_low(strategy)
    event = next(event for event in TriggerMonitor(strategy).on_live_price_update(LivePriceUpdate("ETHUSDC", low_so_far=Decimal("0.5"))) if event.event_type == "breakout_triggered_original_pine")
    assert event.side == StrategySignalSide.SHORT
    assert (Side.BUY if event.side == StrategySignalSide.LONG else Side.SELL) == Side.SELL


def test_dual_trigger_ambiguous_skipped() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_high(strategy)
    for i, low in enumerate(["10", "9", "8", "7", "1", "4", "5"], start=10):
        strategy.on_candle(c(i, "9", low, "6"))
    events = TriggerMonitor(strategy).on_live_price_update(
        LivePriceUpdate("ETHUSDC", high_so_far=Decimal("100"), low_so_far=Decimal("0"))
    )
    assert [event.event_type for event in events] == ["ambiguous_dual_trigger_skipped"]
    assert strategy.state.pending_long_trigger.triggered is False
    assert strategy.state.pending_short_trigger.triggered is False


def test_active_chase_blocks_other_trigger() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_high(strategy)
    events = TriggerMonitor(strategy).on_live_price_update(
        LivePriceUpdate("ETHUSDC", high_so_far=Decimal("11")),
        active_entry_chase=True,
    )
    assert events[0].event_type == "trigger_blocked_active_chase"
    assert strategy.state.pending_long_trigger.triggered is False


def test_position_blocks_new_entry_trigger() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_high(strategy)
    events = TriggerMonitor(strategy).on_live_price_update(
        LivePriceUpdate("ETHUSDC", high_so_far=Decimal("11")),
        has_open_position=True,
    )
    assert events[0].event_type == "ignored_due_to_position"
    assert strategy.state.pending_long_trigger.triggered is False


def test_missed_long_trigger_on_closed_candle_logged() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_high(strategy)
    events = strategy.on_candle(c(7, "11", "3", "9"))
    assert any(event.event_type == "missed_long_trigger_on_closed_candle" for event in events)
    assert not any(event.event_type == "breakout_triggered_original_pine" for event in events)


def test_missed_short_trigger_on_closed_candle_logged() -> None:
    strategy = PivotReversalStrategy()
    seed_pivot_low(strategy)
    events = strategy.on_candle(c(7, "8", "0.5", "2"))
    assert any(event.event_type == "missed_short_trigger_on_closed_candle" for event in events)
    assert not any(event.event_type == "breakout_triggered_original_pine" for event in events)


def test_entry_chaser_still_gtx_only() -> None:
    exchange = DryRunExchange()
    clock = ManualClock()
    run(MakerChaser(exchange, SymbolFilters.ethusdc_test_defaults(), logging.getLogger("test"), clock=clock.now, sleep=clock.sleep).chase_entry(signal_id="sig", side=Side.BUY, quantity=Decimal("1"), max_seconds=1))
    order = next(iter(exchange.orders.values()))
    assert order.order_type == OrderType.LIMIT
    assert order.time_in_force == TimeInForce.GTX


def test_no_stop_market_entry() -> None:
    assert not hasattr(OrderType, "STOP_MARKET")


def test_no_market_entry() -> None:
    exchange = DryRunExchange()
    with pytest.raises(ExchangeFilterFailure):
        run(
            exchange.place_limit_gtx(
                OrderRequest(
                    symbol="ETHUSDC",
                    side=Side.BUY,
                    order_type=OrderType.MARKET,
                    quantity=Decimal("1"),
                    time_in_force=TimeInForce.GTC,
                )
            )
        )


def test_stop_loss_rule_unchanged() -> None:
    exchange = DryRunExchange()
    clock = ManualClock()
    result = run(
        MakerChaser(exchange, SymbolFilters.ethusdc_test_defaults(), logging.getLogger("test"), clock=clock.now, sleep=clock.sleep).chase_stop(
            signal_id="stop",
            side=Side.SELL,
            quantity=Decimal("1"),
            max_seconds=1,
        )
    )
    market_order = exchange.orders[result.market_order_id]
    assert market_order.order_type == OrderType.MARKET
    assert market_order.reduce_only is True


def test_docs_original_pine_mentions_no_safer_close_gate() -> None:
    text = __import__("pathlib").Path("docs/trading_rules.md").read_text(encoding="utf-8")
    assert "original Pine" in text or "原版 Pine" in text
    assert "close <= hprice" in text
    assert "not used as an entry gate" in text or "不再" in text
