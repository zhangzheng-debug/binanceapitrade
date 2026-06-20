from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bot.config import ConfigError, Settings


class SafetyError(RuntimeError):
    """Raised when a runtime mode violates a trading safety rule."""


class SignedOrderForbiddenInDryRun(SafetyError):
    """Raised when a signed/account/order endpoint is reached in dry-run."""


class LiveTradingRejected(SafetyError):
    """Raised when LIVE_TRADING is not ready for startup."""


def assert_no_live_trading(settings: Settings) -> None:
    if settings.live_trading:
        raise LiveTradingRejected("LIVE_TRADING=true is not allowed in this phase")


def assert_no_signed_order_allowed(settings: Settings) -> None:
    if settings.dry_run or settings.public_market_ws_only or not settings.live_trading:
        raise SignedOrderForbiddenInDryRun(
            "signed/account/order endpoints are forbidden unless LIVE_TRADING=true and DRY_RUN=false"
        )


def assert_public_ws_only_dry_run_safe(settings: Settings) -> None:
    if not settings.dry_run:
        raise ConfigError("PUBLIC_MARKET_WS_ONLY requires DRY_RUN=true")
    if settings.live_trading:
        raise ConfigError("PUBLIC_MARKET_WS_ONLY is forbidden when LIVE_TRADING=true")
    if not settings.public_market_dry_run:
        raise ConfigError("PUBLIC_MARKET_WS_ONLY must run under PUBLIC_MARKET_DRY_RUN=true")
    if not settings.public_market_ws_only:
        raise ConfigError("PUBLIC_MARKET_WS_ONLY=true is required for this dry-run mode")
    if settings.binance_api_key or settings.binance_api_secret:
        raise ConfigError("PUBLIC_MARKET_WS_ONLY dry-run must not use Binance API credentials")


def assert_live_ready_or_raise(settings: Settings, filters: Any | None, connectivity: Mapping[str, Any] | None) -> None:
    if not settings.live_trading:
        raise LiveTradingRejected("LIVE_TRADING=true is required for live readiness checks")
    if settings.dry_run:
        raise LiveTradingRejected("LIVE_TRADING=true cannot run with DRY_RUN=true")
    if settings.public_market_ws_only:
        raise LiveTradingRejected("WebSocket-only public market mode cannot be used for live trading")
    if not settings.binance_api_key or not settings.binance_api_secret:
        raise LiveTradingRejected("live trading requires API credentials")

    if filters is None:
        raise LiveTradingRejected("live trading requires fresh REST exchangeInfo filters")
    if getattr(filters, "dry_run_only", False):
        raise LiveTradingRejected("cached dry-run filters cannot be used for live trading")
    if getattr(filters, "safe_for_live", False) is not True:
        raise LiveTradingRejected("filters are not marked safe for live trading")

    connectivity = connectivity or {}
    if settings.require_rest_exchange_info_for_live and not connectivity.get("exchange_info_rest_ok", False):
        raise LiveTradingRejected("live trading requires successful REST exchangeInfo")
    if not connectivity.get("signed_rest_validated", False):
        raise LiveTradingRejected("live trading requires signed REST validation")


def redact_secret(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""
    if len(text) <= 4:
        return "***"
    return f"{text[:2]}...{text[-2:]}"


SECRET_KEY_FRAGMENTS = ("key", "secret", "token", "password", "private", "webhook")


def redact_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in mapping.items():
        lowered = key.lower()
        if any(fragment in lowered for fragment in SECRET_KEY_FRAGMENTS):
            redacted[key] = redact_secret(value)
        else:
            redacted[key] = value
    return redacted
