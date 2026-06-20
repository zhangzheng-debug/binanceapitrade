import asyncio
import logging
from decimal import Decimal

from bot.dry_run_exchange import DryRunExchange
from bot.exchange_filters import SymbolFilters, maker_price
from bot.execution_maker_chaser import MakerChaser, ManualClock
from bot.models import BookTicker, OrderStatus, Side
from bot.risk_manager import RiskManager
from bot.models import Position, PositionSide


def run(coro):
    return asyncio.run(coro)


def make_chaser(exchange: DryRunExchange, clock: ManualClock) -> MakerChaser:
    return MakerChaser(
        exchange,
        SymbolFilters.ethusdc_test_defaults(),
        logging.getLogger("test"),
        clock=clock.now,
        sleep=clock.sleep,
    )


def test_stop_maker_success_does_not_market() -> None:
    exchange = DryRunExchange()
    exchange.set_query_plan([(OrderStatus.FILLED, Decimal("1"))])
    clock = ManualClock()
    result = run(make_chaser(exchange, clock).chase_stop(signal_id="stop1", side=Side.SELL, quantity=Decimal("1")))
    assert result.success is True
    assert result.market_order_id is None
    assert "would_market_reduce_only" not in exchange.calls


def test_stop_timeout_uses_market_reduce_only() -> None:
    exchange = DryRunExchange()
    clock = ManualClock()
    result = run(
        make_chaser(exchange, clock).chase_stop(
            signal_id="stop2",
            side=Side.SELL,
            quantity=Decimal("1"),
            max_seconds=30,
            interval_seconds=Decimal("1"),
        )
    )
    assert result.success is True
    assert result.reason == "market_reduce_only_fallback"
    assert result.market_order_id is not None
    assert "would_market_reduce_only" in exchange.calls
    market_order = exchange.orders[result.market_order_id]
    assert market_order.reduce_only is True
    assert market_order.quantity == Decimal("1")


def test_stop_partial_fill_markets_only_remaining() -> None:
    exchange = DryRunExchange()
    exchange.set_query_plan([(OrderStatus.PARTIALLY_FILLED, Decimal("0.4"))] * 100)
    clock = ManualClock()
    result = run(
        make_chaser(exchange, clock).chase_stop(
            signal_id="stop3",
            side=Side.SELL,
            quantity=Decimal("1"),
            max_seconds=2,
            interval_seconds=Decimal("1"),
        )
    )
    assert result.success is True
    market_order = exchange.orders[result.market_order_id]
    assert market_order.quantity == Decimal("0.6")


def test_stop_maker_price_rules_for_long_and_short_closes() -> None:
    filters = SymbolFilters.ethusdc_test_defaults()
    ticker = BookTicker("ETHUSDC", Decimal("3500.00"), Decimal("1"), Decimal("3500.05"), Decimal("1"))
    assert maker_price(Side.SELL, ticker, filters) > ticker.bid_price
    assert maker_price(Side.BUY, ticker, filters) < ticker.ask_price


def test_reduce_only_quantity_is_clamped_to_position() -> None:
    position = Position("ETHUSDC", PositionSide.LONG, Decimal("0.75"), Decimal("3500"))
    assert RiskManager.clamp_reduce_only_quantity(Decimal("1"), position) == Decimal("0.75")

