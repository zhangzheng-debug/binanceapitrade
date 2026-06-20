from __future__ import annotations

from bot.models import OrderState, Position, ReconciliationReport


def reconcile(
    *,
    dry_run: bool,
    local_position: Position,
    exchange_position: Position | None,
    open_orders: list[OrderState],
    auto_cancel_unknown_orders: bool = False,
) -> ReconciliationReport:
    if dry_run:
        return ReconciliationReport(
            ok=True,
            dry_run=True,
            message="dry-run reconciliation uses local state only",
            local_position=local_position,
            exchange_position=local_position,
        )

    if exchange_position is None:
        return ReconciliationReport(
            ok=False,
            dry_run=False,
            message="live reconciliation failed: missing exchange position",
            local_position=local_position,
        )

    mismatch = (
        local_position.side != exchange_position.side
        or local_position.quantity != exchange_position.quantity
        or bool(open_orders and not auto_cancel_unknown_orders)
    )
    if mismatch:
        return ReconciliationReport(
            ok=False,
            dry_run=False,
            message="state mismatch; prefer exchange position and stop for manual review",
            local_position=local_position,
            exchange_position=exchange_position,
            unknown_open_orders=open_orders,
        )

    return ReconciliationReport(
        ok=True,
        dry_run=False,
        message="reconciliation ok",
        local_position=local_position,
        exchange_position=exchange_position,
    )

