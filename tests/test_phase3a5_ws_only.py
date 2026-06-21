import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from bot.binance_client import BinanceClient, LiveTradingDisabled
from bot.book_ticker_provider import BookTickerUnavailable, StaticBookTickerProvider
from bot.book_ticker_stream import (
    LOCKED_BOOK_TICKER_ROUTED_PATH,
    LOCKED_BOOK_TICKER_STREAM_NAME,
    book_ticker_stream_name,
    book_ticker_ws_url,
    snapshot_from_book_ticker_payload,
)
from bot.config import ConfigError, Settings
from bot.dry_run_exchange import DryRunExchange, ExchangeFilterFailure
from bot.exchange_filters import FilterSource, SymbolFilters, maker_price
from bot.execution_maker_chaser import MakerChaser, ManualClock
from bot.market_data import LOCKED_STREAM_NAME, candle_from_kline_payload, kline_stream_name, kline_ws_url, process_kline_payload
from bot.models import BookTicker, BookTickerSnapshot, OrderRequest, OrderType, Side, TimeInForce
from bot.safety import (
    LiveTradingRejected,
    assert_live_ready_or_raise,
    assert_public_ws_only_dry_run_safe,
    redact_secret,
)
from scripts.diagnose_binance_connectivity import (
    assert_public_only_targets,
    classify_http_status,
    rest_targets,
)
from scripts.scan_secrets import scan_text


def run(coro):
    return asyncio.run(coro)


def snapshot(*, bid: str = "3500.00", ask: str = "3500.05", received_at: datetime | None = None) -> BookTickerSnapshot:
    return BookTickerSnapshot(
        symbol="ETHUSDC",
        best_bid_price=Decimal(bid),
        best_bid_qty=Decimal("1"),
        best_ask_price=Decimal(ask),
        best_ask_qty=Decimal("1"),
        event_time=1,
        received_at=received_at or datetime.now(tz=UTC),
        source="websocket",
    )


def make_payload(symbol: str = "ETHUSDC", bid: str = "3500.00", ask: str = "3500.05") -> dict:
    return {
        "stream": LOCKED_BOOK_TICKER_STREAM_NAME,
        "data": {"e": "bookTicker", "E": 1, "s": symbol, "b": bid, "B": "1", "a": ask, "A": "1"},
    }


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


class DummyStrategy:
    def __init__(self) -> None:
        self.calls = 0

    def on_candle(self, candle) -> list:
        self.calls += 1
        return []


def cached_payload() -> dict:
    return {
        "source": "manual_example_not_for_live",
        "symbol": "ETHUSDC",
        "safe_for_live": False,
        "dry_run_only": True,
        "note": "Dry-run only. Must be replaced by fresh exchangeInfo before testnet/live.",
        "filters": {
            "PRICE_FILTER": {"tickSize": "0.01"},
            "LOT_SIZE": {"stepSize": "0.001", "minQty": "0.001"},
            "MIN_NOTIONAL": {"notional": "5"},
        },
    }


def test_http_451_classified() -> None:
    classification, action = classify_http_status(451, "unavailable")
    assert classification == "rest_451_blocked_no_bypass"
    assert action == "stop_no_testnet_no_live"


def test_diagnosis_never_uses_signed_endpoint() -> None:
    targets = rest_targets()
    assert_public_only_targets(targets)
    assert all(target.method == "GET" for target in targets)
    assert not any("/order" in target.path or "/positionRisk" in target.path for target in targets)


def test_ws_bookticker_parse() -> None:
    parsed = snapshot_from_book_ticker_payload(make_payload())
    assert parsed.symbol == "ETHUSDC"
    assert parsed.best_bid_price == Decimal("3500.00")
    assert parsed.best_ask_price == Decimal("3500.05")


def test_ws_bookticker_rejects_bad_symbol() -> None:
    with pytest.raises(ValueError):
        Settings(BINANCE_SYMBOL="ETHUSDT", _env_file=None)


def test_ws_bookticker_rejects_crossed_book() -> None:
    with pytest.raises(ValueError):
        snapshot_from_book_ticker_payload(make_payload(bid="3500.05", ask="3500.05"))


def test_ws_bookticker_provider_waits_for_first() -> None:
    provider = StaticBookTickerProvider(None)
    with pytest.raises(BookTickerUnavailable):
        run(provider.wait_for_first("ETHUSDC", 0.01))


def test_ws_bookticker_provider_stale_snapshot() -> None:
    stale = snapshot(received_at=datetime.now(tz=UTC) - timedelta(seconds=10))
    provider = StaticBookTickerProvider(stale, stale_seconds=5)
    assert run(provider.get_latest("ETHUSDC")) is None


