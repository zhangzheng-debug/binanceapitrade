from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Iterator

from bot.models import OrderState, Position, StrategyState


class StateStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS bot_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS strategy_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    close_time INTEGER PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                    event_id TEXT PRIMARY KEY,
                    signal_id TEXT,
                    order_id TEXT,
                    client_order_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    type TEXT NOT NULL,
                    time_in_force TEXT,
                    reduce_only INTEGER NOT NULL,
                    requested_qty TEXT NOT NULL,
                    requested_price TEXT,
                    executed_qty TEXT NOT NULL,
                    avg_price TEXT,
                    status TEXT NOT NULL,
                    raw_response_summary TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS positions_snapshot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    entry_price TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reconciliation_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ok INTEGER NOT NULL,
                    dry_run INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def save_strategy_state(self, state: StrategyState) -> None:
        payload = json.dumps(_to_jsonable(asdict(state)), separators=(",", ":"))
        now = datetime.utcnow().isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO strategy_state (id, payload, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
                """,
                (payload, now),
            )

    def record_order_event(self, signal_id: str | None, order: OrderState, event_id: str) -> None:
        now = datetime.utcnow().isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO orders (
                    event_id, signal_id, order_id, client_order_id, symbol, side, type, time_in_force,
                    reduce_only, requested_qty, requested_price, executed_qty, avg_price, status,
                    raw_response_summary, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    signal_id,
                    order.order_id,
                    order.client_order_id,
                    order.symbol,
                    order.side.value,
                    order.order_type.value,
                    order.time_in_force.value if order.time_in_force else None,
                    1 if order.reduce_only else 0,
                    str(order.quantity),
                    str(order.price) if order.price is not None else None,
                    str(order.executed_qty),
                    str(order.avg_price) if order.avg_price is not None else None,
                    order.status.value,
                    json.dumps(order.raw_response_summary, separators=(",", ":")),
                    now,
                ),
            )

    def record_position_snapshot(self, position: Position) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO positions_snapshot (symbol, side, quantity, entry_price, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    position.symbol,
                    position.side.value,
                    str(position.quantity),
                    str(position.entry_price) if position.entry_price is not None else None,
                    datetime.utcnow().isoformat(),
                ),
            )

    def record_event(self, event_id: str, event_type: str, payload: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO events (event_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    event_type = excluded.event_type,
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (
                    event_id,
                    event_type,
                    json.dumps(_to_jsonable(payload), separators=(",", ":")),
                    datetime.utcnow().isoformat(),
                ),
            )


def _to_jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    return value
