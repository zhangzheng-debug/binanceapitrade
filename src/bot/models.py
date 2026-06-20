from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class PositionSide(str, Enum):
    NONE = "NONE"
    LONG = "LONG"
    SHORT = "SHORT"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class TimeInForce(str, Enum):
    GTX = "GTX"
    GTC = "GTC"


class OrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class ChaseType(str, Enum):
    ENTRY = "ENTRY"
    STOP = "STOP"


class StrategySignalSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class PendingTriggerSide(str, Enum):
    LONG_TRIGGER = "LONG_TRIGGER"
    SHORT_TRIGGER = "SHORT_TRIGGER"


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"


@dataclass(slots=True)
class Candle:
    open_time: int
    close_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")
    closed: bool = True


@dataclass(slots=True)
class BookTicker:
    symbol: str
    bid_price: Decimal
    bid_qty: Decimal
    ask_price: Decimal
    ask_qty: Decimal
    event_time: int | None = None


@dataclass(slots=True)
class BookTickerSnapshot:
    symbol: str
    best_bid_price: Decimal
    best_bid_qty: Decimal
    best_ask_price: Decimal
    best_ask_qty: Decimal
    event_time: int | None
    received_at: datetime
    source: str = "websocket"

    def __post_init__(self) -> None:
        self.symbol = self.symbol.upper()
        if self.symbol != "ETHUSDC":
            raise ValueError("bookTicker snapshot must be for ETHUSDC")
        if self.best_bid_price <= 0 or self.best_ask_price <= 0:
            raise ValueError("bookTicker bid/ask prices must be positive")
        if self.best_bid_qty < 0 or self.best_ask_qty < 0:
            raise ValueError("bookTicker bid/ask quantities must be nonnegative")
        if self.best_bid_price >= self.best_ask_price:
            raise ValueError("bookTicker bid must be lower than ask")

    def to_book_ticker(self) -> BookTicker:
        return BookTicker(
            symbol=self.symbol,
            bid_price=self.best_bid_price,
            bid_qty=self.best_bid_qty,
            ask_price=self.best_ask_price,
            ask_qty=self.best_ask_qty,
            event_time=self.event_time,
        )


@dataclass(slots=True)
class OrderRequest:
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    time_in_force: TimeInForce | None = None
    reduce_only: bool = False
    position_side: PositionSide | None = None
    client_order_id: str | None = None


@dataclass(slots=True)
class OrderState:
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    executed_qty: Decimal = Decimal("0")
    price: Decimal | None = None
    avg_price: Decimal | None = None
    status: OrderStatus = OrderStatus.NEW
    time_in_force: TimeInForce | None = None
    reduce_only: bool = False
    position_side: PositionSide | None = None
    order_id: str | None = None
    client_order_id: str | None = None
    raw_response_summary: dict[str, str] = field(default_factory=dict)

    @property
    def remaining_qty(self) -> Decimal:
        remaining = self.quantity - self.executed_qty
        return remaining if remaining > 0 else Decimal("0")

    @property
    def fill_ratio(self) -> Decimal:
        if self.quantity <= 0:
            return Decimal("0")
        return self.executed_qty / self.quantity


@dataclass(slots=True)
class Position:
    symbol: str
    side: PositionSide = PositionSide.NONE
    quantity: Decimal = Decimal("0")
    entry_price: Decimal | None = None

    @property
    def is_flat(self) -> bool:
        return self.side == PositionSide.NONE or self.quantity <= 0


@dataclass(slots=True)
class PendingStopTrigger:
    signal_id: str
    side: PendingTriggerSide
    pine_entry_id: str
    pivot_price: Decimal
    trigger_price: Decimal
    created_from_closed_candle_time: int
    created_at: datetime = field(default_factory=utc_now)
    active: bool = True
    triggered: bool = False
    trigger_detected_at: datetime | None = None
    trigger_source: str | None = None
    invalidated_at: datetime | None = None
    invalidation_reason: str | None = None


@dataclass(slots=True)
class StrategyState:
    hprice: Decimal | None = None
    lprice: Decimal | None = None
    le: bool = False
    se: bool = False
    last_closed_candle_time: int | None = None
    armed_long: bool = False
    armed_short: bool = False
    active_long_stop_price: Decimal | None = None
    active_short_stop_price: Decimal | None = None
    pending_long_trigger: PendingStopTrigger | None = None
    pending_short_trigger: PendingStopTrigger | None = None
    current_signal_id: str | None = None
    current_position_side: PositionSide = PositionSide.NONE
    current_position_qty: Decimal = Decimal("0")
    active_entry_order_id: str | None = None
    active_stop_order_id: str | None = None
    active_chase_type: ChaseType | None = None
    active_chase_started_at: datetime | None = None


@dataclass(slots=True)
class StrategyEvent:
    event_type: str
    signal_id: str | None = None
    price: Decimal | None = None
    candle_time: int | None = None
    side: StrategySignalSide | None = None


@dataclass(slots=True)
class ChaseResult:
    chase_type: ChaseType
    signal_id: str
    success: bool
    filled_qty: Decimal
    final_status: OrderStatus | None
    order_id: str | None = None
    market_order_id: str | None = None
    reason: str = ""
    avg_price: Decimal | None = None


@dataclass(slots=True)
class ReconciliationReport:
    ok: bool
    dry_run: bool
    message: str
    exchange_position: Position | None = None
    local_position: Position | None = None
    unknown_open_orders: list[OrderState] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
