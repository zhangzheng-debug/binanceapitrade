from decimal import Decimal

import pytest

from bot.live_position_state import (
    assert_marker_matches_position,
    clear_managed_position_marker,
    load_managed_position_marker,
    write_managed_position_marker,
)
from bot.models import Position, PositionSide
from bot.safety import LiveTradingRejected


def test_managed_position_marker_roundtrip(tmp_path) -> None:
    path = tmp_path / "live_managed_position.json"
    position = Position("ETHUSDC", PositionSide.LONG, Decimal("2.444"), Decimal("1728.88"))

    write_managed_position_marker(path, position, signal_id="sig1")
    marker = load_managed_position_marker(path)

    assert marker is not None
    assert marker.symbol == "ETHUSDC"
    assert marker.side == PositionSide.LONG
    assert marker.quantity == Decimal("2.444")
    assert marker.entry_price == Decimal("1728.88")
    assert marker.signal_id == "sig1"
    assert_marker_matches_position(marker, position)


def test_marker_mismatch_rejects_resume(tmp_path) -> None:
    path = tmp_path / "live_managed_position.json"
    write_managed_position_marker(path, Position("ETHUSDC", PositionSide.LONG, Decimal("2.444"), Decimal("1728.88")), signal_id="sig1")
    marker = load_managed_position_marker(path)
    assert marker is not None

    with pytest.raises(LiveTradingRejected, match="quantity"):
        assert_marker_matches_position(marker, Position("ETHUSDC", PositionSide.LONG, Decimal("1"), Decimal("1728.88")))


def test_flat_position_clears_marker(tmp_path) -> None:
    path = tmp_path / "live_managed_position.json"
    write_managed_position_marker(path, Position("ETHUSDC", PositionSide.LONG, Decimal("2.444"), Decimal("1728.88")), signal_id="sig1")

    clear_managed_position_marker(path)

    assert load_managed_position_marker(path) is None
