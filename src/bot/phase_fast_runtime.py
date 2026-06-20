from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bot.config import Settings
from bot.logging_config import log_event
from bot.market_log_control import MarketLogControl
from bot.phase3b_runtime import Phase3BRuntimeSummary, write_runtime_summary


@dataclass(slots=True)
class PhaseFastRuntimeSummary(Phase3BRuntimeSummary):
    bookticker_logged_detail_count: int = 0
    bookticker_summary_count: int = 0
    latest_bid: str | None = None
    latest_ask: str | None = None
    latest_maker_buy: str | None = None
    latest_maker_sell: str | None = None
    events_log_size_mb: float = 0.0
    events_log_warn_mb: int = 0
    events_log_max_mb: int = 0
    events_log_warned: bool = False
    events_log_limit_exceeded: bool = False
    bot_log_size_mb: float = 0.0
    bot_log_warn_mb: int = 0
    bot_log_max_mb: int = 0
    bot_log_warned: bool = False
    bot_log_limit_exceeded: bool = False

    def update_from_market_log(self, market_log: MarketLogControl) -> None:
        fields = market_log.runtime_fields()
        self.bookticker_logged_detail_count = int(fields["bookticker_logged_detail_count"])
        self.bookticker_summary_count = int(fields["bookticker_summary_count"])
        self.latest_bid = str(fields["latest_bid"] or "") or None
        self.latest_ask = str(fields["latest_ask"] or "") or None
        self.latest_maker_buy = str(fields["latest_maker_buy"] or "") or None
        self.latest_maker_sell = str(fields["latest_maker_sell"] or "") or None


def _size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    return round(path.stat().st_size / 1_000_000, 3)


def collect_log_size_status(settings: Settings, log_dir: Path | str = "logs") -> dict[str, Any]:
    root = Path(log_dir)
    events_size = _size_mb(root / "events.jsonl")
    bot_size = _size_mb(root / "bot.log")
    return {
        "events_log_size_mb": events_size,
        "events_log_warn_mb": settings.warn_events_log_mb,
        "events_log_max_mb": settings.max_events_log_mb,
        "events_log_warned": events_size >= settings.warn_events_log_mb,
        "events_log_limit_exceeded": events_size >= settings.max_events_log_mb,
        "bot_log_size_mb": bot_size,
        "bot_log_warn_mb": settings.warn_bot_log_mb,
        "bot_log_max_mb": settings.max_bot_log_mb,
        "bot_log_warned": bot_size >= settings.warn_bot_log_mb,
        "bot_log_limit_exceeded": bot_size >= settings.max_bot_log_mb,
    }


def apply_log_size_status(
    summary: PhaseFastRuntimeSummary,
    settings: Settings,
    logger: logging.Logger | None = None,
    log_dir: Path | str = "logs",
) -> dict[str, Any]:
    status = collect_log_size_status(settings, log_dir)
    for key, value in status.items():
        setattr(summary, key, value)
    if logger is not None:
        for prefix, filename in (("events", "events.jsonl"), ("bot", "bot.log")):
            if status[f"{prefix}_log_warned"]:
                log_event(
                    logger,
                    "log_size_warning",
                    log_file=filename,
                    size_mb=status[f"{prefix}_log_size_mb"],
                    warn_mb=status[f"{prefix}_log_warn_mb"],
                    max_mb=status[f"{prefix}_log_max_mb"],
                    limit_exceeded=status[f"{prefix}_log_limit_exceeded"],
                )
    return status


def write_fast_runtime_summary(
    summary: PhaseFastRuntimeSummary,
    path: Path | str,
    *,
    final_status: str,
) -> dict[str, Any]:
    return write_runtime_summary(summary, path, final_status=final_status)


def mirror_fast_runtime_summary(payload: dict[str, Any], path: Path | str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
