from decimal import Decimal

from bot.models import OrderState, OrderStatus, OrderType, Position, PositionSide, Side
from bot.reconciliation import reconcile


def test_dry_run_reconciliation_ok_with_local_state() -> None:
    position = Position("ETHUSDC")
    report = reconcile(dry_run=True, local_position=position, exchange_position=None, open_orders=[])
    assert report.ok is True
    assert report.dry_run is True


def test_live_reconciliation_mismatch_blocks_startup() -> None:
    local = Position("ETHUSDC")
    exchange = Position("ETHUSDC", PositionSide.LONG, Decimal("1"), Decimal("3500"))
    report = reconcile(dry_run=False, local_position=local, exchange_position=exchange, open_orders=[])
    assert report.ok is False
    assert "mismatch" in report.message


def test_live_unknown_open_order_blocks_when_auto_cancel_disabled() -> None:
    local = Position("ETHUSDC")
    open_order = OrderState("ETHUSDC", Side.BUY, OrderType.LIMIT, Decimal("1"), status=OrderStatus.NEW)
    report = reconcile(
        dry_run=False,
        local_position=local,
        exchange_position=local,
        open_orders=[open_order],
        auto_cancel_unknown_orders=False,
    )
    assert report.ok is False
    assert report.unknown_open_orders == [open_order]

