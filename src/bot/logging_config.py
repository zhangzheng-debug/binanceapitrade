from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "created": record.created,
        }
        event_payload = getattr(record, "event_payload", None)
        if isinstance(event_payload, dict):
            payload.update(event_payload)
        return json.dumps(payload, default=str, separators=(",", ":"))


def _mb_to_bytes(value: int, *, fallback_mb: int) -> int:
    size_mb = value if value > 0 else fallback_mb
    return int(size_mb * 1_000_000)


def configure_logging(
    level: str = "INFO",
    log_dir: Path | str = "logs",
    *,
    max_bot_log_mb: int = 2,
    max_events_log_mb: int = 5,
) -> None:
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(console)

    bot_log = RotatingFileHandler(
        log_path / "bot.log",
        maxBytes=_mb_to_bytes(max_bot_log_mb, fallback_mb=2),
        backupCount=3,
        encoding="utf-8",
    )
    bot_log.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(bot_log)

    event_log = RotatingFileHandler(
        log_path / "events.jsonl",
        maxBytes=_mb_to_bytes(max_events_log_mb, fallback_mb=5),
        backupCount=3,
        encoding="utf-8",
    )
    event_log.setFormatter(JsonLineFormatter())
    root.addHandler(event_log)

    for noisy in ("httpcore", "httpx", "websockets"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_event(logger: logging.Logger, event_type: str, **fields: object) -> None:
    logger.info(event_type, extra={"event_payload": {"event": event_type, **fields}})


def log_event_debug(logger: logging.Logger, event_type: str, **fields: object) -> None:
    logger.debug(event_type, extra={"event_payload": {"event": event_type, **fields}})
