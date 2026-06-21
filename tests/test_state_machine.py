from decimal import Decimal

import pytest

from bot.models import Position, PositionSide, StrategySignalSide
from bot.risk_manager import RiskError, RiskManager


def test_has_position_blocks_new_entry() -> None:
    risk = RiskManager(stop_loss_pct=Decimal("0.005"))
    with pytest.raises(RiskError):
        risk.assert_can_start_entry(
            Position("ETHUSDC", PositionSide.LONG, Decimal("1"), Decimal("3500")),
            active_entry=False,
            active_stop=False,
        )


def test_active_entry_or_stop_blocks_new_entry() -> None:
    risk = RiskManager(stop_loss_pct=Decimal("0.005"))
    flat = Position("ETHUSDC")
    with pytest.raises(RiskError):
        risk.assert_can_start_entry(flat, active_entry=True, active_stop=False)
    with pytest.raises(RiskError):
        risk.assert_can_start_entry(flat, active_entry=False, active_stop=True)


def test_opposite_signal_allowed_for_reversal_when_position_exists() -> None:
    risk = RiskManager(stop_loss_pct=Decimal("0.005"))
    risk.assert_signal_allowed(
        StrategySignalSide.SHORT,
        Position("ETHUSDC", PositionSide.LONG, Decimal("1"), Decimal("3500")),
    )


def test_same_side_signal_blocked_when_position_exists() -> None:
    risk = RiskManager(stop_loss_pct=Decimal("0.005"))
    with pytest.raises(RiskError):
        risk.assert_signal_allowed(
            StrategySignalSide.LONG,
            Position("ETHUSDC", PositionSide.LONG, Decimal("1"), Decimal("3500")),
        )


def test_stop_loss_trigger_for_long_and_short() -> None:
    risk = RiskManager(stop_loss_pct=Decimal("0.005"))
    assert risk.stop_triggered(Position("ETHUSDC", PositionSide.LONG, Decimal("1"), Decimal("3500")), Decimal("3482.50"))
    assert risk.stop_triggered(Position("ETHUSDC", PositionSide.SHORT, Decimal("1"), Decimal("3500")), Decimal("3517.50"))
