import asyncio
import logging

import pytest

from bot.config import Settings
from bot.live_strategy_runner import FINAL_LIVE_APPROVAL_ENV
from bot.main import live_entry_fill_limit_reached, run_live_strategy
from bot.safety import LiveTradingRejected


def test_live_strategy_rejects_without_final_human_approval(monkeypatch) -> None:
    monkeypatch.delenv(FINAL_LIVE_APPROVAL_ENV, raising=False)
    settings = Settings(
        DRY_RUN=False,
        LIVE_TRADING=True,
        BINANCE_ENV="mainnet",
        BINANCE_API_KEY="key",
        BINANCE_API_SECRET="secret",
        ORDER_MODE="account_equity_pct",
        POSITION_SIZE_PCT="100",
        _env_file=None,
    )

    with pytest.raises(LiveTradingRejected, match=FINAL_LIVE_APPROVAL_ENV):
        asyncio.run(run_live_strategy(settings, logging.getLogger("test")))


def test_live_entry_fill_limit_zero_means_unlimited() -> None:
    assert live_entry_fill_limit_reached(1, 1) is True
    assert live_entry_fill_limit_reached(2, 1) is False
    assert live_entry_fill_limit_reached(0, 999) is False