def test_entry_chaser_requires_bookticker() -> None:
    exchange = DryRunExchange()
    clock = ManualClock()
    chaser = MakerChaser(
        exchange,
        SymbolFilters.ethusdc_test_defaults(),
        logging.getLogger("test"),
        book_ticker_provider=StaticBookTickerProvider(None),
        clock=clock.now,
        sleep=clock.sleep,
    )
    result = run(chaser.chase_entry(signal_id="sig-wait", side=Side.BUY, quantity=Decimal("1")))
    assert result.success is False
    assert result.reason == "book_ticker_unavailable"
    assert "would_place_order" not in exchange.calls


def test_entry_chaser_uses_ws_bookticker_buy() -> None:
    exchange = DryRunExchange()
    clock = ManualClock()
    chaser = MakerChaser(
        exchange,
        SymbolFilters.ethusdc_test_defaults(),
        logging.getLogger("test"),
        book_ticker_provider=StaticBookTickerProvider(snapshot()),
        clock=clock.now,
        sleep=clock.sleep,
    )
    run(chaser.chase_entry(signal_id="sig-buy", side=Side.BUY, quantity=Decimal("1"), max_seconds=1))
    placed = next(order for order in exchange.orders.values() if order.order_type == OrderType.LIMIT)
    assert placed.price == Decimal("3500.01")
    assert placed.price < Decimal("3500.05")


def test_entry_chaser_uses_ws_bookticker_sell() -> None:
    exchange = DryRunExchange()
    clock = ManualClock()
    chaser = MakerChaser(
        exchange,
        SymbolFilters.ethusdc_test_defaults(),
        logging.getLogger("test"),
        book_ticker_provider=StaticBookTickerProvider(snapshot()),
        clock=clock.now,
        sleep=clock.sleep,
    )
    run(chaser.chase_entry(signal_id="sig-sell", side=Side.SELL, quantity=Decimal("1"), max_seconds=1))
    placed = next(order for order in exchange.orders.values() if order.order_type == OrderType.LIMIT)
    assert placed.price == Decimal("3500.04")
    assert placed.price > Decimal("3500.00")


def test_spread_one_tick_buy_sell() -> None:
    filters = SymbolFilters.ethusdc_test_defaults()
    ticker = BookTicker("ETHUSDC", Decimal("3500.00"), Decimal("1"), Decimal("3500.01"), Decimal("1"))
    assert maker_price(Side.BUY, ticker, filters) == Decimal("3500.00")
    assert maker_price(Side.SELL, ticker, filters) == Decimal("3500.01")


def test_cached_filters_allowed_only_dry_run() -> None:
    filters = SymbolFilters.from_cached_payload(cached_payload(), "ETHUSDC")
    assert filters.source == FilterSource.CACHED_DRY_RUN_ONLY
    assert filters.dry_run_only is True
    assert filters.safe_for_live is False


def test_cached_filters_rejected_live() -> None:
    with pytest.raises(Exception):
        SymbolFilters.from_cached_payload(cached_payload(), "ETHUSDC", live_trading=True)


def test_cached_filters_rejected_testnet_signed_by_default() -> None:
    with pytest.raises(Exception):
        SymbolFilters.from_cached_payload(cached_payload(), "ETHUSDC", testnet_order_test=True)


def test_rest_exchangeinfo_451_dry_run_uses_cached_filters() -> None:
    classification, _ = classify_http_status(451)
    filters = SymbolFilters.from_cached_payload(cached_payload(), "ETHUSDC")
    assert classification == "rest_451_blocked_no_bypass"
    assert filters.source == FilterSource.CACHED_DRY_RUN_ONLY


def test_rest_exchangeinfo_451_live_rejects_startup() -> None:
    settings = Settings(DRY_RUN=False, LIVE_TRADING=True, BINANCE_API_KEY="key", BINANCE_API_SECRET="secret", _env_file=None)
    with pytest.raises(LiveTradingRejected):
        assert_live_ready_or_raise(settings, None, {"exchange_info_rest_ok": False, "signed_rest_validated": False})


def test_public_ws_only_never_calls_signed_order() -> None:
    settings = Settings(DRY_RUN=True, LIVE_TRADING=False, PUBLIC_MARKET_DRY_RUN=True, PUBLIC_MARKET_WS_ONLY=True, _env_file=None)
    client = BinanceClient(settings)
    with pytest.raises(LiveTradingDisabled):
        run(client.query_order("1"))


def test_safety_redacts_secret() -> None:
    secret = "abcdefghijklmnopqrstuvwxyz"
    assert redact_secret(secret) != secret
    assert secret not in redact_secret(secret)


def test_scan_secrets_does_not_echo_raw_secret() -> None:
    secret = "abcdefghijklmnop1234567890secret"
    findings = scan_text(__import__("pathlib").Path("fake.env"), f"BINANCE_API_KEY={secret}\n")
    assert findings
    assert findings[0].redacted_value != secret
    assert secret not in findings[0].redacted_value


