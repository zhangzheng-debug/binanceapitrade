from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bot.logging_config import log_event
from bot.models import OrderStatus


def utc_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def current_max_memory_mb() -> float | None:
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KB; macOS reports bytes. This project runs server-side on Linux.
        return round(float(usage) / 1024.0, 2)
    except Exception:
        return None


@dataclass(slots=True)
class Phase3BRuntimeSummary:
    started_at: str = field(default_factory=utc_iso)
    stopped_at: str | None = None
    runtime_seconds: float = 0.0
    kline_ws_connected_count: int = 0
    kline_ws_reconnect_count: int = 0
    bookticker_ws_connected_count: int = 0
    bookticker_ws_reconnect_count: int = 0
    kline_unclosed_count: int = 0
    kline_closed_count: int = 0
    bookticker_update_count: int = 0
    bookticker_stale_count: int = 0
    strategy_update_count: int = 0
    pivot_high_confirmed_count: int = 0
    pivot_low_confirmed_count: int = 0
    long_armed_count: int = 0
    short_armed_count: int = 0
    pending_long_stop_created_count: int = 0
    pending_short_stop_created_count: int = 0
    pending_long_stop_updated_count: int = 0
    pending_short_stop_updated_count: int = 0
    pending_long_stop_invalidated_count: int = 0
    pending_short_stop_invalidated_count: int = 0
    pine_stop_trigger_detected_count: int = 0
    ambiguous_dual_trigger_skipped_count: int = 0
    trigger_blocked_active_chase_count: int = 0
    ignored_due_to_position_count: int = 0
    missed_long_trigger_on_closed_candle_count: int = 0
    missed_short_trigger_on_closed_candle_count: int = 0
    breakout_triggered_count: int = 0
    entry_chase_started_count: int = 0
    simulated_entry_order_count: int = 0
    simulated_stop_order_count: int = 0
    signed_order_blocked_count: int = 0
    real_order_attempt_count: int = 0
    api_error_count: int = 0
    active_simulated_orders_cancelled_count: int = 0
    max_memory_mb: float | None = None
    bid_ask_sample: dict[str, str] | None = None
    maker_price_sample: dict[str, str] | None = None
    final_status: str = "running"

    def record_strategy_event(self, event_type: str) -> None:
        if event_type == "pivot_high_confirmed":
            self.pivot_high_confirmed_count += 1
        elif event_type == "pivot_low_confirmed":
            self.pivot_low_confirmed_count += 1
        elif event_type == "long_armed":
            self.long_armed_count += 1
        elif event_type == "short_armed":
            self.short_armed_count += 1
        elif event_type == "pending_long_stop_created":
            self.pending_long_stop_created_count += 1
        elif event_type == "pending_short_stop_created":
            self.pending_short_stop_created_count += 1
        elif event_type == "pending_long_stop_updated":
            self.pending_long_stop_updated_count += 1
        elif event_type == "pending_short_stop_updated":
            self.pending_short_stop_updated_count += 1
        elif event_type == "pending_long_stop_invalidated":
            self.pending_long_stop_invalidated_count += 1
        elif event_type == "pending_short_stop_invalidated":
            self.pending_short_stop_invalidated_count += 1
        elif event_type == "pine_stop_trigger_detected":
            self.pine_stop_trigger_detected_count += 1
        elif event_type == "ambiguous_dual_trigger_skipped":
            self.ambiguous_dual_trigger_skipped_count += 1
        elif event_type == "trigger_blocked_active_chase":
            self.trigger_blocked_active_chase_count += 1
        elif event_type == "ignored_due_to_position":
            self.ignored_due_to_position_count += 1
        elif event_type == "missed_long_trigger_on_closed_candle":
            self.missed_long_trigger_on_closed_candle_count += 1
        elif event_type == "missed_short_trigger_on_closed_candle":
            self.missed_short_trigger_on_closed_candle_count += 1
        elif event_type in {"breakout_triggered", "breakout_triggered_original_pine"}:
            self.breakout_triggered_count += 1
        elif event_type == "entry_chase_started":
            self.entry_chase_started_count += 1

    def finish(self, *, final_status: str) -> dict[str, Any]:
        stopped = datetime.now(tz=UTC)
        started = datetime.fromisoformat(self.started_at)
        self.stopped_at = stopped.isoformat()
        self.runtime_seconds = round((stopped - started).total_seconds(), 3)
        self.max_memory_mb = current_max_memory_mb()
        self.final_status = final_status
        return asdict(self)


def write_runtime_summary(summary: Phase3BRuntimeSummary, path: Path | str, *, final_status: str) -> dict[str, Any]:
    payload = summary.finish(final_status=final_status)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


async def cancel_active_simulated_orders(exchange, logger, summary: Phase3BRuntimeSummary, symbol: str) -> None:
    for order in list(await exchange.get_open_orders(symbol)):
        if order.status in {OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED} and order.order_id:
            await exchange.cancel_order(order.order_id)
            summary.active_simulated_orders_cancelled_count += 1
            log_event(
                logger,
                "simulated_order_cancelled_on_shutdown",
                order_id=order.order_id,
                status=order.status.value,
            )
