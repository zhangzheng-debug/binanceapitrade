import pytest

from bot.config import ConfigError, Settings, load_settings


def test_interval_locked_to_15m() -> None:
    settings = Settings(BINANCE_INTERVAL="15m", _env_file=None)
    assert settings.binance_interval == "15m"


def assert_interval_rejected(monkeypatch, interval: str) -> None:
    monkeypatch.setenv("BINANCE_INTERVAL", interval)
    with pytest.raises(ConfigError, match="only supports BINANCE_INTERVAL=15m"):
        load_settings()


def test_interval_rejects_1m(monkeypatch) -> None:
    assert_interval_rejected(monkeypatch, "1m")


def test_interval_rejects_5m(monkeypatch) -> None:
    assert_interval_rejected(monkeypatch, "5m")


def test_interval_rejects_1h(monkeypatch) -> None:
    assert_interval_rejected(monkeypatch, "1h")


def test_public_market_dry_run_no_api_key_allowed(monkeypatch) -> None:
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("LIVE_TRADING", "false")
    monkeypatch.setenv("PUBLIC_MARKET_DRY_RUN", "true")
    monkeypatch.setenv("BINANCE_API_KEY", "")
    monkeypatch.setenv("BINANCE_API_SECRET", "")
    settings = load_settings()
    assert settings.public_market_dry_run is True
    assert settings.dry_run is True
    assert settings.live_trading is False
    assert settings.binance_interval == "15m"
