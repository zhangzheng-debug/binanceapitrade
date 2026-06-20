from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from bot.binance_client import BinanceClient
from bot.book_ticker_stream import BookTickerStream
from bot.models import BookTickerSnapshot, utc_now


class BookTickerUnavailable(TimeoutError):
    pass


class BookTickerProvider(Protocol):
    source_name: str

    async def get_latest(self, symbol: str) -> BookTickerSnapshot | None: ...

    async def wait_for_first(self, symbol: str, timeout_seconds: float) -> BookTickerSnapshot: ...


def _is_stale(snapshot: BookTickerSnapshot, stale_seconds: float) -> bool:
    now = datetime.now(tz=UTC)
    return (now - snapshot.received_at).total_seconds() > stale_seconds


class RestBookTickerProvider:
    source_name = "rest_book_ticker"

    def __init__(self, client: BinanceClient, *, stale_seconds: float = 5.0) -> None:
        self.client = client
        self.stale_seconds = stale_seconds
        self._latest: BookTickerSnapshot | None = None

    async def get_latest(self, symbol: str) -> BookTickerSnapshot | None:
        payload = await self.client.book_ticker(symbol)
        self._latest = BookTickerSnapshot(
            symbol=str(payload["symbol"]),
            best_bid_price=Decimal(str(payload["bidPrice"])),
            best_bid_qty=Decimal(str(payload["bidQty"])),
            best_ask_price=Decimal(str(payload["askPrice"])),
            best_ask_qty=Decimal(str(payload["askQty"])),
            event_time=None,
            received_at=utc_now(),
            source="rest",
        )
        return self._latest

    async def wait_for_first(self, symbol: str, timeout_seconds: float) -> BookTickerSnapshot:
        try:
            snapshot = await asyncio.wait_for(self.get_latest(symbol), timeout=timeout_seconds)
        except TimeoutError as exc:
            raise BookTickerUnavailable("timed out waiting for REST bookTicker") from exc
        if snapshot is None:
            raise BookTickerUnavailable("REST bookTicker returned no snapshot")
        return snapshot


class WebSocketBookTickerProvider:
    source_name = "websocket_book_ticker"

    def __init__(self, stream: BookTickerStream, *, stale_seconds: float = 5.0) -> None:
        self.stream = stream
        self.stale_seconds = stale_seconds

    async def get_latest(self, symbol: str) -> BookTickerSnapshot | None:
        snapshot = self.stream.latest_snapshot
        if snapshot is None or snapshot.symbol != symbol.upper():
            return None
        if _is_stale(snapshot, self.stale_seconds):
            return None
        return snapshot

    async def wait_for_first(self, symbol: str, timeout_seconds: float) -> BookTickerSnapshot:
        try:
            snapshot = await self.stream.wait_for_first(timeout_seconds)
        except TimeoutError as exc:
            raise BookTickerUnavailable("timed out waiting for WebSocket bookTicker") from exc
        if snapshot.symbol != symbol.upper():
            raise BookTickerUnavailable(f"received bookTicker for {snapshot.symbol}, not {symbol.upper()}")
        fresh = await self.get_latest(symbol)
        if fresh is None:
            raise BookTickerUnavailable("bookTicker snapshot is stale or unavailable")
        return fresh


class StaticBookTickerProvider:
    source_name = "static_book_ticker"

    def __init__(self, snapshot: BookTickerSnapshot | None, *, stale_seconds: float = 5.0) -> None:
        self.snapshot = snapshot
        self.stale_seconds = stale_seconds

    async def get_latest(self, symbol: str) -> BookTickerSnapshot | None:
        if self.snapshot is None or self.snapshot.symbol != symbol.upper():
            return None
        if _is_stale(self.snapshot, self.stale_seconds):
            return None
        return self.snapshot

    async def wait_for_first(self, symbol: str, timeout_seconds: float) -> BookTickerSnapshot:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            snapshot = await self.get_latest(symbol)
            if snapshot is not None:
                return snapshot
            await asyncio.sleep(0.01)
        raise BookTickerUnavailable("timed out waiting for static bookTicker")
