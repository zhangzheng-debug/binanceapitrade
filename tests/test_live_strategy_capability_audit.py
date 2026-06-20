from scripts.live_strategy_capability_audit import audit_main


def test_live_strategy_runner_is_wired() -> None:
    payload = audit_main()
    assert payload["final_verdict"] == "LIVE_STRATEGY_CAPABILITY_GO"
    assert payload["live_strategy_runner_implemented"] is True
    assert payload["has_live_runner"] is True
    assert payload["has_live_entry_canary_once"] is True
    assert payload["has_account_equity_sizing"] is True
    assert payload["has_maker_chaser"] is True
    assert payload["has_live_stop_management"] is True
    assert payload["blockers"] == []
