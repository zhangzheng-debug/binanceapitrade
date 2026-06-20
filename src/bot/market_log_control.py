from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from bot.config import Settings
from bot.models import BookTickerSnapshot


@dataclass(slots=True)
class BookTickerLogDecision:
    log_detail: bool
    log_summary: bool
    detail_payload: dict[str, object] = field(default_factory=dict)
    summary_payload: dict[str, object] = field(default_factory=dict)


class MarketLogControl:
    def __init__(self, settings: Settings, *, clock: Callable[[], float] | None = None) -> None:
        self.settings = settings
        self.clock = clock or time.monotonic
        self.bookticker_update_count = 0
        self.bookticker_logged_detail_count = 0
        self.bookticker_summary_count = 0
        self.latest_bid: str | None = None
        self.latest_ask: str | None = None
        self.latest_maker_buy: str | None = None
        self.latest_maker_sell: str | None = None
        self._last_bookticker_summary_at: float | None = None

    def should_log_raw_market_message(self) -> bool:
        return self.settings.log_raw_market_messages

    def should_log_bookticker_detail(self, update_count: int) -> bool:
        if self.settings.bookticker_log_mode == "detail":
            return True
        return update_count == 1 or update_count % self.settings.bookticker_log_every_n == 0

    def set_latest_maker_prices(self, buy_price: Decimal, sell_price: Decimal) -> None:
        self.latest_maker_buy = str(buy_price)
        self.latest_maker_sell = str(sell_price)

    def record_bookticker_snapshot(self, update_count: int, snapshot: BookTickerSnapshot) -> BookTickerLogDecision:
        self.bookticker_update_count = update_count
        self.latest_bid = str(snapshot.best_bid_price)
        self.latest_ask = str(snapshot.best_ask_price)

        log_detail = self.should_log_bookticker_detail(update_count)
        if log_detail:
            self.bookticker_logged_detail_count += 1

        now = self.clock()
        log_summary = (
            self.settings.bookticker_log_mode == "summary"
            and (
                self._last_bookticker_summary_at is None
                or now - self._last_bookticker_summary_at >= self.settings.bookticker_summary_interval_seconds
            )
        )
        if log_summary:
            self._last_bookticker_summary_at = now
            self.bookticker_summary_count += 1

        return BookTickerLogDecision(
            log_detail=log_detail,
            log_summary=log_summary,
            detail_payload={
                "symbol": snapshot.symbol,
                "best_bid": self.latest_bid,
                "best_ask": self.latest_ask,
                "source": snapshot.source,
                "update_count": self.bookticker_update_count,
                "logged_detail_count": self.bookticker_logged_detail_count,
            },
            summary_payload=self.bookticker_summary_payload(),
        )

    def bookticker_summary_payload(self) -> dict[str, object]:
        return {
            "bookticker_update_count": self.bookticker_update_count,
            "bookticker_logged_detail_count": self.bookticker_logged_detail_count,
            "bookticker_summary_count": self.bookticker_summary_count,
            "latest_bid": self.latest_bid or "",
            "latest_ask": self.latest_ask or "",
            "latest_maker_buy": self.latest_maker_buy or "",
            "latest_maker_sell": self.latest_maker_sell or "",
        }

    def should_log_unclosed_kline(self, unclosed_count: int) -> bool:
        return unclosed_count == 1 or unclosed_count % self.settings.kline_log_unclosed_every_n == 0

    def should_log_closed_kline(self) -> bool:
        return True

    def runtime_fields(self) -> dict[str, object]:
        return self.bookticker_summary_payload()
