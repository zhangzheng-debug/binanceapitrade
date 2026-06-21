from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from bot.execution_maker_chaser import ChaserExchange, MakerChaser
from bot.exchange_filters import SymbolFilters
from bot.config import SUPPORTED_INTERVALS, SUPPORTED_SYMBOLS
from bot.models import ChaseResult, Position, PositionSide, Side, StrategyEvent, StrategySignalSide
from bot.position_sizing import PositionSize, account_equity_pct_size
from bot.risk_manager import RiskManager
from bot.safety import LiveTradingRejected

FINAL_LIVE_APPROVAL_ENV = "I_APPROVE_FINAL_LIVE_STRATEGY_START"
EXPECTED_FINAL_LIVE_APPROVAL = "YES"


@dataclass(frozen=True, slots=True)
class LiveEntryCanaryResult:
    signal_id: str
    side: str
    account_equity: str
    position_size_pct: str
    target_notional: str
    quantity: str
    actual_notional: str
    chase_success: bool
    chase_reason: str
    order_id: str | None
    filled_qty: str
    avg_price: str | None


@dataclass(frozen=True, slots=True)
class LiveStopResult:
    signal_id: str
    side: str
    requested_qty: str
    chase_success: bool
    chase_reason: str
    order_id: str | None
    market_order_id: str | None
    filled_qty: str


