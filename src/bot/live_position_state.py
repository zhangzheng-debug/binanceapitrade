from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from bot.models import Position, PositionSide
from bot.safety import LiveTradingRejected


@dataclass(frozen=True, slots=True)
class ManagedPositionMarker:
    symbol: str
    side: PositionSide
    quantity: Decimal
    entry_price: Decimal | None
    signal_id: str
    updated_at_utc: str


def write_managed_position_marker(path: Path, position: Position, *, signal_id: str) -> None:
    if position.is_flat:
        clear_managed_position_marker(path)
        return
    payload = {
        "symbol": position.symbol,
        "side": position.side.value,
        "quantity": str(position.quantity),
        "entry_price": str(position.entry_price) if position.entry_price is not None else None,
        "signal_id": signal_id,
        "updated_at_utc": datetime.now(tz=UTC).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(payload, tmp, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def clear_managed_position_marker(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def load_managed_position_marker(path: Path) -> ManagedPositionMarker | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return marker_from_payload(payload)


def marker_from_payload(payload: dict[str, Any]) -> ManagedPositionMarker:
    return ManagedPositionMarker(
        symbol=str(payload["symbol"]).upper(),
        side=PositionSide(str(payload["side"])),
        quantity=Decimal(str(payload["quantity"])),
        entry_price=Decimal(str(payload["entry_price"])) if payload.get("entry_price") not in (None, "") else None,
        signal_id=str(payload.get("signal_id") or ""),
        updated_at_utc=str(payload.get("updated_at_utc") or ""),
    )


def assert_marker_matches_position(marker: ManagedPositionMarker, position: Position) -> None:
    if position.is_flat:
        raise LiveTradingRejected("managed position resume requires a non-flat exchange position")
    if marker.symbol != position.symbol:
        raise LiveTradingRejected("managed position marker symbol does not match exchange position")
    if marker.side != position.side:
        raise LiveTradingRejected("managed position marker side does not match exchange position")
    if marker.quantity != position.quantity:
        raise LiveTradingRejected("managed position marker quantity does not match exchange position")
