from decimal import Decimal

import pytest

from bot.binance_client import BinanceClient, LiveTradingDisabled
from bot.config import Settings
from bot.dry_run_exchange import DryRunExchange
from bot.market_data import (
    LOCKED_STREAM_NAME,
    candle_from_kline_payload,
    kline_stream_name,
    kline_ws_url,
    process_kline_payload,
)
from bot.models import OrderRequest, OrderType, Side, TimeInForce


class DummyStrategy:
    def __init__(self) -> None:
        self.calls = 0

    def on_candle(self, candle) -> list:
        self.calls += 1
        return []


def kline_payload(closed: bool) -> dict:
    return {
        "stream": LOCKED_STREAM_NAME,
        "data": {
            "e": "kline",
            "s": "ETHUSDC",
            "k": {
                "t": 1,
                "T": 2,
                "s": "ETHUSDC",
                "i": "15m",
                "o": "3500.00",
                "h": "3510.00",
                "l": "3490.00",
                "c": "3505.00",
                "v": "12.5",
                "x": closed,
            },
        },
    }


def test_kline_closed_filter() -> None:
    strategy = DummyStrategy()
    assert process_kline_payload(kline_payload(False), strategy) is None
    assert strategy.calls == 0

    candle = process_kline_payload(kline_payload(True), strategy)
    assert candle is not None
    assert candle.close == Decimal("3505.00")
    assert strategy.calls == 1


def test_stream_name_is_ethusdc_kline_15m() -> None:
    assert kline_stream_name("ETHUSDC", "15m") == "ethusdc@kline_15m"
    assert kline_stream_name("ethusdc", "15m") == "ethusdc@kline_15m"


def test_stream_rejects_other_intervals() -> None:
    with pytest.raises(ValueError):
        kline_stream_name("ETHUSDC", "1m")


def test_ws_url_uses_market_routed_combined_stream() -> None:
    settings = Settings(BINANCE_INTERVAL="15m", _env_file=None)
    assert kline_ws_url(settings).endswith("/market/stream?streams=ethusdc@kline_15m")


def test_public_market_dry_run_cannot_place_real_order() -> None:
    settings = Settings(DRY_RUN=True, LIVE_TRADING=False, PUBLIC_MARKET_DRY_RUN=True, _env_file=None)
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

    exchange = DryRunExchange(symbol="ETHUSDC")
    assert exchange.symbol == "ETHUSDC"


def test_candle_from_kline_payload_ignores_unclosed() -> None:
    assert candle_from_kline_payload(kline_payload(False)) is None

