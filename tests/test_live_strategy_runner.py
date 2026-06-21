import asyncio
from decimal import Decimal

import pytest

from bot.config import Settings
from bot.dry_run_exchange import DryRunExchange
from bot.execution_maker_chaser import ManualClock
from bot.exchange_filters import SymbolFilters
from bot.live_strategy_runner import (
    FINAL_LIVE_APPROVAL_ENV,
    account_equity_from_account_payload,
    require_final_live_strategy_start_approval,
    run_live_entry_canary_once,
    run_live_stop_once,
)
from bot.models import BookTicker, OrderStatus, Position, PositionSide, StrategyEvent, StrategySignalSide
from bot.safety import LiveTradingRejected


def live_settings(**overrides):
    values = {
        "DRY_RUN": False,
        "LIVE_TRADING": True,
        "PUBLIC_MARKET_DRY_RUN": False,
        "PUBLIC_MARKET_WS_ONLY": False,
        "BINANCE_ENV": "mainnet",
        "BINANCE_API_KEY": "key",
        "BINANCE_API_SECRET": "secret",
        "ORDER_MODE": "account_equity_pct",
        "POSITION_SIZE_PCT": "100",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def filters() -> SymbolFilters:
    return SymbolFilters(
        symbol="ETHUSDC",
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        min_notional=Decimal("20"),
        safe_for_live=True,
        dry_run_only=False,
    )


def trigger_event() -> StrategyEvent:
    return StrategyEvent(
        event_type="breakout_triggered_original_pine",
        signal_id="sig-live-canary",
        price=Decimal("3000"),
        candle_time=1,
        side=StrategySignalSide.LONG,
    )


def test_live_entry_canary_uses_100_pct_sizing_and_maker_chaser() -> None:
    exchange = DryRunExchange()
    exchange.set_book_tickers([BookTicker("ETHUSDC", Decimal("3000.00"), Decimal("1"), Decimal("3000.01"), Decimal("1"))])
    exchange.set_query_plan([(OrderStatus.FILLED, Decimal("0.066"))])
    result = asyncio.run(
        run_live_entry_canary_once(
            settings=live_settings(),
            exchange=exchange,
            filters=filters(),
            account_equity=Decimal("100"),
            event=trigger_event(),
        )
    )
    order = next(iter(exchange.orders.values()))

    assert result.target_notional == "100"
    assert result.quantity == "0.033"
    assert result.actual_notional == "99.000"
    assert result.chase_success is True
    assert Decimal(result.avg_price or "0") == Decimal("3000")
    assert order.time_in_force.value == "GTX"
    assert order.reduce_only is False
    assert "would_market_reduce_only" not in exchange.calls


def test_live_entry_canary_rejects_non_live_settings() -> None:
    with pytest.raises(LiveTradingRejected, match="LIVE_TRADING"):
        asyncio.run(
            run_live_entry_canary_once(
                settings=live_settings(DRY_RUN=True, LIVE_TRADING=False),
                exchange=DryRunExchange(),
                filters=filters(),
                account_equity=Decimal("100"),
                event=trigger_event(),
            )
        )


def test_live_entry_canary_rejects_non_account_equity_mode() -> None:
    with pytest.raises(LiveTradingRejected, match="account_equity_pct"):
        asyncio.run(
            run_live_entry_canary_once(
                settings=live_settings(ORDER_MODE="fixed_notional"),
                exchange=DryRunExchange(),
                filters=filters(),
                account_equity=Decimal("100"),
                event=trigger_event(),
            )
        )


def test_live_entry_canary_requires_complete_trigger_event() -> None:
    with pytest.raises(LiveTradingRejected, match="complete strategy trigger"):
        asyncio.run(
            run_live_entry_canary_once(
                settings=live_settings(),
                exchange=DryRunExchange(),
                filters=filters(),
                account_equity=Decimal("100"),
                event=StrategyEvent(event_type="breakout_triggered_original_pine"),
            )
        )


def test_account_equity_prefers_usdc_asset_balance() -> None:
    payload = {
        "totalMarginBalance": "999",
        "assets": [
            {"asset": "USDT", "marginBalance": "50"},
            {"asset": "USDC", "marginBalance": "123.45", "walletBalance": "120"},
        ],
    }

    assert account_equity_from_account_payload(payload) == Decimal("123.45")


def test_account_equity_falls_back_to_total_margin_balance() -> None:
    assert account_equity_from_account_payload({"totalMarginBalance": "88.5", "assets": []}) == Decimal("88.5")


def test_final_live_approval_guard_requires_exact_yes() -> None:
    with pytest.raises(LiveTradingRejected, match=FINAL_LIVE_APPROVAL_ENV):
        require_final_live_strategy_start_approval({})
    require_final_live_strategy_start_approval({FINAL_LIVE_APPROVAL_ENV: "YES"})


def test_live_stop_uses_maker_then_market_reduce_only_fallback() -> None:
    exchange = DryRunExchange()
    clock = ManualClock()
    result = asyncio.run(
        run_live_stop_once(
            settings=live_settings(),
            exchange=exchange,
            filters=filters(),
            position=Position("ETHUSDC", PositionSide.LONG, Decimal("0.01"), Decimal("3000")),
            signal_id="stop-live",
            clock=clock.now,
            sleep=clock.sleep,
        )
    )

    assert result.chase_success is True
    assert result.side == "SELL"
    assert result.market_order_id is not None
    assert "would_market_reduce_only" in exchange.calls
