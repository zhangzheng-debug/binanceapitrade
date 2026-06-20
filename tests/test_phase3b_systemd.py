import asyncio
import logging
from decimal import Decimal
from pathlib import Path

import pytest

from bot.binance_client import BinanceClient, LiveTradingDisabled
from bot.config import Settings
from bot.dry_run_exchange import DryRunExchange
from bot.models import OrderRequest, OrderType, Side, TimeInForce
from bot.phase3b_runtime import Phase3BRuntimeSummary, cancel_active_simulated_orders, write_runtime_summary


ROOT = Path(__file__).resolve().parents[1]
USER_UNIT = ROOT / "deploy" / "systemd" / "ethusdc-pivot-bot-dry-run.user.service"
INSTALL_SCRIPT = ROOT / "scripts" / "install_user_systemd_dry_run.sh"
STOP_SCRIPT = ROOT / "scripts" / "phase3b_user_service_stop.sh"
UNINSTALL_SCRIPT = ROOT / "scripts" / "phase3b_user_service_uninstall.sh"
PREPARE_6H_SCRIPT = ROOT / "scripts" / "phase3b_prepare_6h_user_service.sh"


def run(coro):
    return asyncio.run(coro)


def test_phase3b_bounded_runtime_config() -> None:
    settings = Settings(
        DRY_RUN=True,
        LIVE_TRADING=False,
        PUBLIC_MARKET_DRY_RUN=True,
        PUBLIC_MARKET_WS_ONLY=True,
        EXIT_AFTER_BOUNDED_RUNTIME=True,
        PHASE3B_BOUNDED_RUNTIME_SECONDS=3600,
        _env_file=None,
    )
    assert settings.exit_after_bounded_runtime is True
    assert settings.phase3b_bounded_runtime_seconds == 3600


def test_phase3b_bounded_runtime_rejected_live() -> None:
    with pytest.raises(Exception):
        Settings(
            DRY_RUN=False,
            LIVE_TRADING=True,
            BINANCE_API_KEY="key",
            BINANCE_API_SECRET="secret",
            EXIT_AFTER_BOUNDED_RUNTIME=True,
            _env_file=None,
        )


def test_phase3b_env_forces_15m() -> None:
    text = USER_UNIT.read_text(encoding="utf-8")
    assert "Environment=BINANCE_INTERVAL=15m" in text


def test_phase3b_user_unit_no_live() -> None:
    text = USER_UNIT.read_text(encoding="utf-8")
    assert "Environment=LIVE_TRADING=false" in text
    assert "LIVE_TRADING=true" not in text


def test_phase3b_user_unit_no_api_key_value() -> None:
    text = USER_UNIT.read_text(encoding="utf-8")
    assert "Environment=BINANCE_API_KEY=\n" in text
    assert "Environment=BINANCE_API_SECRET=\n" in text
    assert "APIKEY" not in text


def test_phase3b_user_unit_no_enable_instruction() -> None:
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "systemctl --user enable" not in text
    assert "Not enabling boot autostart." in text


def test_phase3b_scripts_require_approval_env() -> None:
    install_text = INSTALL_SCRIPT.read_text(encoding="utf-8")
    uninstall_text = UNINSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "I_APPROVE_PHASE3B_USER_SYSTEMD_DRY_RUN" in install_text
    assert "I_APPROVE_PHASE3B_USER_SYSTEMD_UNINSTALL" in uninstall_text


def test_runtime_summary_written(tmp_path: Path) -> None:
    summary = Phase3BRuntimeSummary()
    summary.kline_ws_connected_count = 1
    path = tmp_path / "phase3b_runtime_summary.json"
    payload = write_runtime_summary(summary, path, final_status="completed")
    assert path.exists()
    assert payload["final_status"] == "completed"
    assert payload["kline_ws_connected_count"] == 1


def test_runtime_summary_counts_ws_events() -> None:
    summary = Phase3BRuntimeSummary()
    summary.kline_ws_connected_count += 1
    summary.bookticker_ws_connected_count += 1
    summary.kline_unclosed_count += 3
    summary.kline_closed_count += 1
    summary.bookticker_update_count += 250
    summary.record_strategy_event("pivot_high_confirmed")
    summary.record_strategy_event("long_armed")
    assert summary.kline_ws_connected_count == 1
    assert summary.bookticker_ws_connected_count == 1
    assert summary.kline_unclosed_count == 3
    assert summary.kline_closed_count == 1
    assert summary.bookticker_update_count == 250
    assert summary.pivot_high_confirmed_count == 1
    assert summary.long_armed_count == 1


def test_shutdown_cancels_simulated_dry_orders() -> None:
    async def scenario():
        exchange = DryRunExchange()
        order = await exchange.place_limit_gtx(
            OrderRequest(
                symbol="ETHUSDC",
                side=Side.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("1"),
                price=Decimal("3500"),
                time_in_force=TimeInForce.GTX,
            )
        )
        summary = Phase3BRuntimeSummary()
        await cancel_active_simulated_orders(exchange, logging.getLogger("test"), summary, "ETHUSDC")
        return exchange.orders[order.order_id].status.value, summary.active_simulated_orders_cancelled_count

    status, cancelled_count = run(scenario())
    assert status == "CANCELED"
    assert cancelled_count == 1


def test_no_signed_order_in_phase3b_mode() -> None:
    settings = Settings(
        DRY_RUN=True,
        LIVE_TRADING=False,
        PUBLIC_MARKET_DRY_RUN=True,
        PUBLIC_MARKET_WS_ONLY=True,
        EXIT_AFTER_BOUNDED_RUNTIME=True,
        _env_file=None,
    )
    client = BinanceClient(settings)
    with pytest.raises(LiveTradingDisabled):
        run(client.get_open_orders("ETHUSDC"))


def test_phase3b_service_runtime_max_sec_documented() -> None:
    text = USER_UNIT.read_text(encoding="utf-8")
    assert "RuntimeMaxSec=3700" in text


def test_phase3b_stop_script_only_user_service() -> None:
    text = STOP_SCRIPT.read_text(encoding="utf-8")
    assert "systemctl --user stop ethusdc-pivot-bot-dry-run.service" in text
    assert " kill " not in text
    assert "pkill" not in text


def test_phase3b_uninstall_script_no_system_wide() -> None:
    text = UNINSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "systemctl --user" in text
    assert "/etc/systemd" not in text
    assert "sudo" not in text


def test_phase3b_prepare_6h_script_requires_approval_and_does_not_start() -> None:
    text = PREPARE_6H_SCRIPT.read_text(encoding="utf-8")
    assert "I_APPROVE_PHASE3B_6H_PREPARE" in text
    assert "PHASE3B_BOUNDED_RUNTIME_SECONDS=21600" in text
    assert "RuntimeMaxSec=21700" in text
    executable_lines = "\n".join(line for line in text.splitlines() if not line.strip().startswith("echo"))
    assert "systemctl --user start" not in executable_lines
    assert "systemctl --user enable" not in text
