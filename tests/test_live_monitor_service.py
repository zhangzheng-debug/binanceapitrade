from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "deploy" / "systemd" / "ethusdc-pivot-bot-live-monitor.user.service"
TIMER = ROOT / "deploy" / "systemd" / "ethusdc-pivot-bot-live-monitor.user.timer"
RUN_SCRIPT = ROOT / "scripts" / "run_live_monitor_status.sh"
INSTALL_SCRIPT = ROOT / "scripts" / "install_live_monitor_user_timer.sh"


def test_live_monitor_timer_is_user_level_and_periodic() -> None:
    text = TIMER.read_text(encoding="utf-8")

    assert "OnCalendar=*:0/15" in text
    assert "Persistent=true" in text
    assert "WantedBy=timers.target" in text


def test_live_monitor_service_is_readonly_status_writer() -> None:
    text = SERVICE.read_text(encoding="utf-8")

    assert "Type=oneshot" in text
    assert "ExecStart=%h/ethusdc-pivot-bot/scripts/run_live_monitor_status.sh" in text
    assert "Restart=" not in text


def test_live_monitor_run_script_does_not_manage_strategy_service_or_place_orders() -> None:
    text = RUN_SCRIPT.read_text(encoding="utf-8")

    assert "scripts/live_monitor_status.py" in text
    assert "systemctl --user restart" not in text
    assert "systemctl --user stop" not in text
    assert "systemctl --user start ethusdc-pivot-bot-live-strategy" not in text
    assert "POST /fapi/v1/order" not in text


def test_live_monitor_install_script_only_enables_monitor_timer() -> None:
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "ethusdc-pivot-bot-live-monitor.timer" in text
    assert "enable --now ethusdc-pivot-bot-live-monitor.timer" in text
    assert "ethusdc-pivot-bot-live-strategy.service" not in text
