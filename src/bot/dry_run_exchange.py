from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal

from bot.models import (
    BookTicker,
    OrderRequest,
    OrderState,
    OrderStatus,
    OrderType,
    Position,
    Side,
    TimeInForce,
    new_id,
)


class ExchangeError(Exception):
    pass


class PostOnlyWouldTake(ExchangeError):
    pass


class OrderAlreadyFilled(ExchangeError):
    pass


class OrderCanceled(ExchangeError):
    pass


class OrderExpired(ExchangeError):
    pass


class InsufficientMargin(ExchangeError):
    pass


class TimestampDrift(ExchangeError):
    pass


class RateLimit(ExchangeError):
    pass


class NetworkTimeout(ExchangeError):
    pass


class ExchangeFilterFailure(ExchangeError):
    pass


class UnknownExchangeError(ExchangeError):
    pass


@dataclass(slots=True)
class DryRunExchange:
    symbol: str = "ETHUSDC"
    book_tickers: deque[BookTicker] = field(default_factory=deque)
    query_plan: deque[tuple[OrderStatus, Decimal]] = field(default_factory=deque)
    post_only_rejects_remaining: int = 0
    orders: dict[str, OrderState] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    position: Position = field(default_factory=lambda: Position(symbol="ETHUSDC"))

    def set_book_tickers(self, tickers: list[BookTicker]) -> None:
        self.book_tickers = deque(tickers)

    def set_query_plan(self, statuses: list[tuple[OrderStatus, Decimal]]) -> None:
        self.query_plan = deque(statuses)

    async def get_book_ticker(self, symbol: str) -> BookTicker:
        self.calls.append("get_book_ticker")
        if self.book_tickers:
            ticker = self.book_tickers[0]
            if len(self.book_tickers) > 1:
                self.book_tickers.popleft()
            return ticker
        return BookTicker(
            symbol=symbol,
            bid_price=Decimal("3500.00"),
            bid_qty=Decimal("10"),
            ask_price=Decimal("3500.01"),
            ask_qty=Decimal("10"),
        )

    async def place_limit_gtx(self, request: OrderRequest) -> OrderState:
        self.calls.append("would_place_order")
        if request.order_type != OrderType.LIMIT or request.time_in_force != TimeInForce.GTX:
            raise ExchangeFilterFailure("dry-run entry only accepts LIMIT GTX for this path")
        if self.post_only_rejects_remaining > 0:
            self.post_only_rejects_remaining -= 1
            raise PostOnlyWouldTake("dry-run post-only would take")
        order_id = new_id("dry_order")
        state = OrderState(
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            status=OrderStatus.NEW,
            time_in_force=request.time_in_force,
            reduce_only=request.reduce_only,
            position_side=request.position_side,
            order_id=order_id,
            client_order_id=request.client_order_id or new_id("dry_client"),
            raw_response_summary={"mode": "dry_run", "action": "would_place_order"},
        )
        self.orders[order_id] = state
        return state

    async def modify_order(self, order_id: str, side: Side, price: Decimal, quantity: Decimal) -> OrderState:
        self.calls.append("would_modify_order")
        if self.post_only_rejects_remaining > 0:
            self.post_only_rejects_remaining -= 1
            raise PostOnlyWouldTake("dry-run GTX modify would take")
        order = self.orders[order_id]
        if order.status == OrderStatus.FILLED:
            raise OrderAlreadyFilled(order_id)
        order.price = price
        order.quantity = quantity
        order.raw_response_summary = {"mode": "dry_run", "action": "would_modify_order"}
        return order

    async def cancel_order(self, order_id: str) -> OrderState:
        self.calls.append("would_cancel_order")
        order = self.orders[order_id]
        if order.status != OrderStatus.FILLED:
            order.status = OrderStatus.CANCELED
        order.raw_response_summary = {"mode": "dry_run", "action": "would_cancel_order"}
        return order

    async def query_order(self, order_id: str) -> OrderState:
        self.calls.append("query_order")
        order = self.orders[order_id]
        if self.query_plan:
            status, executed_qty = self.query_plan.popleft()
            order.status = status
            order.executed_qty = min(executed_qty, order.quantity)
            if order.executed_qty > 0 and order.avg_price is None:
                order.avg_price = order.price
        return order

    async def market_reduce_only(self, symbol: str, side: Side, quantity: Decimal) -> OrderState:
        self.calls.append("would_market_reduce_only")
        order_id = new_id("dry_market")
        state = OrderState(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            executed_qty=quantity,
            status=OrderStatus.FILLED,
            reduce_only=True,
            order_id=order_id,
            client_order_id=new_id("dry_market_client"),
            raw_response_summary={"mode": "dry_run", "action": "would_market_reduce_only"},
        )
        self.orders[order_id] = state
        return state

    async def get_open_orders(self, symbol: str) -> list[OrderState]:
        self.calls.append("get_open_orders")
        return [
            order
            for order in self.orders.values()
            if order.symbol == symbol and order.status in {OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED}
        ]

    async def get_position(self, symbol: str) -> Position:
        self.calls.append("get_position")
        return self.position