def final_live_strategy_start_approved(environ: dict[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return env.get(FINAL_LIVE_APPROVAL_ENV) == EXPECTED_FINAL_LIVE_APPROVAL


def require_final_live_strategy_start_approval(environ: dict[str, str] | None = None) -> None:
    if not final_live_strategy_start_approved(environ):
        raise LiveTradingRejected(f"missing {FINAL_LIVE_APPROVAL_ENV}=YES")


def _require_live_entry_canary_settings(settings: Any) -> None:
    if not getattr(settings, "live_trading", False):
        raise LiveTradingRejected("LIVE_TRADING=true is required for live entry canary")
    if getattr(settings, "dry_run", True):
        raise LiveTradingRejected("live entry canary cannot run with DRY_RUN=true")
    if getattr(settings, "public_market_dry_run", False) or getattr(settings, "public_market_ws_only", False):
        raise LiveTradingRejected("public market dry-run modes cannot be used for live entry canary")
    if getattr(settings, "order_mode", "") != "account_equity_pct":
        raise LiveTradingRejected("live entry canary requires ORDER_MODE=account_equity_pct")
    if getattr(settings, "binance_symbol", "") not in SUPPORTED_SYMBOLS:
        raise LiveTradingRejected("live entry canary symbol is not supported")
    if getattr(settings, "binance_interval", "") not in SUPPORTED_INTERVALS:
        raise LiveTradingRejected("live entry canary interval is not supported")


def account_equity_from_account_payload(payload: dict[str, Any], preferred_asset: str = "USDC") -> Decimal:
    preferred_asset = preferred_asset.upper()
    for asset in payload.get("assets", []):
        if str(asset.get("asset", "")).upper() != preferred_asset:
            continue
        for key in ("marginBalance", "walletBalance", "availableBalance"):
            value = Decimal(str(asset.get(key, "0")))
            if value > 0:
                return value
    for key in ("totalMarginBalance", "totalWalletBalance", "availableBalance"):
        value = Decimal(str(payload.get(key, "0")))
        if value > 0:
            return value
    raise LiveTradingRejected("positive account equity was not found in futures account payload")


def _side_from_event(event: StrategyEvent) -> Side:
    if event.signal_id is None or event.price is None or event.side is None:
        raise LiveTradingRejected("live entry canary requires a complete strategy trigger event")
    if event.side == StrategySignalSide.LONG:
        return Side.BUY
    if event.side == StrategySignalSide.SHORT:
        return Side.SELL
    raise LiveTradingRejected(f"unsupported strategy side {event.side}")


def _stop_side_from_position(position: Position) -> Side:
    if position.side == PositionSide.LONG:
        return Side.SELL
    if position.side == PositionSide.SHORT:
        return Side.BUY
    raise LiveTradingRejected("live stop requires an open position")


async def run_live_entry_canary_once(
    *,
    settings: Any,
    exchange: ChaserExchange,
    filters: SymbolFilters,
    account_equity: Decimal,
    event: StrategyEvent,
    logger: logging.Logger | None = None,
) -> LiveEntryCanaryResult:
    _require_live_entry_canary_settings(settings)
    side = _side_from_event(event)
    size: PositionSize = account_equity_pct_size(
        account_equity=account_equity,
        position_size_pct=settings.position_size_pct,
        price=event.price or Decimal("0"),
        filters=filters,
    )
    chaser = MakerChaser(exchange, filters, logger or logging.getLogger("bot.live_strategy_runner"))
    chase: ChaseResult = await chaser.chase_entry(
        signal_id=event.signal_id or "",
        side=side,
        quantity=size.quantity,
        max_seconds=settings.entry_chase_seconds,
        interval_seconds=settings.chase_interval_seconds,
        partial_accept_ratio=settings.partial_fill_accept_ratio,
    )
    return LiveEntryCanaryResult(
        signal_id=event.signal_id or "",
        side=side.value,
        account_equity=str(account_equity),
        position_size_pct=str(settings.position_size_pct),
        target_notional=str(size.target_notional),
        quantity=str(size.quantity),
        actual_notional=str(size.actual_notional),
        chase_success=chase.success,
        chase_reason=chase.reason,
        order_id=chase.order_id,
        filled_qty=str(chase.filled_qty),
        avg_price=str(chase.avg_price) if chase.avg_price is not None else None,
    )


def live_entry_canary_result_dict(result: LiveEntryCanaryResult) -> dict[str, Any]:
    return asdict(result)


async def run_live_stop_once(
    *,
    settings: Any,
    exchange: ChaserExchange,
    filters: SymbolFilters,
    position: Position,
    signal_id: str,
    logger: logging.Logger | None = None,
    clock: Callable[[], float] | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> LiveStopResult:
    _require_live_entry_canary_settings(settings)
    side = _stop_side_from_position(position)
    quantity = RiskManager.clamp_reduce_only_quantity(position.quantity, position)
    if quantity <= 0:
        raise LiveTradingRejected("live stop quantity is zero")
    chaser = MakerChaser(
        exchange,
        filters,
        logger or logging.getLogger("bot.live_strategy_runner"),
        clock=clock,
        sleep=sleep,
    )
    chase: ChaseResult = await chaser.chase_stop(
        signal_id=signal_id,
        side=side,
        quantity=quantity,
        max_seconds=settings.stop_chase_seconds,
        interval_seconds=settings.chase_interval_seconds,
    )
    return LiveStopResult(
        signal_id=signal_id,
        side=side.value,
        requested_qty=str(quantity),
        chase_success=chase.success,
        chase_reason=chase.reason,
        order_id=chase.order_id,
        market_order_id=chase.market_order_id,
        filled_qty=str(chase.filled_qty),
    )


async def run_live_reduce_only_close_once(
    *,
    settings: Any,
    exchange: ChaserExchange,
    filters: SymbolFilters,
    position: Position,
    signal_id: str,
    logger: logging.Logger | None = None,
) -> LiveStopResult:
    _require_live_entry_canary_settings(settings)
    side = _stop_side_from_position(position)
    quantity = RiskManager.clamp_reduce_only_quantity(position.quantity, position)
    if quantity <= 0:
        raise LiveTradingRejected("live close quantity is zero")
    chaser = MakerChaser(exchange, filters, logger or logging.getLogger("bot.live_strategy_runner"))
    chase: ChaseResult = await chaser.chase_reduce_only(
        signal_id=signal_id,
        side=side,
        quantity=quantity,
        max_seconds=settings.entry_chase_seconds,
        interval_seconds=settings.chase_interval_seconds,
    )
    return LiveStopResult(
        signal_id=signal_id,
        side=side.value,
        requested_qty=str(quantity),
        chase_success=chase.success,
        chase_reason=chase.reason,
        order_id=chase.order_id,
        market_order_id=chase.market_order_id,
        filled_qty=str(chase.filled_qty),
    )


def live_stop_result_dict(result: LiveStopResult) -> dict[str, Any]:
    return asdict(result)
