from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from decimal import Decimal

import websockets

from bot.config import Settings
from bot.logging_config import log_event
from bot.market_log_control import MarketLogControl
from bot.models import BookTickerSnapshot, utc_now

LOCKED_BOOK_TICKER_STREAM_NAME = "ethusdc@bookTicker"
LOCKED_BOOK_TICKER_ROUTED_PATH = "/public"


def book_ticker_stream_name(symbol: str) -> str:
    if symbol.upper() != "ETHUSDC":
        raise ValueError("Initial release only supports ETHUSDC bookTicker stream")
    return LOCKED_BOOK_TICKER_STREAM_NAME


def book_ticker_ws_url(settings: Settings) -> str:
    stream = book_ticker_stream_name(settings.binance_symbol)
    return f"{settings.ws_public_base_url}/stream?streams={stream}"


def snapshot_from_book_ticker_payload(payload: dict) -> BookTickerSnapshot:
    data = payload.get("data", payload)
    return BookTickerSnapshot(
        symbol=str(data["s"]),
        best_bid_price=Decimal(str(data["b"])),
        best_bid_qty=Decimal(str(data["B"])),
        best_ask_price=Decimal(str(data["a"])),
        best_ask_qty=Decimal(str(data["A"])),
        event_time=int(data["E"]) if data.get("E") is not None else None,
        received_at=utc_now(),
        source="websocket",
    )


class BookTickerStream:
    def __init__(
        self,
        settings: Settings,
        logger: logging.Logger | None = None,
        *,
        callback: Callable[[BookTickerSnapshot], Awaitable[None] | None] | None = None,
        queue: asyncio.Queue[BookTickerSnapshot] | None = None,
        market_log_control: MarketLogControl | None = None,
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.callback = callback
        self.queue = queue
        self.market_log_control = market_log_control or MarketLogControl(settings)
        self.latest_snapshot: BookTickerSnapshot | None = None
        self._first_snapshot = asyncio.Event()
        self._update_count = 0
        self.connected_count = 0
        self.reconnect_count = 0
        self.error_count = 0

    @property
    def update_count(self) -> int:
        return self._update_count

    async def wait_for_first(self, timeout_seconds: float) -> BookTickerSnapshot:
        await asyncio.wait_for(self._first_snapshot.wait(), timeout=timeout_seconds)
        if self.latest_snapshot is None:
            raise TimeoutError("bookTicker first snapshot was signaled but no snapshot is available")
        return self.latest_snapshot

    async def run(self, *, max_seconds: float | None = None) -> None:
        url = book_ticker_ws_url(self.settings)
        deadline = time.monotonic() + max_seconds if max_seconds is not None else None
        while deadline is None or time.monotonic() < deadline:
            if self.logger is not None:
                log_event(
                    self.logger,
                    "book_ticker_ws_connecting",
                    url=url,
                    stream=LOCKED_BOOK_TICKER_STREAM_NAME,
                    routed_path=LOCKED_BOOK_TICKER_ROUTED_PATH,
                )
            try:
                async with websockets.connect(url, ping_interval=180, ping_timeout=600) as ws:
                    self.connected_count += 1
                    if self.logger is not None:
                        log_event(self.logger, "book_ticker_ws_connected", stream=LOCKED_BOOK_TICKER_STREAM_NAME)
                    while deadline is None or time.monotonic() < deadline:
                        timeout = max(0.0, deadline - time.monotonic()) if deadline is not None else None
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=timeout)
                        except TimeoutError:
                            return
                        self._update_count += 1
                        if (
                            self.logger is not None
                            and self.market_log_control.should_log_raw_market_message()
                            and self.market_log_control.should_log_bookticker_detail(self._update_count)
                        ):
                            log_event(
                                self.logger,
                                "book_ticker_update_received",
                                stream=LOCKED_BOOK_TICKER_STREAM_NAME,
                                update_count=self._update_count,
                            )
                        try:
                            snapshot = snapshot_from_book_ticker_payload(json.loads(message))
                        except Exception as exc:
                            if self.logger is not None:
                                self.error_count += 1
                                log_event(
                                    self.logger,
                                    "book_ticker_ws_error",
                                    error=exc.__class__.__name__,
                                    message=str(exc),
                                )
                            continue
                        await self._publish(snapshot)
            except websockets.ConnectionClosed as exc:
                self.reconnect_count += 1
                if self.logger is not None:
                    log_event(self.logger, "book_ticker_ws_disconnected", reason=str(exc))
                    log_event(self.logger, "book_ticker_ws_reconnecting", stream=LOCKED_BOOK_TICKER_STREAM_NAME)
                continue
            except OSError as exc:
                self.error_count += 1
                self.reconnect_count += 1
                if self.logger is not None:
                    log_event(self.logger, "book_ticker_ws_error", error=exc.__class__.__name__, message=str(exc))
                    log_event(self.logger, "book_ticker_ws_reconnecting", stream=LOCKED_BOOK_TICKER_STREAM_NAME)
                continue
        if self.logger is not None:
            log_event(self.logger, "book_ticker_ws_disconnected", reason="bounded_run_finished")

    async def _publish(self, snapshot: BookTickerSnapshot) -> None:
        self.latest_snapshot = snapshot
        self._first_snapshot.set()
        if self.queue is not None:
            await self.queue.put(snapshot)
        if self.callback is not None:
            result = self.callback(snapshot)
            if result is not None:
                await result
        decision = self.market_log_control.record_bookticker_snapshot(self._update_count, snapshot)
        if self.logger is not None and decision.log_detail:
            log_event(
                self.logger,
                "book_ticker_update_parsed",
                **decision.detail_payload,
            )
        if self.logger is not None and decision.log_summary:
            log_event(self.logger, "book_ticker_summary", **decision.summary_payload)
