from __future__ import annotations

import asyncio
import json
import logging
import time
from decimal import Decimal
from pathlib import Path

import httpx
import websockets

from bot.alerts import AlertManager
from bot.binance_client import BinanceClient
from bot.book_ticker_provider import WebSocketBookTickerProvider
from bot.book_ticker_stream import BookTickerStream
from bot.config import ConfigError, load_settings
from bot.dry_run_exchange import DryRunExchange
from bot.execution_maker_chaser import MakerChaser
from bot.exchange_filters import SymbolFilters, maker_price
from bot.live_strategy_runner import (
    account_equity_from_account_payload,
    require_final_live_strategy_start_approval,
    run_live_entry_canary_once,
    run_live_reduce_only_close_once,
    run_live_stop_once,
)
from bot.live_position_state import (
    assert_marker_matches_position,
    clear_managed_position_marker,
    load_managed_position_marker,
    write_managed_position_marker,
)
from bot.logging_config import configure_logging, log_event
from bot.market_log_control import MarketLogControl
from bot.market_data import LOCKED_STREAM_NAME, candle_from_kline_payload, kline_ws_url, stream_closed_klines
from bot.models import Position, PositionSide, Side, StrategyEvent, StrategySignalSide
from bot.phase_fast_runtime import PhaseFastRuntimeSummary, apply_log_size_status, mirror_fast_runtime_summary
from bot.phase3b_runtime import (
    cancel_active_simulated_orders,
    write_runtime_summary,
)
from bot.reconciliation import reconcile
from bot.risk_manager import RiskError, RiskManager
from bot.safety import LiveTradingRejected, assert_public_ws_only_dry_run_safe
from bot.state_store import StateStore
from bot.strategy_pivot import PivotReversalStrategy
from bot.trigger_monitor import LivePriceUpdate, TriggerMonitor


async def async_main() -> int:
    settings = load_settings()
    configure_logging(
        settings.log_level,
        log_dir=settings.log_dir,
        max_bot_log_mb=settings.max_bot_log_mb,
        max_events_log_mb=settings.max_events_log_mb,
    )
    logger = logging.getLogger("bot.main")
    alerts = AlertManager(enabled=settings.alerts_enabled)

    log_event(logger, "config_loaded", **settings.safe_summary())
    if settings.dry_run:
        log_event(logger, "dry_run_enabled", symbol=settings.binance_symbol)
    if settings.live_trading:
        log_event(logger, "live_trading_requested", symbol=settings.binance_symbol)
        await alerts.alert("live bot started", "LIVE_TRADING=true was requested")

    store = StateStore(settings.state_db_path)
    store.initialize()

    if settings.live_trading:
        await run_live_strategy(settings, logger, alerts=alerts)
        return 0

    exchange = DryRunExchange(symbol=settings.binance_symbol)
    filters = SymbolFilters.ethusdc_test_defaults()
    local_position = Position(symbol=settings.binance_symbol)
    report = reconcile(
        dry_run=settings.dry_run,
        local_position=local_position,
        exchange_position=await exchange.get_position(settings.binance_symbol),
        open_orders=await exchange.get_open_orders(settings.binance_symbol),
        auto_cancel_unknown_orders=settings.auto_cancel_unknown_orders,
    )
    store.record_event("startup_reconciliation", "reconciliation_ok" if report.ok else "reconciliation_mismatch", {"message": report.message})
    log_event(logger, "reconciliation_ok" if report.ok else "reconciliation_mismatch", message=report.message)

    if settings.public_market_dry_run:
        await run_public_market_dry_run(settings, logger, exchange=exchange)
        return 0

    log_event(
        logger,
        "bot_started",
        mode="dry_run" if settings.dry_run else "live",
        symbol=settings.binance_symbol,
        tick_size=str(filters.tick_size),
        step_size=str(filters.step_size),
        fixed_notional=str(settings.fixed_notional or Decimal("0")),
    )
    return 0


