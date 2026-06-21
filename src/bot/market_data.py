from __future__ import annotations

import json
from collections.abc import AsyncIterator
from decimal import Decimal
import logging

import websockets

from bot.config import SUPPORTED_INTERVALS, SUPPORTED_SYMBOLS, Settings
from bot.logging_config import log_event, log_event_debug
from bot.models import Candle

LOCKED_SYMBOL = "ETHUSDC"
LOCKED_INTERVAL = "15m"
LOCKED_STREAM_NAME = "ethusdc@kline_15m"


class UserDataStreamClient:
    """Placeholder for later listen-key and account update handling."""

    async def start(self) -> None:
        raise NotImplementedError("user data stream is intentionally deferred")


def kline_stream_name(symbol: str, interval: str) -> str:
    normalized_symbol = symbol.upper()
    if normalized_symbol not in SUPPORTED_SYMBOLS:
        allowed = ", ".join(sorted(SUPPORTED_SYMBOLS))
        raise ValueError(f"Supported kline stream symbols: {allowed}")
    if interval not in SUPPORTED_INTERVALS:
        allowed = ", ".join(sorted(SUPPORTED_INTERVALS))
        raise ValueError(f"Supported kline intervals: {allowed}")
    return f"{normalized_symbol.lower()}@kline_{interval}"


def kline_ws_url(settings: Settings) -> str:
    stream = kline_stream_name(settings.binance_symbol, settings.binance_interval)
    return f"{settings.ws_market_base_url}/stream?streams={stream}"


def candle_from_kline_payload(payload: dict, logger: logging.Logger | None = None) -> Candle | None:
    data = payload.get("data", payload)
    kline = data.get("k", {})
    if not kline:
        return None
    if not kline.get("x"):
        if logger is not None:
            log_event_debug(
                logger,
                "kline_update_ignored_unclosed",
                symbol=str(kline.get("s", "")).upper(),
                interval=str(kline.get("i", "")),
                close_time=kline.get("T"),
            )
        return None
    candle = Candle(
        open_time=int(kline["t"]),
        close_time=int(kline["T"]),
        open=Decimal(str(kline["o"])),
        high=Decimal(str(kline["h"])),
        low=Decimal(str(kline["l"])),
        close=Decimal(str(kline["c"])),
        volume=Decimal(str(kline["v"])),
        closed=True,
    )
    if logger is not None:
        log_event(
            logger,
            "candle_closed_received",
            symbol=str(kline.get("s", "")).upper(),
            interval=str(kline.get("i", "")),
            close_time=candle.close_time,
            close=str(candle.close),
        )
    return candle


async def stream_closed_klines(settings: Settings, logger: logging.Logger | None = None) -> AsyncIterator[Candle]:
    url = kline_ws_url(settings)
    stream = kline_stream_name(settings.binance_symbol, settings.binance_interval)
    while True:
        if logger is not None:
            log_event(logger, "websocket_connecting", url=url, stream=stream)
        try:
            async with websockets.connect(url, ping_interval=180, ping_timeout=600) as ws:
                if logger is not None:
                    log_event(logger, "websocket_connected", url=url, stream=stream)
                async for message in ws:
                    candle = candle_from_kline_payload(json.loads(message), logger)
                    if candle is not None:
                        yield candle
        except websockets.ConnectionClosed as exc:
            if logger is not None:
                log_event(logger, "websocket_disconnected", reason=str(exc))
                log_event(logger, "websocket_reconnecting", stream=stream)
            continue
        except OSError as exc:
            if logger is not None:
                log_event(logger, "websocket_disconnected", reason=str(exc))
                log_event(logger, "websocket_reconnecting", stream=stream)
            continue


def process_kline_payload(payload: dict, strategy, logger: logging.Logger | None = None) -> Candle | None:
    candle = candle_from_kline_payload(payload, logger)
    if candle is not None:
        strategy.on_candle(candle)
    return candle
