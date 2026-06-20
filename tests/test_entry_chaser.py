import asyncio
import logging
from decimal import Decimal

import pytest

from bot.dry_run_exchange import DryRunExchange
from bot.exchange_filters import SymbolFilters
from bot.execution_maker_chaser import MakerChaser, ManualClock
from bot.models import BookTicker, OrderStatus, Side


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


def test_entry_60_second_timeout_cancels_and_never_markets() -> None:
    exchange = DryRunExchange()
    clock = ManualClock()
    result = run(
        make_chaser(exchange, clock).chase_entry(
            signal_id="sig1",
            side=Side.BUY,
            quantity=Decimal("1"),
            max_seconds=60,
            interval_seconds=Decimal("1"),
        )
    )
    assert result.success is False
    assert result.reason == "timeout_no_fill"
    assert "would_cancel_order" in exchange.calls
    assert "would_market_reduce_only" not in exchange.calls


def test_entry_partial_fill_below_accept_ratio_chases_until_timeout() -> None:
    exchange = DryRunExchange()
    exchange.set_query_plan([(OrderStatus.PARTIALLY_FILLED, Decimal("0.50"))] * 100)
    clock = ManualClock()
    result = run(
        make_chaser(exchange, clock).chase_entry(
            signal_id="sig2",
            side=Side.BUY,
            quantity=Decimal("1"),
            max_seconds=3,
            interval_seconds=Decimal("1"),
            partial_accept_ratio=Decimal("0.95"),
        )
    )
    assert result.success is True
    assert result.filled_qty == Decimal("0.50")
    assert result.reason == "partial_after_timeout"
    assert "would_cancel_order" in exchange.calls


def test_entry_partial_fill_at_accept_ratio_cancels_remainder() -> None:
    exchange = DryRunExchange()
    exchange.set_query_plan([(OrderStatus.PARTIALLY_FILLED, Decimal("0.95"))])
    clock = ManualClock()
    result = run(
        make_chaser(exchange, clock).chase_entry(
            signal_id="sig3",
            side=Side.BUY,
            quantity=Decimal("1"),
            max_seconds=60,
            interval_seconds=Decimal("1"),
            partial_accept_ratio=Decimal("0.95"),
        )
    )
    assert result.success is True
    assert result.reason == "partial_fill_accepted"
    assert "would_cancel_order" in exchange.calls


def test_entry_post_only_would_take_retries_without_market() -> None:
    exchange = DryRunExchange(post_only_rejects_remaining=2)
    exchange.set_query_plan([(OrderStatus.FILLED, Decimal("1"))])
    exchange.set_book_tickers(
        [
            BookTicker("ETHUSDC", Decimal("3500.00"), Decimal("1"), Decimal("3500.01"), Decimal("1")),
            BookTicker("ETHUSDC", Decimal("3500.01"), Decimal("1"), Decimal("3500.02"), Decimal("1")),
            BookTicker("ETHUSDC", Decimal("3500.02"), Decimal("1"), Decimal("3500.03"), Decimal("1")),
        ]
    )
    clock = ManualClock()
    result = run(
        make_chaser(exchange, clock).chase_entry(
            signal_id="sig4",
            side=Side.BUY,
            quantity=Decimal("1"),
            max_seconds=60,
            interval_seconds=Decimal("1"),
        )
    )
    assert result.success is True
    assert result.filled_qty == Decimal("1")
    assert exchange.calls.count("would_place_order") == 3
    assert "would_market_reduce_only" not in exchange.calls


def test_entry_cancellation_cancels_active_limit_order() -> None:
    exchange = DryRunExchange()
    clock = ManualClock()

    async def cancel_sleep(seconds: float) -> None:
        clock.value += seconds
        raise asyncio.CancelledError

    chaser = MakerChaser(
        exchange,
        SymbolFilters.ethusdc_test_defaults(),
        logging.getLogger("test"),
        clock=clock.now,
        sleep=cancel_sleep,
    )

    with pytest.raises(asyncio.CancelledError):
        run(chaser.chase_entry(signal_id="sig-cancel", side=Side.BUY, quantity=Decimal("1")))

    assert "would_place_order" in exchange.calls
    assert "would_cancel_order" in exchange.calls