async def run_live_strategy(settings, logger: logging.Logger, *, alerts: AlertManager | None = None, client: BinanceClient | None = None) -> None:
    require_final_live_strategy_start_approval()
    owns_client = client is None
    client = client or BinanceClient(settings)
    book_stream: BookTickerStream | None = None
    book_task: asyncio.Task | None = None
    entry_task: asyncio.Task | None = None
    stop_task: asyncio.Task | None = None
    position = Position(settings.binance_symbol)
    live_entry_fill_count = 0
    risk = RiskManager(settings.stop_loss_pct, stop_loss_enabled=settings.stop_loss_enabled)
    try:
        exchange_info = await client.exchange_info()
        filters = SymbolFilters.from_exchange_info(exchange_info, settings.binance_symbol)
        if filters.dry_run_only or not filters.safe_for_live:
            raise ConfigError("live strategy requires REST exchangeInfo filters safe_for_live=true")
        if await client.position_mode_dual_side():
            raise LiveTradingRejected("final live strategy requires Binance Futures One-way Position Mode")
        open_orders = await client.get_open_orders(settings.binance_symbol)
        if open_orders:
            raise LiveTradingRejected("final live strategy requires zero open orders at startup")
        position = await client.get_position(settings.binance_symbol)
        if not position.is_flat:
            if not settings.live_strategy_resume_existing_position:
                raise LiveTradingRejected("final live strategy must start flat; existing positions need manual handling")
            marker = load_managed_position_marker(settings.live_managed_position_marker_path)
            if marker is None:
                raise LiveTradingRejected("managed position resume requires a local managed-position marker")
            assert_marker_matches_position(marker, position)
            live_entry_fill_count = 1
            log_event(
                logger,
                "live_strategy_resumed_managed_position",
                symbol=position.symbol,
                side=position.side.value,
                quantity=str(position.quantity),
                entry_price=str(position.entry_price) if position.entry_price is not None else "",
                marker_signal_id=marker.signal_id,
            )
        else:
            clear_managed_position_marker(settings.live_managed_position_marker_path)
        account_equity = account_equity_from_account_payload(await client.account())
        log_event(
            logger,
            "live_strategy_started",
            symbol=settings.binance_symbol,
            interval=settings.binance_interval,
            filter_source=filters.source.value,
            position_size_pct=str(settings.position_size_pct),
            account_equity=str(account_equity),
        )

        strategy = PivotReversalStrategy(settings.left_bars, settings.right_bars, tick_size=filters.tick_size)
        trigger_monitor = TriggerMonitor(strategy, tie_break_mode=settings.tie_break_mode)

        def active_entry_chase() -> bool:
            return entry_task is not None and not entry_task.done()

        def active_stop_chase() -> bool:
            return stop_task is not None and not stop_task.done()

        def position_signal_side() -> StrategySignalSide | None:
            if position.side == PositionSide.LONG:
                return StrategySignalSide.LONG
            if position.side == PositionSide.SHORT:
                return StrategySignalSide.SHORT
            return None

        async def run_live_stop(signal_id: str) -> None:
            nonlocal position
            result = await run_live_stop_once(
                settings=settings,
                exchange=client,
                filters=filters,
                position=position,
                signal_id=signal_id,
                logger=logger,
            )
            log_event(
                logger,
                "live_stop_chase_finished",
                signal_id=result.signal_id,
                side=result.side,
                success=result.chase_success,
                reason=result.chase_reason,
                filled_qty=result.filled_qty,
                market_order_id=result.market_order_id or "",
            )
            if result.chase_success:
                position = Position(settings.binance_symbol)
                clear_managed_position_marker(settings.live_managed_position_marker_path)

        async def run_live_entry(event: StrategyEvent) -> None:
            nonlocal live_entry_fill_count, position
            risk.assert_can_start_entry(position, active_entry=False, active_stop=active_stop_chase())
            if event.side is not None:
                risk.assert_signal_allowed(event.side, position)
            refreshed_equity = account_equity_from_account_payload(await client.account())
            result = await run_live_entry_canary_once(
                settings=settings,
                exchange=client,
                filters=filters,
                account_equity=refreshed_equity,
                event=event,
                logger=logger,
            )
            log_event(
                logger,
                "live_entry_chase_finished",
                signal_id=result.signal_id,
                side=result.side,
                success=result.chase_success,
                reason=result.chase_reason,
                filled_qty=result.filled_qty,
                quantity=result.quantity,
                actual_notional=result.actual_notional,
            )
            if result.chase_success and Decimal(result.filled_qty) > 0:
                live_entry_fill_count += 1
                side = PositionSide.LONG if event.side == StrategySignalSide.LONG else PositionSide.SHORT
                entry_price = Decimal(result.avg_price) if result.avg_price is not None else event.price
                position = Position(settings.binance_symbol, side, Decimal(result.filled_qty), entry_price)
                write_managed_position_marker(settings.live_managed_position_marker_path, position, signal_id=result.signal_id)
                if live_entry_fill_limit_reached(settings.live_strategy_max_entry_fills, live_entry_fill_count):
                    log_event(
                        logger,
                        "live_strategy_entry_fill_limit_reached",
                        entry_fill_count=live_entry_fill_count,
                        max_entry_fills=settings.live_strategy_max_entry_fills,
                    )

        async def run_live_reversal(event: StrategyEvent) -> None:
            nonlocal position
            if event.side is None or event.signal_id is None:
                log_event(logger, "live_reversal_blocked_incomplete_signal")
                return
            original_position = position
            close_signal_id = f"reverse_close_{event.signal_id}"
            log_event(
                logger,
                "live_reversal_close_started",
                signal_id=event.signal_id,
                from_side=original_position.side.value,
                to_side=event.side.value,
                quantity=str(original_position.quantity),
            )
            close_result = await run_live_reduce_only_close_once(
                settings=settings,
                exchange=client,
                filters=filters,
                position=original_position,
                signal_id=close_signal_id,
                logger=logger,
            )
            log_event(
                logger,
                "live_reversal_close_finished",
                signal_id=event.signal_id,
                side=close_result.side,
                success=close_result.chase_success,
                reason=close_result.chase_reason,
                order_id=close_result.order_id or "",
                filled_qty=close_result.filled_qty,
            )
            position = await client.get_position(settings.binance_symbol)
            if not position.is_flat:
                write_managed_position_marker(settings.live_managed_position_marker_path, position, signal_id=event.signal_id)
                log_event(
                    logger,
                    "live_reversal_blocked_close_incomplete",
                    signal_id=event.signal_id,
                    remaining_side=position.side.value,
                    remaining_quantity=str(position.quantity),
                )
                return
            clear_managed_position_marker(settings.live_managed_position_marker_path)
            await run_live_entry(event)

        async def handle_strategy_events(events: list[StrategyEvent]) -> None:
            nonlocal entry_task
            for event in events:
                log_event(
                    logger,
                    event.event_type,
                    signal_id=event.signal_id or "",
                    side=event.side.value if event.side is not None else "",
                    price=str(event.price) if event.price is not None else "",
                    candle_time=event.candle_time,
                )
                if event.event_type != "breakout_triggered_original_pine":
                    continue
                if event.signal_id is None:
                    log_event(logger, "live_trigger_blocked_missing_signal_id")
                    continue
                if event.side is None:
                    log_event(logger, "live_trigger_blocked_missing_side", signal_id=event.signal_id)
                    continue
                if live_entry_fill_limit_reached(settings.live_strategy_max_entry_fills, live_entry_fill_count):
                    log_event(
                        logger,
                        "live_trigger_blocked_entry_fill_limit",
                        signal_id=event.signal_id,
                        entry_fill_count=live_entry_fill_count,
                        max_entry_fills=settings.live_strategy_max_entry_fills,
                    )
                    continue
                if active_entry_chase():
                    log_event(logger, "live_trigger_blocked_active_chase", signal_id=event.signal_id)
                    continue
                if active_stop_chase():
                    log_event(logger, "live_trigger_blocked_active_close", signal_id=event.signal_id)
                    continue
                try:
                    risk.assert_signal_allowed(event.side, position)
                except RiskError as exc:
                    log_event(logger, "live_trigger_blocked_risk", signal_id=event.signal_id, reason=str(exc))
                    continue
                if position.is_flat:
                    entry_task = asyncio.create_task(run_live_entry(event))
                else:
                    entry_task = asyncio.create_task(run_live_reversal(event))

        async def update_live_bookticker(snapshot) -> None:
            nonlocal stop_task
            events = trigger_monitor.on_live_price_update(
                LivePriceUpdate(
                    symbol=snapshot.symbol,
                    event_time=snapshot.event_time,
                    best_bid=snapshot.best_bid_price,
                    best_ask=snapshot.best_ask_price,
                    source="bookTicker",
                ),
                active_entry_chase=active_entry_chase(),
                open_position_side=position_signal_side(),
            )
            await handle_strategy_events(events)
            if not settings.stop_loss_enabled or position.is_flat or active_stop_chase():
                return
            observed_price = snapshot.best_bid_price if position.side == PositionSide.LONG else snapshot.best_ask_price
            if risk.stop_triggered(position, observed_price):
                stop_signal = f"stop_{position.side.value.lower()}_{snapshot.event_time or 0}"
                log_event(logger, "live_stop_triggered", signal_id=stop_signal, side=position.side.value, observed_price=str(observed_price))
                stop_task = asyncio.create_task(run_live_stop(stop_signal))

        market_log = MarketLogControl(settings)
        book_stream = BookTickerStream(settings, logger, callback=update_live_bookticker, market_log_control=market_log)
        book_task = asyncio.create_task(book_stream.run())
        await book_stream.wait_for_first(20)

        async for candle in stream_closed_klines(settings, logger):
            events = strategy.on_candle(candle)
            await handle_strategy_events(events)
    finally:
        if entry_task is not None and not entry_task.done():
            entry_task.cancel()
        if stop_task is not None and not stop_task.done():
            stop_task.cancel()
        for task in (entry_task, stop_task):
            if task is not None:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if book_task is not None:
            if not book_task.done():
                book_task.cancel()
            try:
                await book_task
            except asyncio.CancelledError:
                pass
        if owns_client:
            await client.close()
        log_event(logger, "live_strategy_stopped", symbol=settings.binance_symbol)


