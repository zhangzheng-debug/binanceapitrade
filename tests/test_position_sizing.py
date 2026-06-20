from decimal import Decimal

import pytest

from bot.exchange_filters import SymbolFilters
from bot.position_sizing import PositionSizingError, account_equity_pct_size


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


def test_account_equity_pct_size_uses_200_pct_and_floor_quantizes() -> None:
    size = account_equity_pct_size(
        account_equity=Decimal("123.45"),
        position_size_pct=Decimal("200"),
        price=Decimal("3456.78"),
        filters=filters(),
    )

    assert size.target_notional == Decimal("246.90")
    assert size.quantity == Decimal("0.071")
    assert size.actual_notional == Decimal("245.43138")
    assert size.actual_notional <= size.target_notional


def test_account_equity_pct_size_rejects_above_200() -> None:
    with pytest.raises(PositionSizingError, match="must not exceed 200"):
        account_equity_pct_size(
            account_equity=Decimal("100"),
            position_size_pct=Decimal("201"),
            price=Decimal("3000"),
            filters=filters(),
        )


def test_account_equity_pct_size_rejects_below_min_notional_without_upsizing() -> None:
    with pytest.raises(PositionSizingError, match="below minNotional"):
        account_equity_pct_size(
            account_equity=Decimal("5"),
            position_size_pct=Decimal("200"),
            price=Decimal("3000"),
            filters=filters(),
        )
