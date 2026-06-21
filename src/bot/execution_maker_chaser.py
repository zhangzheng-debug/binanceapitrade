from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Protocol

from bot.alerts import AlertManager
from bot.book_ticker_provider import BookTickerProvider, BookTickerUnavailable
from bot.dry_run_exchange import PostOnlyWouldTake
from bot.exchange_filters import SymbolFilters, maker_price, quantize_quantity
from bot.logging_config import log_event
from bot.models import (
    ChaseResult,
    ChaseType,
    OrderRequest,
    OrderState,
    OrderStatus,
    OrderType,
    Side,
    TimeInForce,
    new_id,
)


class ChaserExchange(Protocol):
    async def get_book_ticker(self, symbol: str): ...
    async def place_limit_gtx(self, request: OrderRequest) -> OrderState: ...
    async def modify_order(self, order_id: str, side: Side, price: Decimal, quantity: Decimal) -> OrderState: ...
    async def cancel_order(self, order_id: str) -> OrderState: ...
    async def query_order(self, order_id: str) -> OrderState: ...
    async def market_reduce_only(self, symbol: str, side: Side, quantity: Decimal) -> OrderState: ...


class ManualClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    async def sleep(self, seconds: float) -> None:
        self.value += seconds


class MakerChaser:
    def __init__(
        self,
        exchange: ChaserExchange,
        filters: SymbolFilters,
        logger,
        *,
        alerts: AlertManager | None = None,
        book_ticker_provider: BookTickerProvider | None = None,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.exchange = exchange
        self.filters = filters
        self.logger = logger
        self.alerts = alerts or AlertManager(enabled=False)
        self.book_ticker_provider = book_ticker_provider
        self.clock = clock or time.monotonic
        self.sleep = sleep or asyncio.sleep

    async def chase_entry(
        self,
        *,
        signal_id: str,
        side: Side,
        quantity: Decimal,
        max_seconds: int = 60,
        interval_seconds: Decimal = Decimal("1"),
        partial_accept_ratio: Decimal = Decimal("0.95"),
    ) -> ChaseResult:
        return await self._chase(
            chase_type=ChaseType.ENTRY,
            signal_id=signal_id,
            side=side,
            quantity=quantity,
            max_seconds=max_seconds,
            interval_seconds=interval_seconds,
            partial_accept_ratio=partial_accept_ratio,
            reduce_only=False,
            market_fallback=False,
        )

    async def chase_stop(
        self,
        *,
        signal_id: str,
        side: Side,
        quantity: Decimal,
        max_seconds: int = 30,
        interval_seconds: Decimal = Decimal("1"),
    ) -> ChaseResult:
        return await self._chase(
            chase_type=ChaseType.STOP,
            signal_id=signal_id,
            side=side,
            quantity=quantity,
            max_seconds=max_seconds,
            interval_seconds=interval_seconds,
            partial_accept_ratio=Decimal("1"),
            reduce_only=True,
            market_fallback=True,
        )

    async def chase_reduce_only(
        self,
        *,
        signal_id: str,
        side: Side,
        quantity: Decimal,
        max_seconds: int = 60,
        interval_seconds: Decimal = Decimal("1"),
    ) -> ChaseResult:
        return await self._chase(
            chase_type=ChaseType.CLOSE,
            signal_id=signal_id,
            side=side,
            quantity=quantity,
            max_seconds=max_seconds,
            interval_seconds=interval_seconds,
            partial_accept_ratio=Decimal("1"),
            reduce_only=True,
            market_fallback=False,
        )

    async def _chase(
        self,
        *,
        chase_type: ChaseType,
        signal_id: str,
        side: Side,
        quantity: Decimal,
        max_seconds: int,
        interval_seconds: Decimal,
        partial_accept_ratio: Decimal,
        reduce_only: bool,
        market_fallback: bool,
    ) -> ChaseResult:
        requested_qty = quantize_quantity(quantity, self.filters)
        start = self.clock()
        order: OrderState | None = None
        last_order_id: str | None = None

        try:
            first_ticker = await self._fresh_book_ticker()
        except BookTickerUnavailable as exc:
            log_event(
                self.logger,
                "would_wait_for_book_ticker",
                signal_id=signal_id,
                chase_type=chase_type.value,
                reason=str(exc),
            )
            return ChaseResult(
                chase_type,
                signal_id,
                False,
                Decimal("0"),
                None,
                reason="book_ticker_unavailable",
            )

        log_event(
            self.logger,
            f"{chase_type.value.lower()}_chase_started",
            signal_id=signal_id,
            side=side.value,
            qty=str(requested_qty),
        )

        try:
            while self.clock() - start < max_seconds:
                if order is None:
                    ticker = first_ticker
                else:
                    try:
                        ticker = await self._fresh_book_ticker()
                    except BookTickerUnavailable as exc:
                        log_event(
                            self.logger,
                            "book_ticker_stale",
                            signal_id=signal_id,
                            chase_type=chase_type.value,
                            reason=str(exc),
                        )
                        break
                price = maker_price(side, ticker, self.filters)
                try:
                    if order is None or order.status in {OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED}:
                        order = await self.exchange.place_limit_gtx(
                            OrderRequest(
                                symbol=self.filters.symbol,
                                side=side,
                                order_type=OrderType.LIMIT,
                                quantity=requested_qty,
                                price=price,
                                time_in_force=TimeInForce.GTX,
                                reduce_only=reduce_only,
                                client_order_id=new_id("client"),
                            )
                        )
                        last_order_id = order.order_id
                        log_event(self.logger, f"{chase_type.value.lower()}_order_placed", signal_id=signal_id, price=str(price))
                    else:
                        await self.exchange.modify_order(order.order_id or "", side, price, requested_qty)
                        log_event(self.logger, f"{chase_type.value.lower()}_order_modified", signal_id=signal_id, price=str(price))
                except PostOnlyWouldTake:
                    log_event(
                        self.logger,
                        f"{chase_type.value.lower()}_order_rejected_post_only",
                        signal_id=signal_id,
                        side=side.value,
                    )
                    await self.sleep(float(interval_seconds))
                    continue

                order = await self.exchange.query_order(order.order_id or "")
                if order.status == OrderStatus.FILLED:
                    log_event(self.logger, f"{chase_type.value.lower()}_order_filled", signal_id=signal_id, qty=str(order.executed_qty))
                    await self.alerts.alert("order filled", "order filled", signal_id=signal_id, chase_type=chase_type.value)
                    return ChaseResult(
                        chase_type,
                        signal_id,
                        True,
                        order.executed_qty,
                        order.status,
                        order.order_id,
                        avg_price=order.avg_price or order.price,
                    )
                if order.status == OrderStatus.PARTIALLY_FILLED:
                    log_event(
                        self.logger,
                        f"{chase_type.value.lower()}_order_partially_filled",
                        signal_id=signal_id,
                        qty=str(order.executed_qty),
                        ratio=str(order.fill_ratio),
                    )
                    if not market_fallback and order.fill_ratio >= partial_accept_ratio:
                        await self.exchange.cancel_order(order.order_id or "")
                        return ChaseResult(
                            chase_type,
                            signal_id,
                            True,
                            order.executed_qty,
                            order.status,
                            order.order_id,
                            reason="partial_fill_accepted",
                            avg_price=order.avg_price or order.price,
                        )

                await self.sleep(float(interval_seconds))
        except asyncio.CancelledError:
            if order and order.status not in {OrderStatus.FILLED, OrderStatus.CANCELED}:
                await self.exchange.cancel_order(order.order_id or "")
                log_event(self.logger, f"{chase_type.value.lower()}_order_cancelled_on_shutdown", signal_id=signal_id, order_id=order.order_id)
            raise

        filled_qty = order.executed_qty if order else Decimal("0")
        if order and order.status not in {OrderStatus.FILLED, OrderStatus.CANCELED}:
            await self.exchange.cancel_order(order.order_id or "")
            log_event(self.logger, f"{chase_type.value.lower()}_order_cancelled", signal_id=signal_id, order_id=order.order_id)

        log_event(self.logger, f"{chase_type.value.lower()}_chase_timeout", signal_id=signal_id, filled_qty=str(filled_qty))

        if market_fallback:
            remaining = requested_qty - filled_qty
            if remaining > 0:
                market_order = await self.exchange.market_reduce_only(self.filters.symbol, side, remaining)
                log_event(
                    self.logger,
                    "stop_fallback_market",
                    signal_id=signal_id,
                    qty=str(remaining),
                    market_order_id=market_order.order_id,
                )
                await self.alerts.alert("market stop used", "market reduceOnly fallback used", signal_id=signal_id)
                return ChaseResult(
                    chase_type,
                    signal_id,
                    True,
                    requested_qty,
                    market_order.status,
                    last_order_id,
                    market_order.order_id,
                    reason="market_reduce_only_fallback",
                    avg_price=market_order.avg_price or market_order.price,
                )

        if filled_qty > 0:
            return ChaseResult(
                chase_type,
                signal_id,
                True,
                filled_qty,
                order.status if order else None,
                last_order_id,
                reason="partial_after_timeout",
                avg_price=order.avg_price or order.price if order else None,
            )
        return ChaseResult(
            chase_type,
            signal_id,
            False,
            Decimal("0"),
            order.status if order else None,
            last_order_id,
            reason="timeout_no_fill",
        )

    async def _fresh_book_ticker(self):
        if self.book_ticker_provider is None:
            return await self.exchange.get_book_ticker(self.filters.symbol)
        snapshot = await self.book_ticker_provider.get_latest(self.filters.symbol)
        if snapshot is None:
            raise BookTickerUnavailable("fresh bookTicker snapshot is unavailable")
        return snapshot.to_book_ticker()