def live_entry_fill_limit_reached(max_entry_fills: int, entry_fill_count: int) -> bool:
    return max_entry_fills > 0 and entry_fill_count >= max_entry_fills


async def run_live_stop(settings, logger: logging.Logger, *, exchange, filters: SymbolFilters, position: Position, signal_id: str):
    return await run_live_stop_once(
        settings=settings,
        exchange=exchange,
        filters=filters,
        position=position,
        signal_id=signal_id,
        logger=logger,
    )


async def run_public_market_dry_run(settings, logger: logging.Logger, exchange: DryRunExchange | None = None) -> None:
    if settings.public_market_ws_only:
        assert_public_ws_only_dry_run_safe(settings)
        log_event(logger, "ws_only_fallback_enabled", symbol=settings.binance_symbol)

    runtime_seconds = (
        settings.phase_fast_smoke_seconds or settings.phase3b_bounded_runtime_seconds
        if settings.exit_after_bounded_runtime
        else settings.public_market_dry_run_seconds
    )
    summary = PhaseFastRuntimeSummary()
    market_log = MarketLogControl(settings)
    final_status = "completed"

    log_event(
        logger,
        "public_market_dry_run_started",
        symbol=settings.binance_symbol,
        interval=settings.binance_interval,
        stream=LOCKED_STREAM_NAME,
        seconds=runtime_seconds,
        exit_after_bounded_runtime=settings.exit_after_bounded_runtime,
        phase_fast_smoke_seconds=settings.phase_fast_smoke_seconds,
    )
    client = BinanceClient(settings)
    book_stream: BookTickerStream | None = None
    book_task: asyncio.Task | None = None
    entry_task: asyncio.Task | None = None
    try:
        filters: SymbolFilters | None = None
        try:
            exchange_info = await client.exchange_info()
            filters = SymbolFilters.from_exchange_info(exchange_info, settings.binance_symbol)
            log_event(
                logger,
                "exchange_info_loaded",
                symbol=filters.symbol,
                tick_size=str(filters.tick_size),
                step_size=str(filters.step_size),
                min_qty=str(filters.min_qty),
                min_notional=str(filters.min_notional),
                filter_source=filters.source.value,
                safe_for_live=filters.safe_for_live,
                dry_run_only=filters.dry_run_only,
            )
        except Exception as exc:  # public probe should not block dry-run boot
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            if status_code == 451:
                log_event(
                    logger,
                    "rest_451_detected",
                    api="exchangeInfo",
                    classification="http_451_unavailable_for_legal_reasons_or_region_block",
                    action="report_only_no_bypass",
                )
            summary.api_error_count += 1
            log_event(logger, "api_error", api="exchangeInfo", error=exc.__class__.__name__, message=str(exc))
            if settings.allow_cached_exchange_filters_in_dry_run:
                filters = SymbolFilters.from_cached_file(
                    settings.cached_exchange_filters_path,
                    settings.binance_symbol,
                    live_trading=settings.live_trading,
                    testnet_order_test=settings.testnet_order_test,
                )
                log_event(
                    logger,
                    "exchange_info_loaded_from_cache",
                    symbol=filters.symbol,
                    tick_size=str(filters.tick_size),
                    step_size=str(filters.step_size),
                    min_qty=str(filters.min_qty),
                    min_notional=str(filters.min_notional),
                    filter_source=filters.source.value,
                    safe_for_live=filters.safe_for_live,
                    dry_run_only=filters.dry_run_only,
                    note=filters.note,
                )
            else:
                raise

        if filters is None:
            raise ConfigError("public market dry-run requires REST or cached exchange filters")

        strategy = PivotReversalStrategy(settings.left_bars, settings.right_bars, tick_size=filters.tick_size)
        trigger_monitor = TriggerMonitor(strategy, tie_break_mode=settings.tie_break_mode)

        def active_entry_chase() -> bool:
            return entry_task is not None and not entry_task.done()

        async def run_entry_chase(event: StrategyEvent) -> None:
            nonlocal entry_task
            if exchange is None:
                log_event(logger, "trigger_blocked_no_dry_run_exchange", signal_id=event.signal_id or "")
                return
            if event.signal_id is None or event.side is None or event.price is None:
                log_event(logger, "trigger_blocked_missing_event_fields")
                return
            if settings.order_mode == "account_equity_pct":
                log_event(
                    logger,
                    "trigger_blocked_account_equity_sizing_unavailable",
                    signal_id=event.signal_id,
                    position_size_pct=str(settings.position_size_pct),
                )
                summary.record_strategy_event("trigger_blocked_account_equity_sizing_unavailable")
                return
            side = Side.BUY if event.side == StrategySignalSide.LONG else Side.SELL
            notional = settings.fixed_notional or Decimal("100")
            quantity = settings.fixed_qty if settings.fixed_qty is not None else notional / event.price
            provider = WebSocketBookTickerProvider(book_stream, stale_seconds=float(settings.book_ticker_stale_seconds)) if book_stream is not None else None
            chaser = MakerChaser(exchange, filters, logger, book_ticker_provider=provider)
            summary.record_strategy_event("entry_chase_started")
            result = await chaser.chase_entry(
                signal_id=event.signal_id,
                side=side,
                quantity=quantity,
                max_seconds=settings.entry_chase_seconds,
                interval_seconds=settings.chase_interval_seconds,
                partial_accept_ratio=settings.partial_fill_accept_ratio,
            )
            if result.order_id:
                summary.simulated_entry_order_count += 1
            log_event(
                logger,
                "entry_chase_finished",
                signal_id=event.signal_id,
                success=result.success,
                reason=result.reason,
                filled_qty=str(result.filled_qty),
            )

        async def handle_strategy_events(events: list[StrategyEvent]) -> None:
            nonlocal entry_task
            for event in events:
                summary.record_strategy_event(event.event_type)
                log_event(
                    logger,
                    event.event_type,
                    signal_id=event.signal_id or "",
                    side=event.side.value if event.side is not None else "",
                    price=str(event.price) if event.price is not None else "",
                    candle_time=event.candle_time,
                )
                if event.event_type == "breakout_triggered_original_pine":
                    if active_entry_chase():
                        log_event(logger, "trigger_blocked_active_chase", signal_id=event.signal_id or "")
                        summary.record_strategy_event("trigger_blocked_active_chase")
                        continue
                    entry_task = asyncio.create_task(run_entry_chase(event))

        if settings.public_market_ws_only:
            async def update_bookticker_runtime(snapshot) -> None:
                ticker = snapshot.to_book_ticker()
                buy_price = maker_price(Side.BUY, ticker, filters)
                sell_price = maker_price(Side.SELL, ticker, filters)
                market_log.set_latest_maker_prices(buy_price, sell_price)
                summary.latest_bid = str(snapshot.best_bid_price)
                summary.latest_ask = str(snapshot.best_ask_price)
                summary.latest_maker_buy = str(buy_price)
                summary.latest_maker_sell = str(sell_price)
                events = trigger_monitor.on_live_price_update(
                    LivePriceUpdate(
                        symbol=snapshot.symbol,
                        event_time=snapshot.event_time,
                        best_bid=snapshot.best_bid_price,
                        best_ask=snapshot.best_ask_price,
                        source="bookTicker",
                    ),
                    active_entry_chase=active_entry_chase(),
                    has_open_position=False,
                )
                await handle_strategy_events(events)

            book_stream = BookTickerStream(
                settings,
                logger,
                callback=update_bookticker_runtime,
                market_log_control=market_log,
            )
            book_task = asyncio.create_task(book_stream.run(max_seconds=runtime_seconds))
            try:
                snapshot = await book_stream.wait_for_first(min(20, runtime_seconds))
                ticker = snapshot.to_book_ticker()
                buy_price = maker_price(Side.BUY, ticker, filters)
                sell_price = maker_price(Side.SELL, ticker, filters)
                summary.bid_ask_sample = {
                    "best_bid": str(snapshot.best_bid_price),
                    "best_ask": str(snapshot.best_ask_price),
                    "source": snapshot.source,
                }
                summary.maker_price_sample = {
                    "buy_maker_price": str(buy_price),
                    "sell_maker_price": str(sell_price),
                    "filter_source": filters.source.value,
                }
                log_event(
                    logger,
                    "maker_price_sample",
                    symbol=settings.binance_symbol,
                    source=snapshot.source,
                    best_bid=str(snapshot.best_bid_price),
                    best_ask=str(snapshot.best_ask_price),
                    buy_maker_price=str(buy_price),
                    sell_maker_price=str(sell_price),
                    filter_source=filters.source.value,
                )
            except Exception as exc:
                log_event(logger, "would_wait_for_book_ticker", error=exc.__class__.__name__, message=str(exc))
        else:
            try:
                ticker = await client.book_ticker(settings.binance_symbol)
                log_event(
                    logger,
                    "book_ticker_loaded",
                    symbol=str(ticker.get("symbol", "")),
                    bid_price=str(ticker.get("bidPrice", "")),
                    ask_price=str(ticker.get("askPrice", "")),
                )
            except Exception as exc:
                summary.api_error_count += 1
                log_event(logger, "api_error", api="bookTicker", error=exc.__class__.__name__, message=str(exc))

        try:
            if settings.exit_after_bounded_runtime:
                await observe_klines_for_phase3b(
                    settings,
                    logger,
                    strategy,
                    summary,
                    runtime_seconds,
                    market_log,
                    trigger_monitor,
                    handle_strategy_events,
                    active_entry_chase,
                )
                log_event(logger, "bounded_runtime_reached", seconds=runtime_seconds)
            else:
                async with asyncio.timeout(runtime_seconds):
                    async for candle in stream_closed_klines(settings, logger):
                        summary.kline_closed_count += 1
                        events = strategy.on_candle(candle)
                        summary.strategy_update_count += 1
                        await handle_strategy_events(events)
        except TimeoutError:
            log_event(
                logger,
                "public_market_dry_run_timeout",
                closed_candles=summary.kline_closed_count,
                message="no failure if no 15m candle closed during the bounded observation window",
            )
    finally:
        final_status = "completed"
        log_event(logger, "bot_stopping", reason="bounded_runtime" if settings.exit_after_bounded_runtime else "public_market_dry_run_finished")
        if entry_task is not None and not entry_task.done():
            try:
                await entry_task
            except asyncio.CancelledError:
                pass
        if book_task is not None:
            if not book_task.done():
                book_task.cancel()
            try:
                await book_task
            except asyncio.CancelledError:
                pass
        if book_stream is not None:
            summary.bookticker_ws_connected_count = book_stream.connected_count
            summary.bookticker_ws_reconnect_count = book_stream.reconnect_count
            summary.bookticker_update_count = book_stream.update_count
            summary.api_error_count += book_stream.error_count
            summary.update_from_market_log(market_log)
        if exchange is not None:
            await cancel_active_simulated_orders(exchange, logger, summary, settings.binance_symbol)
        await client.close()
        log_event(logger, "websocket_closed", stream=LOCKED_STREAM_NAME)
        if settings.public_market_ws_only:
            log_event(logger, "websocket_closed", stream="ethusdc@bookTicker")
        apply_log_size_status(summary, settings, logger)
        payload = write_runtime_summary(
            summary,
            Path("logs") / "phase3b_runtime_summary.json",
            final_status=final_status,
        )
        if settings.phase_fast_smoke_seconds:
            mirror_fast_runtime_summary(payload, Path("logs") / "fast_smoke_runtime_summary.json")
            log_event(logger, "fast_smoke_runtime_summary_written", path="logs/fast_smoke_runtime_summary.json")
        log_event(logger, "final_runtime_summary", **payload)
        log_event(logger, "public_market_dry_run_finished", stream=LOCKED_STREAM_NAME)


