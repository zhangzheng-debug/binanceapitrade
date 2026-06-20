from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "deploy" / "systemd" / "ethusdc-pivot-bot-live-strategy.user.service"
INSTALL_SCRIPT = ROOT / "scripts" / "install_final_live_strategy_user_service.sh"
START_SCRIPT = ROOT / "scripts" / "start_final_live_strategy_user_service.sh"
STATUS_SCRIPT = ROOT / "scripts" / "status_final_live_strategy_user_service.sh"
STOP_SCRIPT = ROOT / "scripts" / "stop_final_live_strategy_user_service.sh"
RUN_SCRIPT = ROOT / "scripts" / "run_final_live_strategy.sh"


def test_final_live_unit_is_user_level_and_requires_final_gate() -> None:
    text = UNIT.read_text(encoding="utf-8")

    assert "Environment=I_APPROVE_FINAL_LIVE_STRATEGY_START=YES" in text
    assert "EnvironmentFile=" not in text
    assert "ExecStart=%h/ethusdc-pivot-bot/scripts/run_final_live_strategy.sh" in text
    assert "Restart=on-failure" in text
    assert "RuntimeMaxSec=" not in text
    assert "WantedBy=default.target" in text
    assert "/etc/systemd" not in text


def test_final_live_install_script_enables_without_starting() -> None:
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "I_APPROVE_FINAL_LIVE_STRATEGY_USER_SERVICE" in text
    assert "$HOME/.config/systemd/user" in text
    assert "ethusdc-pivot-bot-live-strategy.service" in text
    assert "systemctl --user daemon-reload" in text
    assert "systemctl --user enable ethusdc-pivot-bot-live-strategy.service" in text
    assert "systemctl --user start" not in text
    assert "/etc/systemd" not in text


def test_final_live_start_script_runs_gates_before_start() -> None:
    text = START_SCRIPT.read_text(encoding="utf-8")

    assert "I_APPROVE_FINAL_LIVE_STRATEGY_START" in text
    assert "python scripts/scan_secrets.py" in text
    assert "python scripts/live_strategy_capability_audit.py" in text
    assert "python scripts/live_readiness_gate_report.py" in text
    assert "python scripts/final_live_start_gate.py" in text
    assert "systemctl --user start ethusdc-pivot-bot-live-strategy.service" in text


def test_final_live_run_script_uses_restart_safe_runtime_gates() -> None:
    text = RUN_SCRIPT.read_text(encoding="utf-8")

    assert "source .env.live.readonly" in text
    assert "python scripts/final_live_start_gate.py" not in text
    assert "python scripts/live_readiness_gate_report.py" not in text
    assert "python scripts/check_config.py" in text
    assert "export DRY_RUN=false" in text
    assert "export LIVE_TRADING=true" in text
    assert "export ORDER_MODE=account_equity_pct" in text
    assert "export POSITION_SIZE_PCT=200" in text
    assert 'export LIVE_STRATEGY_MAX_ENTRY_FILLS="${LIVE_STRATEGY_MAX_ENTRY_FILLS:-0}"' in text
    assert 'export LIVE_STRATEGY_RESUME_EXISTING_POSITION="${LIVE_STRATEGY_RESUME_EXISTING_POSITION:-true}"' in text
    assert "exec .venv/bin/python -m bot.main" in text


def test_final_live_status_and_stop_are_scoped_to_user_service() -> None:
    status = STATUS_SCRIPT.read_text(encoding="utf-8")
    stop = STOP_SCRIPT.read_text(encoding="utf-8")

    assert "systemctl --user status ethusdc-pivot-bot-live-strategy.service" in status
    assert "journalctl --user -u ethusdc-pivot-bot-live-strategy.service" in status
    assert "systemctl --user stop ethusdc-pivot-bot-live-strategy.service" in stop
    assert "systemctl stop" not in status
    assert "systemctl stop" not in stop
