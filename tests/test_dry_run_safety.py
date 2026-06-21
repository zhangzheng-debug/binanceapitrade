from decimal import Decimal

import pytest

from bot.binance_client import BinanceClient, LiveTradingDisabled
from bot.config import ConfigError, Settings, load_settings
from bot.models import OrderRequest, OrderType, Side, TimeInForce


def test_dry_run_binance_client_refuses_real_order() -> None:
    settings = Settings(DRY_RUN=True, LIVE_TRADING=False)
    client = BinanceClient(settings)
    request = OrderRequest(
        symbol="ETHUSDC",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1"),
        price=Decimal("3500"),
        time_in_force=TimeInForce.GTX,
    )
    with pytest.raises(LiveTradingDisabled):
        import asyncio

        asyncio.run(client.place_limit_gtx(request))


def test_live_trading_without_api_key_rejected(monkeypatch) -> None:
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("LIVE_TRADING", "true")
    monkeypatch.setenv("BINANCE_API_KEY", "")
    monkeypatch.setenv("BINANCE_API_SECRET", "")
    with pytest.raises(ConfigError):
        load_settings()


def test_live_and_dry_run_cannot_both_be_true(monkeypatch) -> None:
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("LIVE_TRADING", "true")
    monkeypatch.setenv("BINANCE_API_KEY", "x")
    monkeypatch.setenv("BINANCE_API_SECRET", "y")
    with pytest.raises(ConfigError):
        load_settings()


def test_env_example_empty_optional_decimals_are_allowed(monkeypatch) -> None:
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("ORDER_MODE", "fixed_notional")
    monkeypatch.setenv("FIXED_QTY", "")
    monkeypatch.setenv("FIXED_NOTIONAL", "100")
    monkeypatch.setenv("TAKE_PROFIT_ENABLED", "false")
    monkeypatch.setenv("TAKE_PROFIT_PCT", "")
    settings = load_settings()
    assert settings.fixed_qty is None
    assert settings.fixed_notional == Decimal("100")
    assert settings.take_profit_pct is None


def test_account_equity_pct_position_size_defaults_to_100(monkeypatch) -> None:
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("PUBLIC_MARKET_DRY_RUN", "false")
    monkeypatch.setenv("PUBLIC_MARKET_WS_ONLY", "false")
    monkeypatch.setenv("EXIT_AFTER_BOUNDED_RUNTIME", "false")
    monkeypatch.setenv("PHASE_FAST_SMOKE_SECONDS", "0")
    monkeypatch.setenv("ORDER_MODE", "account_equity_pct")
    settings = load_settings()
    assert settings.order_mode == "account_equity_pct"
    assert settings.position_size_pct == Decimal("100")


def test_live_strategy_entry_fill_limit_defaults_to_one() -> None:
    settings = Settings(_env_file=None)
    assert settings.live_strategy_max_entry_fills == 1
    assert settings.safe_summary()["live_strategy_max_entry_fills"] == 1


def test_live_strategy_entry_fill_limit_accepts_zero_for_unlimited() -> None:
    settings = Settings(LIVE_STRATEGY_MAX_ENTRY_FILLS="0", _env_file=None)
    assert settings.live_strategy_max_entry_fills == 0
    assert settings.safe_summary()["live_strategy_max_entry_fills"] == 0


def test_account_equity_pct_position_size_rejects_above_200(monkeypatch) -> None:
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("PUBLIC_MARKET_DRY_RUN", "false")
    monkeypatch.setenv("PUBLIC_MARKET_WS_ONLY", "false")
    monkeypatch.setenv("EXIT_AFTER_BOUNDED_RUNTIME", "false")
    monkeypatch.setenv("PHASE_FAST_SMOKE_SECONDS", "0")
    monkeypatch.setenv("ORDER_MODE", "account_equity_pct")
    monkeypatch.setenv("POSITION_SIZE_PCT", "201")
    with pytest.raises(ConfigError):
        load_settings()
