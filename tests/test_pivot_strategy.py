from decimal import Decimal

from bot.models import Candle
from bot.strategy_pivot import PivotReversalStrategy


def c(i: int, high: str, low: str, close: str | None = None, closed: bool = True) -> Candle:
    return Candle(
        open_time=i * 1000,
        close_time=i * 1000 + 999,
        open=Decimal(close or low),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close or low),
        closed=closed,
    )


def test_pivot_high_delayed_confirmation_right_bars_2() -> None:
    strategy = PivotReversalStrategy(left_bars=4, right_bars=2)
    highs = ["1", "2", "3", "4", "10", "7", "6"]
    events = []
    for i, high in enumerate(highs):
        events.extend(strategy.on_candle(c(i, high, "1", "5")))
        if i < 6:
            assert not any(event.event_type == "pivot_high_confirmed" for event in events)
    assert any(event.event_type == "pivot_high_confirmed" and event.price == Decimal("10") for event in events)


def test_pivot_low_delayed_confirmation_right_bars_2() -> None:
    strategy = PivotReversalStrategy(left_bars=4, right_bars=2)
    lows = ["10", "9", "8", "7", "1", "4", "5"]
    events = []
    for i, low in enumerate(lows):
        events.extend(strategy.on_candle(c(i, "12", low, "6")))
        if i < 6:
            assert not any(event.event_type == "pivot_low_confirmed" for event in events)
    assert any(event.event_type == "pivot_low_confirmed" and event.price == Decimal("1") for event in events)


def test_pine_state_semantics_for_pivot_flags() -> None:
    strategy = PivotReversalStrategy(left_bars=4, right_bars=2)
    for i, high in enumerate(["1", "2", "3", "4", "10", "7", "6"]):
        strategy.on_candle(c(i, high, "1", "5"))

    assert strategy.state.hprice == Decimal("10")
    assert strategy.state.le is True
    assert strategy.state.armed_long is True

    strategy.on_candle(c(7, "11", "3", "11"))
    assert strategy.state.le is False
    assert strategy.state.armed_long is False

    low_strategy = PivotReversalStrategy(left_bars=4, right_bars=2)
    for i, low in enumerate(["10", "9", "8", "7", "1", "4", "5"]):
        low_strategy.on_candle(c(i, "12", low, "6"))
    assert low_strategy.state.lprice == Decimal("1")
    assert low_strategy.state.se is True
    low_strategy.on_candle(c(7, "8", "0.5", "0.5"))
    assert low_strategy.state.se is False


def test_unclosed_candle_does_not_update_pivot() -> None:
    strategy = PivotReversalStrategy(left_bars=4, right_bars=2)
    for i, high in enumerate(["1", "2", "3", "4", "10", "7"]):
        strategy.on_candle(c(i, high, "1", "5"))
    strategy.on_candle(c(6, "6", "1", "5", closed=False))
    assert strategy.state.hprice is None

    strategy.on_candle(c(6, "6", "1", "5", closed=True))
    assert strategy.state.hprice == Decimal("10")

