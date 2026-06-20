from decimal import Decimal

import pytest

from bot.exchange_filters import (
    ExchangeFilterError,
    SymbolFilters,
    assert_order_filters,
    quantize_price,
    quantize_quantity,
)
from bot.models import Side


def test_exchange_info_parser_uses_filters_not_precision() -> None:
    payload = {
        "symbols": [
            {
                "symbol": "ETHUSDC",
                "pricePrecision": 2,
                "quantityPrecision": 3,
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.05"},
                    {"filterType": "LOT_SIZE", "minQty": "0.010", "stepSize": "0.010"},
                    {"filterType": "MIN_NOTIONAL", "notional": "5.0"},
                ],
            }
        ]
    }
    filters = SymbolFilters.from_exchange_info(payload, "ETHUSDC")
    assert filters.tick_size == Decimal("0.05")
    assert filters.step_size == Decimal("0.010")


def test_price_quantization_decimal_floor_and_ceil() -> None:
    filters = SymbolFilters("ETHUSDC", Decimal("0.05"), Decimal("0.001"), Decimal("0.001"), Decimal("5"))
    assert quantize_price(Decimal("3500.079"), filters, side=Side.BUY) == Decimal("3500.05")
    assert quantize_price(Decimal("3500.071"), filters, side=Side.SELL) == Decimal("3500.10")


def test_quantity_quantization_and_min_qty_rejection() -> None:
    filters = SymbolFilters("ETHUSDC", Decimal("0.01"), Decimal("0.001"), Decimal("0.010"), Decimal("5"))
    assert quantize_quantity(Decimal("0.1239"), filters) == Decimal("0.123")
    with pytest.raises(ExchangeFilterError):
        assert_order_filters(Decimal("0.009"), Decimal("3500.00"), filters)


def test_notional_rejection() -> None:
    filters = SymbolFilters("ETHUSDC", Decimal("0.01"), Decimal("0.001"), Decimal("0.001"), Decimal("5"))
    with pytest.raises(ExchangeFilterError):
        assert_order_filters(Decimal("0.001"), Decimal("1000.00"), filters)

