from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from bot.config import Settings
from bot.market_log_control import MarketLogControl
from bot.models import BookTickerSnapshot
from bot.phase_fast_runtime import PhaseFastRuntimeSummary, collect_log_size_status, write_fast_runtime_summary


ROOT = Path(__file__).resolve().parents[1]
FAST_UNIT = ROOT / "deploy" / "systemd" / "ethusdc-pivot-bot-fast-smoke.user.service"
INSTALL_SCRIPT = ROOT / "scripts" / "install_fast_smoke_user_service.sh"
START_SCRIPT = ROOT / "scripts" / "start_fast_smoke_user_service.sh"


class ManualClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def snapshot() -> BookTickerSnapshot:
    return BookTickerSnapshot(
        symbol="ETHUSDC",
        best_bid_price=Decimal("1726.60"),
        best_bid_qty=Decimal("1"),
        best_ask_price=Decimal("1726.61"),
        best_ask_qty=Decimal("1"),
        event_time=1,
        received_at=datetime.now(tz=UTC),
        source="websocket",
    )


def fast_settings(**overrides) -> Settings:
    values = {
        "DRY_RUN": True,
        "LIVE_TRADING": False,
        "PUBLIC_MARKET_DRY_RUN": True,
        "PUBLIC_MARKET_WS_ONLY": True,
        "EXIT_AFTER_BOUNDED_RUNTIME": True,
        "PHASE_FAST_SMOKE_SECONDS": 1800,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_bookticker_log_sampling_reduces_event_volume() -> None:
    control = MarketLogControl(fast_settings(BOOKTICKER_LOG_EVERY_N=2000))
    logged = []
    for update_count in range(1, 5001):
        decision = control.record_bookticker_snapshot(update_count, snapshot())
        if decision.log_detail:
            logged.append(update_count)
    assert logged == [1, 2000, 4000]
    assert control.bookticker_logged_detail_count == 3


def test_bookticker_summary_interval() -> None:
    clock = ManualClock()
    control = MarketLogControl(fast_settings(BOOKTICKER_SUMMARY_INTERVAL_SECONDS=60), clock=clock)
    assert control.record_bookticker_snapshot(1, snapshot()).log_summary is True
    clock.advance(59)
    assert control.record_bookticker_snapshot(2, snapshot()).log_summary is False
    clock.advance(1)
    assert control.record_bookticker_snapshot(3, snapshot()).log_summary is True
    assert control.bookticker_summary_count == 2


def test_unclosed_kline_sampling() -> None:
    control = MarketLogControl(fast_settings(KLINE_LOG_UNCLOSED_EVERY_N=200))
    logged = [count for count in range(1, 401) if control.should_log_unclosed_kline(count)]
    assert logged == [1, 200, 400]


def test_closed_kline_always_logged() -> None:
    control = MarketLogControl(fast_settings())
    assert control.should_log_closed_kline() is True


def test_fast_smoke_unit_no_live() -> None:
    text = FAST_UNIT.read_text(encoding="utf-8")
    assert "Environment=LIVE_TRADING=false" in text
    assert "LIVE_TRADING=true" not in text
    assert "RuntimeMaxSec=1900" in text
    assert "systemctl" not in text


def test_fast_smoke_unit_no_api_key() -> None:
    text = FAST_UNIT.read_text(encoding="utf-8")
    assert "Environment=BINANCE_API_KEY=\n" in text
    assert "Environment=BINANCE_API_SECRET=\n" in text
    assert "APIKEY" not in text


def test_fast_smoke_unit_no_enable() -> None:
    install_text = INSTALL_SCRIPT.read_text(encoding="utf-8")
    start_text = START_SCRIPT.read_text(encoding="utf-8")
    unit_text = FAST_UNIT.read_text(encoding="utf-8")
    assert "systemctl --user enable" not in install_text
    assert "systemctl --user enable" not in start_text
    assert "WantedBy=" not in unit_text


def test_fast_smoke_runtime_summary_fields(tmp_path: Path) -> None:
    summary = PhaseFastRuntimeSummary()
    summary.bookticker_update_count = 5000
    summary.bookticker_logged_detail_count = 3
    summary.bookticker_summary_count = 2
    summary.latest_bid = "1726.60"
    summary.latest_ask = "1726.61"
    path = tmp_path / "fast_smoke_runtime_summary.json"
    payload = write_fast_runtime_summary(summary, path, final_status="completed")
    assert path.exists()
    assert payload["bookticker_update_count"] == 5000
    assert payload["bookticker_logged_detail_count"] == 3
    assert payload["bookticker_summary_count"] == 2
    assert payload["latest_bid"] == "1726.60"


def test_log_size_warning_fields(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "events.jsonl").write_text("x" * 1_100_000, encoding="utf-8")
    settings = fast_settings(WARN_EVENTS_LOG_MB=1, MAX_EVENTS_LOG_MB=100)
    status = collect_log_size_status(settings, log_dir)
    assert status["events_log_size_mb"] >= 1
    assert status["events_log_warned"] is True
    assert status["events_log_max_mb"] == 100


def test_raw_market_messages_disabled_by_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.log_raw_market_messages is False
