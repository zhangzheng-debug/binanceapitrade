from decimal import Decimal

from bot.exchange_filters import SymbolFilters, maker_price
from bot.models import BookTicker, Side


def filters() -> SymbolFilters:
    return SymbolFilters("ETHUSDC", Decimal("0.01"), Decimal("0.001"), Decimal("0.001"), Decimal("5"))


def test_buy_maker_price_one_tick_spread() -> None:
    price = maker_price(
        Side.BUY,
        BookTicker("ETHUSDC", Decimal("3500.00"), Decimal("1"), Decimal("3500.01"), Decimal("1")),
        filters(),
    )
    assert price == Decimal("3500.00")
    assert price < Decimal("3500.01")


def test_sell_maker_price_one_tick_spread() -> None:
    price = maker_price(
        Side.SELL,
        BookTicker("ETHUSDC", Decimal("3500.00"), Decimal("1"), Decimal("3500.01"), Decimal("1")),
        filters(),
    )
    assert price == Decimal("3500.01")
    assert price > Decimal("3500.00")


def test_wide_spread_maker_prices_do_not_cross() -> None:
    ticker = BookTicker("ETHUSDC", Decimal("3500.00"), Decimal("1"), Decimal("3500.05"), Decimal("1"))
    buy_price = maker_price(Side.BUY, ticker, filters())
    sell_price = maker_price(Side.SELL, ticker, filters())
    assert buy_price == Decimal("3500.01")
    assert sell_price == Decimal("3500.04")
    assert buy_price < ticker.ask_price
    assert sell_price > ticker.bid_price

