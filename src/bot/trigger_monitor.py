from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from bot.models import PendingStopTrigger, StrategyEvent, StrategySignalSide
from bot.strategy_pivot import PivotReversalStrategy


@dataclass(slots=True)
class LivePriceUpdate:
    symbol: str
    event_time: int | None = None
    latest_price: Decimal | None = None
    high_so_far: Decimal | None = None
    low_so_far: Decimal | None = None
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    source: str = "unknown"


class TriggerMonitor:
    def __init__(self, strategy: PivotReversalStrategy, *, tie_break_mode: str = "skip_ambiguous") -> None:
        self.strategy = strategy
        self.tie_break_mode = tie_break_mode

    def on_live_price_update(
        self,
        update: LivePriceUpdate,
        *,
        active_entry_chase: bool = False,
        has_open_position: bool = False,
        open_position_side: StrategySignalSide | None = None,
    ) -> list[StrategyEvent]:
        long_trigger = self.strategy.state.pending_long_trigger
        short_trigger = self.strategy.state.pending_short_trigger
        long_hit = self._long_hit(long_trigger, update)
        short_hit = self._short_hit(short_trigger, update)

        if not long_hit and not short_hit:
            return []

        if long_hit and short_hit:
            return [StrategyEvent("ambiguous_dual_trigger_skipped", candle_time=update.event_time)]

        side = StrategySignalSide.LONG if long_hit else StrategySignalSide.SHORT
        trigger = long_trigger if long_hit else short_trigger
        if trigger is None:
            return []

        if active_entry_chase:
            return [
                StrategyEvent(
                    "trigger_blocked_active_chase",
                    trigger.signal_id,
                    trigger.trigger_price,
                    update.event_time,
                    side,
                )
            ]

        if open_position_side == side:
            return [
                StrategyEvent(
                    "same_side_trigger_ignored_position_open",
                    trigger.signal_id,
                    trigger.trigger_price,
                    update.event_time,
                    side,
                )
            ]

        if has_open_position and open_position_side is None:
            return [
                StrategyEvent(
                    "ignored_due_to_position",
                    trigger.signal_id,
                    trigger.trigger_price,
                    update.event_time,
                    side,
                )
            ]

        self.strategy.mark_triggered(trigger, update.source)
        events = [
            StrategyEvent("pine_stop_trigger_detected", trigger.signal_id, trigger.trigger_price, update.event_time, side),
            StrategyEvent("breakout_triggered_original_pine", trigger.signal_id, trigger.trigger_price, update.event_time, side),
        ]
        invalidated = self.strategy.invalidate_opposite_trigger(side, "blocked_by_active_chase")
        if invalidated is not None:
            events.append(invalidated)
        return events

    @staticmethod
    def _long_hit(trigger: PendingStopTrigger | None, update: LivePriceUpdate) -> bool:
        if trigger is None or not trigger.active or trigger.triggered:
            return False
        observed = [update.high_so_far, update.latest_price, update.best_ask]
        return any(value is not None and value >= trigger.trigger_price for value in observed)

    @staticmethod
    def _short_hit(trigger: PendingStopTrigger | None, update: LivePriceUpdate) -> bool:
        if trigger is None or not trigger.active or trigger.triggered:
            return False
        observed = [update.low_so_far, update.latest_price, update.best_bid]
        return any(value is not None and value <= trigger.trigger_price for value in observed)
