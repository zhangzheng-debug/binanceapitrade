from __future__ import annotations

from collections import deque
from decimal import Decimal

from bot.models import (
    Candle,
    PendingStopTrigger,
    PendingTriggerSide,
    StrategyEvent,
    StrategySignalSide,
    StrategyState,
    new_id,
    utc_now,
)


class PivotReversalStrategy:
    def __init__(
        self,
        left_bars: int = 4,
        right_bars: int = 2,
        *,
        tick_size: Decimal = Decimal("0.01"),
        max_candles: int = 500,
    ) -> None:
        if left_bars < 1 or right_bars < 1:
            raise ValueError("left_bars and right_bars must be positive")
        self.left_bars = left_bars
        self.right_bars = right_bars
        self.tick_size = tick_size
        self.candles: deque[Candle] = deque(maxlen=max_candles)
        self.state = StrategyState()

    def on_candle(self, candle: Candle) -> list[StrategyEvent]:
        if not candle.closed:
            return []
        self.candles.append(candle)
        self.state.last_closed_candle_time = candle.close_time
        events: list[StrategyEvent] = []

        pivot_high = self._confirmed_pivot_high()
        pivot_low = self._confirmed_pivot_low()

        if pivot_high is not None:
            self.state.hprice = pivot_high.high
            self.state.le = True
            events.append(
                StrategyEvent(
                    event_type="pivot_high_confirmed",
                    price=pivot_high.high,
                    candle_time=pivot_high.close_time,
                )
            )
        elif self.state.le and self.state.hprice is not None and candle.high > self.state.hprice:
            self.state.le = False
            if not self._pending_triggered("long"):
                events.append(
                    StrategyEvent(
                        event_type="missed_long_trigger_on_closed_candle",
                        price=self.state.hprice + self.tick_size,
                        candle_time=candle.close_time,
                        side=StrategySignalSide.LONG,
                    )
                )

        if pivot_low is not None:
            self.state.lprice = pivot_low.low
            self.state.se = True
            events.append(
                StrategyEvent(
                    event_type="pivot_low_confirmed",
                    price=pivot_low.low,
                    candle_time=pivot_low.close_time,
                )
            )
        elif self.state.se and self.state.lprice is not None and candle.low < self.state.lprice:
            self.state.se = False
            if not self._pending_triggered("short"):
                events.append(
                    StrategyEvent(
                        event_type="missed_short_trigger_on_closed_candle",
                        price=self.state.lprice - self.tick_size,
                        candle_time=candle.close_time,
                        side=StrategySignalSide.SHORT,
                    )
                )

        events.extend(self._sync_pending_long(candle.close_time))
        events.extend(self._sync_pending_short(candle.close_time))
        self.state.armed_long = self.state.le and self.state.pending_long_trigger is not None and self.state.pending_long_trigger.active
        self.state.armed_short = self.state.se and self.state.pending_short_trigger is not None and self.state.pending_short_trigger.active
        return events

    def check_breakout(self, last_price: Decimal, tick_size: Decimal) -> StrategyEvent | None:
        self.tick_size = tick_size
        long_trigger = self.state.pending_long_trigger
        if long_trigger is not None and long_trigger.active and last_price >= long_trigger.trigger_price:
            self.mark_triggered(long_trigger, "legacy_last_price")
            return StrategyEvent(
                event_type="breakout_triggered_original_pine",
                signal_id=long_trigger.signal_id,
                side=StrategySignalSide.LONG,
                price=long_trigger.trigger_price,
                candle_time=self.state.last_closed_candle_time,
            )
        short_trigger = self.state.pending_short_trigger
        if short_trigger is not None and short_trigger.active and last_price <= short_trigger.trigger_price:
            self.mark_triggered(short_trigger, "legacy_last_price")
            return StrategyEvent(
                event_type="breakout_triggered_original_pine",
                signal_id=short_trigger.signal_id,
                side=StrategySignalSide.SHORT,
                price=short_trigger.trigger_price,
                candle_time=self.state.last_closed_candle_time,
            )
        return None

    def mark_triggered(self, trigger: PendingStopTrigger, source: str) -> None:
        trigger.active = False
        trigger.triggered = True
        trigger.trigger_detected_at = utc_now()
        trigger.trigger_source = source
        if trigger.side == PendingTriggerSide.LONG_TRIGGER:
            self.state.le = False
            self.state.armed_long = False
        else:
            self.state.se = False
            self.state.armed_short = False

    def invalidate_opposite_trigger(self, side: StrategySignalSide, reason: str) -> StrategyEvent | None:
        if side == StrategySignalSide.LONG:
            trigger = self.state.pending_short_trigger
            event_type = "pending_short_stop_invalidated"
            event_side = StrategySignalSide.SHORT
        else:
            trigger = self.state.pending_long_trigger
            event_type = "pending_long_stop_invalidated"
            event_side = StrategySignalSide.LONG
        if trigger is None or not trigger.active or trigger.triggered:
            return None
        trigger.active = False
        trigger.invalidated_at = utc_now()
        trigger.invalidation_reason = reason
        return StrategyEvent(event_type, trigger.signal_id, trigger.trigger_price, self.state.last_closed_candle_time, event_side)

    def _sync_pending_long(self, closed_candle_time: int) -> list[StrategyEvent]:
        if self.state.le and self.state.hprice is not None:
            trigger_price = self.state.hprice + self.tick_size
            self.state.active_long_stop_price = trigger_price
            existing = self.state.pending_long_trigger
            if existing is None or not existing.active or existing.triggered:
                signal_id = new_id("sig")
                self.state.pending_long_trigger = PendingStopTrigger(
                    signal_id=signal_id,
                    side=PendingTriggerSide.LONG_TRIGGER,
                    pine_entry_id="PivRevLE",
                    pivot_price=self.state.hprice,
                    trigger_price=trigger_price,
                    created_from_closed_candle_time=closed_candle_time,
                )
                self.state.current_signal_id = signal_id
                return [
                    StrategyEvent("pending_long_stop_created", signal_id, trigger_price, closed_candle_time, StrategySignalSide.LONG),
                    StrategyEvent("long_armed", signal_id, trigger_price, closed_candle_time, StrategySignalSide.LONG),
                ]
            if existing.trigger_price != trigger_price or existing.pivot_price != self.state.hprice:
                existing.pivot_price = self.state.hprice
                existing.trigger_price = trigger_price
                existing.created_from_closed_candle_time = closed_candle_time
                return [StrategyEvent("pending_long_stop_updated", existing.signal_id, trigger_price, closed_candle_time, StrategySignalSide.LONG)]
            return []
        self.state.active_long_stop_price = None
        trigger = self.state.pending_long_trigger
        if trigger is not None and trigger.active and not trigger.triggered:
            trigger.active = False
            trigger.invalidated_at = utc_now()
            trigger.invalidation_reason = "le_false"
            return [StrategyEvent("pending_long_stop_invalidated", trigger.signal_id, trigger.trigger_price, closed_candle_time, StrategySignalSide.LONG)]
        return []

    def _sync_pending_short(self, closed_candle_time: int) -> list[StrategyEvent]:
        if self.state.se and self.state.lprice is not None:
            trigger_price = self.state.lprice - self.tick_size
            self.state.active_short_stop_price = trigger_price
            existing = self.state.pending_short_trigger
            if existing is None or not existing.active or existing.triggered:
                signal_id = new_id("sig")
                self.state.pending_short_trigger = PendingStopTrigger(
                    signal_id=signal_id,
                    side=PendingTriggerSide.SHORT_TRIGGER,
                    pine_entry_id="PivRevSE",
                    pivot_price=self.state.lprice,
                    trigger_price=trigger_price,
                    created_from_closed_candle_time=closed_candle_time,
                )
                self.state.current_signal_id = signal_id
                return [
                    StrategyEvent("pending_short_stop_created", signal_id, trigger_price, closed_candle_time, StrategySignalSide.SHORT),
                    StrategyEvent("short_armed", signal_id, trigger_price, closed_candle_time, StrategySignalSide.SHORT),
                ]
            if existing.trigger_price != trigger_price or existing.pivot_price != self.state.lprice:
                existing.pivot_price = self.state.lprice
                existing.trigger_price = trigger_price
                existing.created_from_closed_candle_time = closed_candle_time
                return [StrategyEvent("pending_short_stop_updated", existing.signal_id, trigger_price, closed_candle_time, StrategySignalSide.SHORT)]
            return []
        self.state.active_short_stop_price = None
        trigger = self.state.pending_short_trigger
        if trigger is not None and trigger.active and not trigger.triggered:
            trigger.active = False
            trigger.invalidated_at = utc_now()
            trigger.invalidation_reason = "se_false"
            return [StrategyEvent("pending_short_stop_invalidated", trigger.signal_id, trigger.trigger_price, closed_candle_time, StrategySignalSide.SHORT)]
        return []

    def _pending_triggered(self, side: str) -> bool:
        trigger = self.state.pending_long_trigger if side == "long" else self.state.pending_short_trigger
        return trigger is not None and trigger.triggered

    def _confirmed_pivot_high(self) -> Candle | None:
        return self._confirmed_pivot(kind="high")

    def _confirmed_pivot_low(self) -> Candle | None:
        return self._confirmed_pivot(kind="low")

    def _confirmed_pivot(self, *, kind: str) -> Candle | None:
        total_needed = self.left_bars + self.right_bars + 1
        if len(self.candles) < total_needed:
            return None

        items = list(self.candles)
        candidate_index = len(items) - 1 - self.right_bars
        candidate = items[candidate_index]
        left = items[candidate_index - self.left_bars : candidate_index]
        right = items[candidate_index + 1 : candidate_index + 1 + self.right_bars]

        if kind == "high":
            return candidate if all(candidate.high > c.high for c in left + right) else None
        return candidate if all(candidate.low < c.low for c in left + right) else None
