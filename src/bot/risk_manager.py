from __future__ import annotations

from decimal import Decimal

from bot.models import Position, PositionSide, StrategySignalSide


class RiskError(ValueError):
    """Raised when a trade would violate risk constraints."""


class RiskManager:
    def __init__(self, stop_loss_pct: Decimal, stop_loss_enabled: bool = True) -> None:
        self.stop_loss_pct = stop_loss_pct
        self.stop_loss_enabled = stop_loss_enabled

    def assert_can_start_entry(self, position: Position, active_entry: bool, active_stop: bool) -> None:
        if not position.is_flat:
            raise RiskError("new entry is blocked while a position is open")
        if active_entry:
            raise RiskError("new entry is blocked while another entry chase is active")
        if active_stop:
            raise RiskError("new entry is blocked while a stop chase is active")

    def assert_signal_allowed(self, signal_side: StrategySignalSide, position: Position) -> None:
        if position.is_flat:
            return
        if position.side == PositionSide.LONG and signal_side == StrategySignalSide.SHORT:
            raise RiskError("short entry is blocked while long position exists")
        if position.side == PositionSide.SHORT and signal_side == StrategySignalSide.LONG:
            raise RiskError("long entry is blocked while short position exists")
        raise RiskError("adding to an existing position is blocked")

    def stop_triggered(self, position: Position, last_price: Decimal) -> bool:
        if not self.stop_loss_enabled or position.entry_price is None or position.is_flat:
            return False
        if position.side == PositionSide.LONG:
            return last_price <= position.entry_price * (Decimal("1") - self.stop_loss_pct)
        if position.side == PositionSide.SHORT:
            return last_price >= position.entry_price * (Decimal("1") + self.stop_loss_pct)
        return False

    @staticmethod
    def clamp_reduce_only_quantity(requested: Decimal, position: Position) -> Decimal:
        if requested <= 0 or position.quantity <= 0:
            return Decimal("0")
        return min(requested, position.quantity)

