import pytest

from bot.config import ConfigError, Settings, load_settings


def test_interval_allows_15m_and_1h() -> None:
    settings = Settings(BINANCE_INTERVAL="15m", _env_file=None)
    assert settings.binance_interval == "15m"
    btc_settings = Settings(BINANCE_SYMBOL="BTCUSDC", BINANCE_INTERVAL="1h", _env_file=None)
    assert btc_settings.binance_symbol == "BTCUSDC"
    assert btc_settings.binance_interval == "1h"
    xrp_settings = Settings(BINANCE_SYMBOL="XRPUSDC", BINANCE_INTERVAL="1h", _env_file=None)
    assert xrp_settings.binance_symbol == "XRPUSDC"
    assert xrp_settings.binance_interval == "1h"


def assert_interval_rejected(monkeypatch, interval: str) -> None:
    monkeypatch.setenv("BINANCE_INTERVAL", interval)
    with pytest.raises(ConfigError, match="Supported BINANCE_INTERVAL values"):
        load_settings()


def test_interval_rejects_1m(monkeypatch) -> None:
    assert_interval_rejected(monkeypatch, "1m")


def test_interval_rejects_5m(monkeypatch) -> None:
    assert_interval_rejected(monkeypatch, "5m")


def test_symbol_rejects_unsupported(monkeypatch) -> None:
    monkeypatch.setenv("BINANCE_SYMBOL", "ETHUSDT")
    with pytest.raises(ConfigError, match="Supported BINANCE_SYMBOL values"):
        load_settings()


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
