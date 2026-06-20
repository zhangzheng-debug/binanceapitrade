from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from bot.exchange_filters import SymbolFilters, decimal_floor_to_step


class PositionSizingError(ValueError):
    """Raised when configured sizing cannot produce a valid exchange order."""


@dataclass(frozen=True, slots=True)
class PositionSize:
    account_equity: Decimal
    position_size_pct: Decimal
    target_notional: Decimal
    price: Decimal
    quantity: Decimal
    actual_notional: Decimal


def account_equity_pct_size(
    *,
    account_equity: Decimal,
    position_size_pct: Decimal,
    price: Decimal,
    filters: SymbolFilters,
) -> PositionSize:
    if account_equity <= 0:
        raise PositionSizingError("account equity must be greater than zero")
    if position_size_pct <= 0:
        raise PositionSizingError("position size percent must be greater than zero")
    if position_size_pct > Decimal("200"):
        raise PositionSizingError("position size percent must not exceed 200")
    if price <= 0:
        raise PositionSizingError("price must be greater than zero")

    target_notional = account_equity * position_size_pct / Decimal("100")
    raw_quantity = target_notional / price
    quantity = decimal_floor_to_step(raw_quantity, filters.step_size)
    actual_notional = quantity * price

    if quantity <= 0 or quantity < filters.min_qty:
        raise PositionSizingError(f"quantity {quantity} is below minQty {filters.min_qty}")
    if actual_notional < filters.min_notional:
        raise PositionSizingError(f"notional {actual_notional} is below minNotional {filters.min_notional}")

    return PositionSize(
        account_equity=account_equity,
        position_size_pct=position_size_pct,
        target_notional=target_notional,
        price=price,
        quantity=quantity,
        actual_notional=actual_notional,
    )
