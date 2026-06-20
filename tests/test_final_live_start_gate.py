from scripts.final_live_start_gate import evaluate


def ready_summary(**overrides):
    values = {
        "signed_readonly_preflight_go": True,
        "readonly_final_verdict": "SIGNED_READONLY_PREFLIGHT_GO",
        "order_control_final_verdict": "LIVE_ORDER_CONTROL_CANARY_GO",
        "final_gate": "READY_FOR_FINAL_LIVE_STRATEGY_DECISION",
        "exchange_info_source": "EXCHANGE_INFO_REST",
        "position_mode_dual_side": False,
        "final_open_orders_count": 0,
        "unexpected_fill": False,
        "order_mode": "account_equity_pct",
        "position_size_pct": "200",
        "next_required_human_instruction": "decide whether to start a tiny live strategy canary under a supervised service",
    }
    values.update(overrides)
    return values


def ready_config(**overrides):
    values = {
        "binance_symbol": "ETHUSDC",
        "binance_interval": "15m",
        "binance_env": "mainnet",
        "live_trading": False,
        "has_api_key": True,
        "has_api_secret": True,
    }
    values.update(overrides)
    return values


def ready_capability(**overrides):
    values = {"final_verdict": "LIVE_STRATEGY_CAPABILITY_GO"}
    values.update(overrides)
    return values


def test_final_live_start_gate_blocks_current_hedge_wait_state() -> None:
    payload = evaluate(
        ready_summary(
            order_control_final_verdict="LIVE_ORDER_CONTROL_CANARY_NO_GO",
            final_gate="WAITING_FOR_POSITION_MODE_OR_HEDGE_CANARY_APPROVAL",
        ),
        ready_config(),
        ready_capability(),
        final_approval=False,
    )
    assert payload["final_verdict"] == "FINAL_LIVE_START_GATE_NO_GO"
    assert payload["checks"]["order_control_canary"]["ok"] is False
    assert payload["checks"]["final_human_approval"]["ok"] is False


def test_final_live_start_gate_still_requires_final_human_approval() -> None:
    payload = evaluate(ready_summary(), ready_config(), ready_capability(), final_approval=False)
    assert payload["final_verdict"] == "FINAL_LIVE_START_GATE_NO_GO"
    assert payload["checks"]["order_control_canary"]["ok"] is True
    assert payload["checks"]["final_human_approval"]["ok"] is False


def test_final_live_start_gate_go_when_all_gates_and_final_approval_are_present() -> None:
    payload = evaluate(ready_summary(), ready_config(), ready_capability(), final_approval=True)
    assert payload["final_verdict"] == "FINAL_LIVE_START_GATE_GO"
    assert payload["approved_for_final_live_strategy_start"] is True


def test_final_live_start_gate_requires_live_trading_false_before_start() -> None:
    payload = evaluate(ready_summary(), ready_config(live_trading=True), ready_capability(), final_approval=True)
    assert payload["final_verdict"] == "FINAL_LIVE_START_GATE_NO_GO"
    assert payload["checks"]["config_live_trading_false_until_start"]["ok"] is False


def test_final_live_start_gate_requires_live_strategy_capability() -> None:
    payload = evaluate(
        ready_summary(),
        ready_config(),
        ready_capability(final_verdict="LIVE_STRATEGY_CAPABILITY_NO_GO"),
        final_approval=True,
    )
    assert payload["final_verdict"] == "FINAL_LIVE_START_GATE_NO_GO"
    assert payload["checks"]["live_strategy_capability"]["ok"] is False
    assert payload["next_required_human_instruction"] == "implement and validate the live strategy runner before final live start"


def test_final_live_start_gate_requires_one_way_position_mode_for_strategy() -> None:
    payload = evaluate(
        ready_summary(position_mode_dual_side=True),
        ready_config(),
        ready_capability(),
        final_approval=True,
    )
    assert payload["final_verdict"] == "FINAL_LIVE_START_GATE_NO_GO"
    assert payload["checks"]["one_way_position_mode_for_strategy"]["ok"] is False
    assert payload["next_required_human_instruction"] == "switch Binance Futures Position Mode to One-way before final live strategy start"