async def observe_klines_for_phase3b(
    settings,
    logger: logging.Logger,
    strategy: PivotReversalStrategy,
    summary: PhaseFastRuntimeSummary,
    runtime_seconds: int,
    market_log: MarketLogControl | None = None,
    trigger_monitor: TriggerMonitor | None = None,
    on_strategy_events=None,
    active_entry_chase=None,
) -> None:
    url = kline_ws_url(settings)
    deadline = time.monotonic() + runtime_seconds
    while time.monotonic() < deadline:
        log_event(logger, "websocket_connecting", url=url, stream=LOCKED_STREAM_NAME)
        try:
            async with websockets.connect(url, ping_interval=180, ping_timeout=600) as ws:
                summary.kline_ws_connected_count += 1
                log_event(logger, "websocket_connected", url=url, stream=LOCKED_STREAM_NAME)
                while time.monotonic() < deadline:
                    timeout = max(0.0, deadline - time.monotonic())
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    except TimeoutError:
                        return
                    payload = json.loads(message)
                    data = payload.get("data", payload)
                    kline = data.get("k", {})
                    if not kline:
                        continue
                    if trigger_monitor is not None and on_strategy_events is not None:
                        trigger_events = trigger_monitor.on_live_price_update(
                            LivePriceUpdate(
                                symbol=str(kline.get("s", "")).upper(),
                                event_time=int(kline["T"]) if kline.get("T") is not None else None,
                                latest_price=Decimal(str(kline["c"])) if kline.get("c") is not None else None,
                                high_so_far=Decimal(str(kline["h"])) if kline.get("h") is not None else None,
                                low_so_far=Decimal(str(kline["l"])) if kline.get("l") is not None else None,
                                source="kline_closed" if kline.get("x") else "kline_unclosed",
                            ),
                            active_entry_chase=active_entry_chase() if active_entry_chase is not None else False,
                            has_open_position=False,
                        )
                        await on_strategy_events(trigger_events)
                    if not kline.get("x"):
                        summary.kline_unclosed_count += 1
                        if market_log is None or market_log.should_log_unclosed_kline(summary.kline_unclosed_count):
                            log_event(
                                logger,
                                "kline_update_ignored_unclosed",
                                symbol=str(kline.get("s", "")).upper(),
                                interval=str(kline.get("i", "")),
                                close_time=kline.get("T"),
                                unclosed_count=summary.kline_unclosed_count,
                            )
                        continue
                    candle = candle_from_kline_payload(payload, logger)
                    if candle is None:
                        continue
                    summary.kline_closed_count += 1
                    events = strategy.on_candle(candle)
                    summary.strategy_update_count += 1
                    if on_strategy_events is not None:
                        await on_strategy_events(events)
                    else:
                        for event in events:
                            summary.record_strategy_event(event.event_type)
                            log_event(
                                logger,
                                event.event_type,
                                signal_id=event.signal_id,
                                price=str(event.price) if event.price is not None else "",
                                candle_time=event.candle_time,
                            )
        except websockets.ConnectionClosed as exc:
            summary.kline_ws_reconnect_count += 1
            log_event(logger, "websocket_disconnected", reason=str(exc))
            log_event(logger, "websocket_reconnecting", stream=LOCKED_STREAM_NAME)
        except OSError as exc:
            summary.kline_ws_reconnect_count += 1
            summary.api_error_count += 1
            log_event(logger, "websocket_disconnected", reason=str(exc))
            log_event(logger, "websocket_reconnecting", stream=LOCKED_STREAM_NAME)


def main() -> int:
    try:
        return asyncio.run(async_main())
    except ConfigError as exc:
        print(f"configuration error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
