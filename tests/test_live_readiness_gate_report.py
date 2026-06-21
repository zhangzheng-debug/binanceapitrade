from scripts.live_readiness_gate_report import summarize


def test_readiness_summary_waits_for_hedge_mode_approval() -> None:
    summary = summarize(
        {
            "final_verdict": "SIGNED_READONLY_PREFLIGHT_GO",
            "checks": {"exchange_info": {"filters_source": "EXCHANGE_INFO_REST"}},
            "order_mode": "account_equity_pct",
            "position_size_pct": "100",
        },
        {
            "final_verdict": "LIVE_ORDER_CONTROL_CANARY_NO_GO",
            "position_mode_dual_side": True,
            "hedge_mode_approval_env_present": False,
            "initial_open_orders_count": 0,
            "final_open_orders_count": 0,
            "real_order_attempt_count": 0,
            "signed_calls": [{"method": "GET", "path": "/fapi/v1/openOrders"}],
        },
        {"bundle": "dist/bundle.tar.gz", "sha256": "abc"},
        {"final_verdict": "LIVE_STRATEGY_CAPABILITY_NO_GO", "live_strategy_runner_implemented": False},
    )

    assert summary["signed_readonly_preflight_go"] is True
    assert summary["final_gate"] == "WAITING_FOR_POSITION_MODE_OR_HEDGE_CANARY_APPROVAL"
    assert "I_APPROVE_HEDGE_MODE_ORDER_CONTROL_CANARY=YES" in summary["next_required_human_instruction"]
    assert summary["real_order_attempt_count"] == 0
    assert summary["live_strategy_capability_verdict"] == "LIVE_STRATEGY_CAPABILITY_NO_GO"