def test_config_public_ws_only_safe() -> None:
    settings = Settings(DRY_RUN=True, LIVE_TRADING=False, PUBLIC_MARKET_DRY_RUN=True, PUBLIC_MARKET_WS_ONLY=True, _env_file=None)
    assert_public_ws_only_dry_run_safe(settings)


def test_config_public_ws_only_live_rejected() -> None:
    with pytest.raises(Exception):
        Settings(
            DRY_RUN=False,
            LIVE_TRADING=True,
            PUBLIC_MARKET_DRY_RUN=True,
            PUBLIC_MARKET_WS_ONLY=True,
            BINANCE_API_KEY="key",
            BINANCE_API_SECRET="secret",
            _env_file=None,
        )


def test_combined_stream_names() -> None:
    assert LOCKED_STREAM_NAME == "ethusdc@kline_15m"
    assert book_ticker_stream_name("ETHUSDC") == "ethusdc@bookTicker"
    assert kline_stream_name("BTCUSDC", "1h") == "btcusdc@kline_1h"
    assert book_ticker_stream_name("BTCUSDC") == "btcusdc@bookTicker"
    assert kline_stream_name("XRPUSDC", "1h") == "xrpusdc@kline_1h"
    assert book_ticker_stream_name("XRPUSDC") == "xrpusdc@bookTicker"


def test_combined_routed_paths() -> None:
    settings = Settings(BINANCE_ENV="mainnet", _env_file=None)
    btc_settings = Settings(BINANCE_ENV="mainnet", BINANCE_SYMBOL="BTCUSDC", BINANCE_INTERVAL="1h", _env_file=None)
    xrp_settings = Settings(BINANCE_ENV="mainnet", BINANCE_SYMBOL="XRPUSDC", BINANCE_INTERVAL="1h", _env_file=None)
    assert "/market/stream?streams=ethusdc@kline_15m" in kline_ws_url(settings)
    assert "/market/stream?streams=btcusdc@kline_1h" in kline_ws_url(btc_settings)
    assert "/market/stream?streams=xrpusdc@kline_1h" in kline_ws_url(xrp_settings)
    assert LOCKED_BOOK_TICKER_ROUTED_PATH == "/public"
    assert "/public/stream?streams=ethusdc@bookTicker" in book_ticker_ws_url(settings)
    assert "/public/stream?streams=btcusdc@bookTicker" in book_ticker_ws_url(btc_settings)
    assert "/public/stream?streams=xrpusdc@bookTicker" in book_ticker_ws_url(xrp_settings)


def test_kline_unclosed_ignored_still() -> None:
    strategy = DummyStrategy()
    assert process_kline_payload(kline_payload(False), strategy) is None
    assert strategy.calls == 0


def test_kline_closed_updates_strategy() -> None:
    strategy = DummyStrategy()
    assert candle_from_kline_payload(kline_payload(True)) is not None
    assert process_kline_payload(kline_payload(True), strategy) is not None
    assert strategy.calls == 1


def test_no_market_entry_still() -> None:
    exchange = DryRunExchange()
    request = OrderRequest(
        symbol="ETHUSDC",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
        time_in_force=TimeInForce.GTC,
    )
    with pytest.raises(ExchangeFilterFailure):
        run(exchange.place_limit_gtx(request))


def test_stop_fallback_market_reduce_only_only() -> None:
    exchange = DryRunExchange()
    clock = ManualClock()
    chaser = MakerChaser(exchange, SymbolFilters.ethusdc_test_defaults(), logging.getLogger("test"), clock=clock.now, sleep=clock.sleep)
    result = run(chaser.chase_stop(signal_id="stop-reduce", side=Side.SELL, quantity=Decimal("1"), max_seconds=1))
    market_order = exchange.orders[result.market_order_id]
    assert market_order.order_type == OrderType.MARKET
    assert market_order.reduce_only is True


def test_live_trading_requires_rest_exchangeinfo() -> None:
    settings = Settings(DRY_RUN=False, LIVE_TRADING=True, BINANCE_API_KEY="key", BINANCE_API_SECRET="secret", _env_file=None)
    filters = SymbolFilters.from_exchange_info(
        {"symbols": [{"symbol": "ETHUSDC", "filters": [{"filterType": "PRICE_FILTER", "tickSize": "0.01"}, {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"}, {"filterType": "MIN_NOTIONAL", "notional": "5"}]}]},
        "ETHUSDC",
    )
    with pytest.raises(LiveTradingRejected):
        assert_live_ready_or_raise(settings, filters, {"exchange_info_rest_ok": False, "signed_rest_validated": True})


def test_documentation_mentions_rest_451_gate() -> None:
    text = __import__("pathlib").Path("docs/risk_rules.md").read_text(encoding="utf-8")
    assert "REST 451" in text
    assert "testnet" in text.lower()
    assert "live" in text.lower()
