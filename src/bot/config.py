from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(ValueError):
    """Raised when runtime configuration is unsafe."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    dry_run: bool = Field(default=True, alias="DRY_RUN")
    live_trading: bool = Field(default=False, alias="LIVE_TRADING")
    public_market_dry_run: bool = Field(default=False, alias="PUBLIC_MARKET_DRY_RUN")
    public_market_dry_run_seconds: int = Field(default=20, alias="PUBLIC_MARKET_DRY_RUN_SECONDS", ge=1)
    public_market_ws_only: bool = Field(default=False, alias="PUBLIC_MARKET_WS_ONLY")
    allow_cached_exchange_filters_in_dry_run: bool = Field(
        default=False,
        alias="ALLOW_CACHED_EXCHANGE_FILTERS_IN_DRY_RUN",
    )
    cached_exchange_filters_path: Path = Field(
        default=Path("./config/exchange_filters_ETHUSDC.json"),
        alias="CACHED_EXCHANGE_FILTERS_PATH",
    )
    require_rest_exchange_info_for_live: bool = Field(
        default=True,
        alias="REQUIRE_REST_EXCHANGE_INFO_FOR_LIVE",
    )
    require_signed_rest_validation_for_testnet: bool = Field(
        default=True,
        alias="REQUIRE_SIGNED_REST_VALIDATION_FOR_TESTNET",
    )
    testnet_order_test: bool = Field(default=False, alias="TESTNET_ORDER_TEST")
    book_ticker_stale_seconds: Decimal = Field(default=Decimal("5"), alias="BOOK_TICKER_STALE_SECONDS")
    bookticker_log_mode: Literal["summary", "detail"] = Field(default="summary", alias="BOOKTICKER_LOG_MODE")
    bookticker_log_every_n: int = Field(default=2000, alias="BOOKTICKER_LOG_EVERY_N", ge=1)
    bookticker_summary_interval_seconds: int = Field(
        default=60,
        alias="BOOKTICKER_SUMMARY_INTERVAL_SECONDS",
        ge=1,
    )
    kline_log_unclosed_every_n: int = Field(default=200, alias="KLINE_LOG_UNCLOSED_EVERY_N", ge=1)
    log_raw_market_messages: bool = Field(default=False, alias="LOG_RAW_MARKET_MESSAGES")
    max_events_log_mb: int = Field(default=100, alias="MAX_EVENTS_LOG_MB", ge=1)
    warn_events_log_mb: int = Field(default=50, alias="WARN_EVENTS_LOG_MB", ge=1)
    max_bot_log_mb: int = Field(default=100, alias="MAX_BOT_LOG_MB", ge=1)
    warn_bot_log_mb: int = Field(default=50, alias="WARN_BOT_LOG_MB", ge=1)
    exit_after_bounded_runtime: bool = Field(default=False, alias="EXIT_AFTER_BOUNDED_RUNTIME")
    phase3b_bounded_runtime_seconds: int = Field(
        default=3600,
        alias="PHASE3B_BOUNDED_RUNTIME_SECONDS",
        ge=1,
    )
    phase_fast_smoke_seconds: int = Field(default=0, alias="PHASE_FAST_SMOKE_SECONDS", ge=0)

    binance_api_key: str = Field(default="", alias="BINANCE_API_KEY")
    binance_api_secret: str = Field(default="", alias="BINANCE_API_SECRET")

    binance_env: Literal["testnet", "mainnet"] = Field(default="testnet", alias="BINANCE_ENV")
    binance_symbol: str = Field(default="ETHUSDC", alias="BINANCE_SYMBOL")
    binance_interval: str = Field(default="15m", alias="BINANCE_INTERVAL")
    api_key_ip_whitelist_expected: str = Field(default="", alias="API_KEY_IP_WHITELIST_EXPECTED")
    strategy_variant: Literal["original_pivot_reversal", "safer_pivot_reversal"] = Field(
        default="original_pivot_reversal",
        alias="STRATEGY_VARIANT",
    )
    tie_break_mode: Literal["skip_ambiguous"] = Field(default="skip_ambiguous", alias="TIE_BREAK_MODE")

    left_bars: int = Field(default=4, alias="LEFT_BARS", ge=1)
    right_bars: int = Field(default=2, alias="RIGHT_BARS", ge=1)

    entry_chase_seconds: int = Field(default=60, alias="ENTRY_CHASE_SECONDS", ge=1)
    stop_chase_seconds: int = Field(default=30, alias="STOP_CHASE_SECONDS", ge=1)
    chase_interval_seconds: Decimal = Field(default=Decimal("1.0"), alias="CHASE_INTERVAL_SECONDS")
    partial_fill_accept_ratio: Decimal = Field(
        default=Decimal("0.95"),
        alias="PARTIAL_FILL_ACCEPT_RATIO",
        gt=Decimal("0"),
        le=Decimal("1"),
    )

    order_mode: Literal["fixed_qty", "fixed_notional", "account_equity_pct"] = Field(default="fixed_notional", alias="ORDER_MODE")
    fixed_qty: Decimal | None = Field(default=None, alias="FIXED_QTY")
    fixed_notional: Decimal | None = Field(default=Decimal("100"), alias="FIXED_NOTIONAL")
    position_size_pct: Decimal = Field(default=Decimal("200"), alias="POSITION_SIZE_PCT", gt=Decimal("0"))

    stop_loss_enabled: bool = Field(default=True, alias="STOP_LOSS_ENABLED")
    stop_loss_pct: Decimal = Field(default=Decimal("0.005"), alias="STOP_LOSS_PCT", gt=Decimal("0"))
    live_strategy_max_entry_fills: int = Field(default=1, alias="LIVE_STRATEGY_MAX_ENTRY_FILLS", ge=0)
    live_strategy_resume_existing_position: bool = Field(
        default=False,
        alias="LIVE_STRATEGY_RESUME_EXISTING_POSITION",
    )
    live_managed_position_marker_path: Path = Field(
        default=Path("./data/live_managed_position.json"),
        alias="LIVE_MANAGED_POSITION_MARKER_PATH",
    )

    take_profit_enabled: bool = Field(default=False, alias="TAKE_PROFIT_ENABLED")
    take_profit_pct: Decimal | None = Field(default=None, alias="TAKE_PROFIT_PCT")

    state_db_path: Path = Field(default=Path("./data/state.sqlite3"), alias="STATE_DB_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    auto_cancel_unknown_orders: bool = Field(default=False, alias="AUTO_CANCEL_UNKNOWN_ORDERS")
    require_manual_reconciliation_on_mismatch: bool = Field(
        default=True,
        alias="REQUIRE_MANUAL_RECONCILIATION_ON_MISMATCH",
    )

    alerts_enabled: bool = Field(default=False, alias="ALERTS_ENABLED")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    credit_expires_at: str = Field(default="2026-08-01", alias="CREDIT_EXPIRES_AT")

    @field_validator("binance_symbol")
    @classmethod
    def symbol_must_be_ethusdc(cls, value: str) -> str:
        normalized = value.upper()
        if normalized != "ETHUSDC":
            raise ConfigError("Initial release only supports BINANCE_SYMBOL=ETHUSDC")
        return normalized

    @field_validator("binance_interval")
    @classmethod
    def interval_must_be_15m(cls, value: str) -> str:
        normalized = value.strip()
        if normalized != "15m":
            raise ConfigError("Initial release only supports BINANCE_INTERVAL=15m")
        return normalized

    @field_validator("chase_interval_seconds")
    @classmethod
    def chase_interval_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ConfigError("CHASE_INTERVAL_SECONDS must be positive")
        return value

    @field_validator("book_ticker_stale_seconds")
    @classmethod
    def book_ticker_stale_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ConfigError("BOOK_TICKER_STALE_SECONDS must be positive")
        return value

    @field_validator("fixed_qty", "fixed_notional", "take_profit_pct", mode="before")
    @classmethod
    def empty_decimal_is_none(cls, value):
        if value == "":
            return None
        return value

    @model_validator(mode="after")
    def validate_safety(self) -> Settings:
        if self.live_trading and self.dry_run:
            raise ConfigError("LIVE_TRADING=true is mutually exclusive with DRY_RUN=true")
        if self.public_market_dry_run and not self.dry_run:
            raise ConfigError("PUBLIC_MARKET_DRY_RUN=true requires DRY_RUN=true")
        if self.public_market_dry_run and self.live_trading:
            raise ConfigError("PUBLIC_MARKET_DRY_RUN=true cannot bypass LIVE_TRADING safety checks")
        if self.public_market_ws_only and not self.dry_run:
            raise ConfigError("PUBLIC_MARKET_WS_ONLY=true requires DRY_RUN=true")
        if self.public_market_ws_only and self.live_trading:
            raise ConfigError("PUBLIC_MARKET_WS_ONLY=true is only allowed for dry-run, never live")
        if self.exit_after_bounded_runtime and self.live_trading:
            raise ConfigError("EXIT_AFTER_BOUNDED_RUNTIME=true is forbidden with LIVE_TRADING=true")
        if self.exit_after_bounded_runtime and not self.dry_run:
            raise ConfigError("EXIT_AFTER_BOUNDED_RUNTIME=true requires DRY_RUN=true")
        if self.phase_fast_smoke_seconds and not self.exit_after_bounded_runtime:
            raise ConfigError("PHASE_FAST_SMOKE_SECONDS requires EXIT_AFTER_BOUNDED_RUNTIME=true")
        if self.phase_fast_smoke_seconds and self.live_trading:
            raise ConfigError("PHASE_FAST_SMOKE_SECONDS is forbidden with LIVE_TRADING=true")
        if self.warn_events_log_mb > self.max_events_log_mb:
            raise ConfigError("WARN_EVENTS_LOG_MB must be less than or equal to MAX_EVENTS_LOG_MB")
        if self.warn_bot_log_mb > self.max_bot_log_mb:
            raise ConfigError("WARN_BOT_LOG_MB must be less than or equal to MAX_BOT_LOG_MB")
        if self.live_trading and self.allow_cached_exchange_filters_in_dry_run:
            raise ConfigError("cached exchange filters are dry-run only and cannot be enabled for live")
        if self.testnet_order_test and self.allow_cached_exchange_filters_in_dry_run:
            raise ConfigError("TESTNET_ORDER_TEST=true cannot use cached exchange filters by default")
        if self.live_trading and (not self.binance_api_key or not self.binance_api_secret):
            raise ConfigError("LIVE_TRADING=true requires BINANCE_API_KEY and BINANCE_API_SECRET")
        if self.strategy_variant != "original_pivot_reversal":
            raise ConfigError("STRATEGY_VARIANT=safer_pivot_reversal is deprecated; use original_pivot_reversal")
        if self.stop_chase_seconds > self.entry_chase_seconds:
            raise ConfigError("STOP_CHASE_SECONDS must not exceed ENTRY_CHASE_SECONDS in the initial release")
        if self.order_mode == "fixed_notional":
            if self.fixed_notional is None or self.fixed_notional <= 0:
                raise ConfigError("FIXED_NOTIONAL must be greater than zero when ORDER_MODE=fixed_notional")
        if self.order_mode == "fixed_qty":
            if self.fixed_qty is None or self.fixed_qty <= 0:
                raise ConfigError("FIXED_QTY must be greater than zero when ORDER_MODE=fixed_qty")
        if self.order_mode == "account_equity_pct" and self.position_size_pct > Decimal("200"):
            raise ConfigError("POSITION_SIZE_PCT must not exceed 200 in the initial release")
        return self

    @property
    def rest_base_url(self) -> str:
        if self.binance_env == "testnet":
            return "https://testnet.binancefuture.com"
        return "https://fapi.binance.com"

    @property
    def ws_market_base_url(self) -> str:
        if self.binance_env == "testnet":
            return "wss://stream.binancefuture.com/market"
        return "wss://fstream.binance.com/market"

    @property
    def ws_public_base_url(self) -> str:
        if self.binance_env == "testnet":
            return "wss://stream.binancefuture.com/public"
        return "wss://fstream.binance.com/public"

    def safe_summary(self) -> dict[str, str | bool | int]:
        return {
            "dry_run": self.dry_run,
            "live_trading": self.live_trading,
            "public_market_dry_run": self.public_market_dry_run,
            "public_market_dry_run_seconds": self.public_market_dry_run_seconds,
            "public_market_ws_only": self.public_market_ws_only,
            "allow_cached_exchange_filters_in_dry_run": self.allow_cached_exchange_filters_in_dry_run,
            "cached_exchange_filters_path": str(self.cached_exchange_filters_path),
            "require_rest_exchange_info_for_live": self.require_rest_exchange_info_for_live,
            "require_signed_rest_validation_for_testnet": self.require_signed_rest_validation_for_testnet,
            "testnet_order_test": self.testnet_order_test,
            "book_ticker_stale_seconds": str(self.book_ticker_stale_seconds),
            "bookticker_log_mode": self.bookticker_log_mode,
            "bookticker_log_every_n": self.bookticker_log_every_n,
            "bookticker_summary_interval_seconds": self.bookticker_summary_interval_seconds,
            "kline_log_unclosed_every_n": self.kline_log_unclosed_every_n,
            "log_raw_market_messages": self.log_raw_market_messages,
            "max_events_log_mb": self.max_events_log_mb,
            "warn_events_log_mb": self.warn_events_log_mb,
            "max_bot_log_mb": self.max_bot_log_mb,
            "warn_bot_log_mb": self.warn_bot_log_mb,
            "exit_after_bounded_runtime": self.exit_after_bounded_runtime,
            "phase3b_bounded_runtime_seconds": self.phase3b_bounded_runtime_seconds,
            "phase_fast_smoke_seconds": self.phase_fast_smoke_seconds,
            "binance_env": self.binance_env,
            "binance_symbol": self.binance_symbol,
            "binance_interval": self.binance_interval,
            "api_key_ip_whitelist_expected": self.api_key_ip_whitelist_expected,
            "strategy_variant": self.strategy_variant,
            "tie_break_mode": self.tie_break_mode,
            "entry_chase_seconds": self.entry_chase_seconds,
            "stop_chase_seconds": self.stop_chase_seconds,
            "order_mode": self.order_mode,
            "fixed_notional": str(self.fixed_notional) if self.fixed_notional is not None else "",
            "fixed_qty": str(self.fixed_qty) if self.fixed_qty is not None else "",
            "position_size_pct": str(self.position_size_pct),
            "live_strategy_max_entry_fills": self.live_strategy_max_entry_fills,
            "live_strategy_resume_existing_position": self.live_strategy_resume_existing_position,
            "live_managed_position_marker_path": str(self.live_managed_position_marker_path),
            "has_api_key": bool(self.binance_api_key),
            "has_api_secret": bool(self.binance_api_secret),
            "state_db_path": str(self.state_db_path),
            "credit_expires_at": self.credit_expires_at,
        }


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc
