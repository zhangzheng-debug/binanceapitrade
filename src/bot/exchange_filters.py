from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from enum import Enum
from pathlib import Path

from bot.models import BookTicker, Side


class ExchangeFilterError(ValueError):
    """Raised when an order violates symbol trading filters."""


class FilterSource(str, Enum):
    EXCHANGE_INFO_REST = "EXCHANGE_INFO_REST"
    CACHED_DRY_RUN_ONLY = "CACHED_DRY_RUN_ONLY"
    MOCK_TEST = "MOCK_TEST"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SymbolFilters:
    symbol: str
    tick_size: Decimal
    step_size: Decimal
    min_qty: Decimal
    min_notional: Decimal
    market_step_size: Decimal | None = None
    market_min_qty: Decimal | None = None
    source: FilterSource = FilterSource.UNKNOWN
    safe_for_live: bool = False
    dry_run_only: bool = True
    note: str = ""

    @classmethod
    def from_exchange_info(cls, payload: dict, symbol: str) -> SymbolFilters:
        for item in payload.get("symbols", []):
            if item.get("symbol") == symbol:
                filters = {f["filterType"]: f for f in item.get("filters", [])}
                price_filter = filters.get("PRICE_FILTER", {})
                lot_filter = filters.get("LOT_SIZE", {})
                market_lot_filter = filters.get("MARKET_LOT_SIZE", {})
                min_notional_filter = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL") or {}
                notional = (
                    min_notional_filter.get("notional")
                    or min_notional_filter.get("minNotional")
                    or "0"
                )
                return cls(
                    symbol=symbol,
                    tick_size=Decimal(str(price_filter["tickSize"])),
                    step_size=Decimal(str(lot_filter["stepSize"])),
                    min_qty=Decimal(str(lot_filter["minQty"])),
                    min_notional=Decimal(str(notional)),
                    market_step_size=Decimal(str(market_lot_filter["stepSize"]))
                    if market_lot_filter.get("stepSize")
                    else None,
                    market_min_qty=Decimal(str(market_lot_filter["minQty"]))
                    if market_lot_filter.get("minQty")
                    else None,
                    source=FilterSource.EXCHANGE_INFO_REST,
                    safe_for_live=True,
                    dry_run_only=False,
                    note="fresh REST exchangeInfo",
                )
        raise ExchangeFilterError(f"symbol {symbol} not found in exchangeInfo")

    @classmethod
    def from_cached_payload(
        cls,
        payload: dict,
        symbol: str,
        *,
        live_trading: bool = False,
        testnet_order_test: bool = False,
    ) -> SymbolFilters:
        if live_trading:
            raise ExchangeFilterError("cached exchange filters are forbidden for live trading")
        if testnet_order_test:
            raise ExchangeFilterError("cached exchange filters are forbidden for testnet signed order tests by default")

        payload_symbol = str(payload.get("symbol", "")).upper()
        if payload_symbol != symbol.upper():
            raise ExchangeFilterError(f"cached filters symbol mismatch: {payload_symbol} != {symbol.upper()}")
        if payload.get("safe_for_live") is not False:
            raise ExchangeFilterError("cached filters must explicitly set safe_for_live=false")
        if payload.get("dry_run_only") is not True:
            raise ExchangeFilterError("cached filters must explicitly set dry_run_only=true")

        filters = payload.get("filters", {})
        price_filter = filters.get("PRICE_FILTER", {})
        lot_filter = filters.get("LOT_SIZE", {})
        market_lot_filter = filters.get("MARKET_LOT_SIZE", {})
        min_notional_filter = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL") or {}
        notional = min_notional_filter.get("notional") or min_notional_filter.get("minNotional") or "0"

        return cls(
            symbol=symbol.upper(),
            tick_size=Decimal(str(price_filter["tickSize"])),
            step_size=Decimal(str(lot_filter["stepSize"])),
            min_qty=Decimal(str(lot_filter["minQty"])),
            min_notional=Decimal(str(notional)),
            market_step_size=Decimal(str(market_lot_filter["stepSize"])) if market_lot_filter.get("stepSize") else None,
            market_min_qty=Decimal(str(market_lot_filter["minQty"])) if market_lot_filter.get("minQty") else None,
            source=FilterSource.CACHED_DRY_RUN_ONLY,
            safe_for_live=False,
            dry_run_only=True,
            note=str(payload.get("note", "cached dry-run only filters")),
        )

    @classmethod
    def from_cached_file(
        cls,
        path: Path | str,
        symbol: str,
        *,
        live_trading: bool = False,
        testnet_order_test: bool = False,
    ) -> SymbolFilters:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_cached_payload(
            payload,
            symbol,
            live_trading=live_trading,
            testnet_order_test=testnet_order_test,
        )

    @classmethod
    def ethusdc_test_defaults(cls) -> SymbolFilters:
        return cls(
            symbol="ETHUSDC",
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_qty=Decimal("0.001"),
            min_notional=Decimal("5"),
            source=FilterSource.MOCK_TEST,
            safe_for_live=False,
            dry_run_only=True,
            note="unit-test defaults only",
        )


def decimal_floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ExchangeFilterError("step must be positive")
    return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step


def decimal_ceil_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ExchangeFilterError("step must be positive")
    return (value / step).to_integral_value(rounding=ROUND_CEILING) * step


def quantize_price(value: Decimal, filters: SymbolFilters, *, side: Side) -> Decimal:
    if side == Side.BUY:
        return decimal_floor_to_step(value, filters.tick_size)
    return decimal_ceil_to_step(value, filters.tick_size)


def quantize_quantity(value: Decimal, filters: SymbolFilters, *, market: bool = False) -> Decimal:
    step = filters.market_step_size if market and filters.market_step_size else filters.step_size
    return decimal_floor_to_step(value, step)


def maker_price(side: Side, ticker: BookTicker, filters: SymbolFilters) -> Decimal:
    tick = filters.tick_size
    best_bid = decimal_floor_to_step(ticker.bid_price, tick)
    best_ask = decimal_ceil_to_step(ticker.ask_price, tick)
    if best_ask <= best_bid:
        raise ExchangeFilterError("invalid or crossed book")

    spread = best_ask - best_bid
    if side == Side.BUY:
        if spread <= tick:
            price = best_bid
        else:
            price = min(best_bid + tick, best_ask - tick)
        price = decimal_floor_to_step(price, tick)
        if price >= best_ask:
            raise ExchangeFilterError("BUY maker price would cross best ask")
        return price

    if spread <= tick:
        price = best_ask
    else:
        price = max(best_ask - tick, best_bid + tick)
    price = decimal_ceil_to_step(price, tick)
    if price <= best_bid:
        raise ExchangeFilterError("SELL maker price would cross best bid")
    return price


def assert_order_filters(quantity: Decimal, price: Decimal, filters: SymbolFilters) -> None:
    qty = quantize_quantity(quantity, filters)
    if qty != quantity:
        raise ExchangeFilterError(f"quantity {quantity} is not aligned to stepSize {filters.step_size}")
    if quantity < filters.min_qty:
        raise ExchangeFilterError(f"quantity {quantity} is below minQty {filters.min_qty}")
    notional = quantity * price
    if notional < filters.min_notional:
        raise ExchangeFilterError(f"notional {notional} is below minNotional {filters.min_notional}")
