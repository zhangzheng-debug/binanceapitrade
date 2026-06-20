from decimal import Decimal

from bot.exchange_filters import SymbolFilters
from scripts.live_canary_order_control import (
    canary_quantity,
    hedge_cleanup_order_for_row,
    hedge_position_side_for_order_side,
    is_flat,
    net_position_amount,
    position_rows,
    side_safe_price,
)


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


def test_canary_buy_price_is_below_bid_and_aligned() -> None:
    price = side_safe_price("BUY", Decimal("1734.47"), Decimal("1734.48"), filters())
    assert price < Decimal("1734.47")
    assert price % Decimal("0.01") == 0


def test_canary_sell_price_is_above_ask_and_aligned() -> None:
    price = side_safe_price("SELL", Decimal("1734.47"), Decimal("1734.48"), filters())
    assert price > Decimal("1734.48")
    assert price % Decimal("0.01") == 0


def test_canary_quantity_meets_min_notional() -> None:
    f = filters()
    qty = canary_quantity(Decimal("1731.00"), f, Decimal("10"))
    assert qty * Decimal("1731.00") >= f.min_notional
    assert qty % f.step_size == 0


def test_position_rows_and_flat_detection() -> None:
    payload = [
        {"symbol": "ETHUSDC", "positionSide": "BOTH", "positionAmt": "0", "entryPrice": "0"},
        {"symbol": "BTCUSDC", "positionSide": "BOTH", "positionAmt": "1", "entryPrice": "1"},
    ]
    rows = position_rows(payload, "ETHUSDC")
    assert is_flat(rows)
    assert net_position_amount(rows) == Decimal("0")


def test_nonzero_position_is_not_flat() -> None:
    rows = position_rows([{"symbol": "ETHUSDC", "positionSide": "BOTH", "positionAmt": "-0.001", "entryPrice": "1"}], "ETHUSDC")
    assert not is_flat(rows)
    assert net_position_amount(rows) == Decimal("-0.001")


def test_hedge_position_side_mapping_for_control_orders() -> None:
    assert hedge_position_side_for_order_side("BUY") == "LONG"
    assert hedge_position_side_for_order_side("SELL") == "SHORT"


def test_hedge_cleanup_maps_long_and_short_rows_to_exact_closes() -> None:
    long_close = hedge_cleanup_order_for_row({"position_side": "LONG", "position_amt": "0.012"})
    short_close = hedge_cleanup_order_for_row({"position_side": "SHORT", "position_amt": "-0.034"})
    flat_close = hedge_cleanup_order_for_row({"position_side": "LONG", "position_amt": "0"})

    assert long_close == ("SELL", "LONG", Decimal("0.012"))
    assert short_close == ("BUY", "SHORT", Decimal("0.034"))
    assert flat_close is None
