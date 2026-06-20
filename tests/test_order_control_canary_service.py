from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "deploy" / "systemd" / "ethusdc-pivot-bot-order-control-canary.user.service"
INSTALL_SCRIPT = ROOT / "scripts" / "install_order_control_canary_user_service.sh"
START_SCRIPT = ROOT / "scripts" / "start_order_control_canary_user_service.sh"


def test_order_control_canary_unit_is_one_shot_and_not_autostarted() -> None:
    text = UNIT.read_text(encoding="utf-8")
    assert "Type=oneshot" in text
    assert "Restart=no" in text
    assert "WantedBy=" not in text
    assert "[Install]" not in text
    assert "systemctl" not in text


def test_order_control_canary_unit_keeps_live_strategy_disabled() -> None:
    text = UNIT.read_text(encoding="utf-8")
    assert "Environment=LIVE_TRADING=false" in text
    assert "Environment=DRY_RUN=false" in text
    assert "Environment=PUBLIC_MARKET_DRY_RUN=false" in text
    assert "python scripts/live_canary_order_control.py" in text
    assert "python -m bot.main" not in text


def test_order_control_canary_unit_loads_secret_env_without_embedding_secret() -> None:
    text = UNIT.read_text(encoding="utf-8")
    assert "EnvironmentFile=%h/ethusdc-pivot-bot/.env.live.readonly" in text
    assert "BINANCE_API_KEY=" not in text
    assert "BINANCE_API_SECRET=" not in text


def test_order_control_canary_scripts_require_approval_and_do_not_enable() -> None:
    install_text = INSTALL_SCRIPT.read_text(encoding="utf-8")
    start_text = START_SCRIPT.read_text(encoding="utf-8")
    assert "I_APPROVE_ORDER_CONTROL_CANARY_USER_SERVICE" in install_text
    assert "I_APPROVE_ORDER_CONTROL_CANARY_START" in start_text
    assert "systemctl --user enable" not in install_text
    assert "systemctl --user enable" not in start_text


def test_hedge_mode_canary_requires_separate_start_env() -> None:
    unit_text = UNIT.read_text(encoding="utf-8")
    start_text = START_SCRIPT.read_text(encoding="utf-8")
    assert "I_APPROVE_HEDGE_MODE_ORDER_CONTROL_CANARY=YES" not in unit_text
    assert "I_APPROVE_HEDGE_MODE_ORDER_CONTROL_CANARY" in start_text
