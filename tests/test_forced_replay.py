import asyncio
from pathlib import Path

from scripts import replay_forced_original_pivot_trigger as replay


def run(coro):
    return asyncio.run(coro)


def test_forced_long_replay_creates_pending_trigger() -> None:
    result = run(replay.replay_long())
    assert result["ok"] is True
    assert "pending_long_stop_created" in result["seed_events"]
    assert result["trigger_price"] == "10.01"


def test_forced_long_replay_starts_maker_chaser() -> None:
    result = run(replay.replay_long())
    assert "entry_chase_started" in result["chase"]["exchange_calls"] or result["chase"]["dry_run_limit_gtx_order_created"]
    assert result["chase"]["entry_side"] == "BUY"


def test_forced_short_replay_creates_pending_trigger() -> None:
    result = run(replay.replay_short())
    assert result["ok"] is True
    assert "pending_short_stop_created" in result["seed_events"]
    assert result["trigger_price"] == "0.99"


def test_forced_short_replay_starts_maker_chaser() -> None:
    result = run(replay.replay_short())
    assert result["chase"]["dry_run_limit_gtx_order_created"] is True
    assert result["chase"]["entry_side"] == "SELL"


def test_forced_replay_no_market_entry() -> None:
    payload = run(replay.run_forced_replay())
    assert payload["market_entry_order_attempt_count"] == 0


def test_forced_replay_no_stop_market_entry() -> None:
    payload = run(replay.run_forced_replay())
    assert payload["stop_market_order_attempt_count"] == 0


def test_forced_replay_no_signed_rest() -> None:
    payload = run(replay.run_forced_replay())
    assert payload["signed_rest_call_count"] == 0
    assert payload["real_order_attempt_count"] == 0


def test_forced_dual_trigger_skip() -> None:
    result = replay.replay_ambiguous()
    assert result["ok"] is True
    assert result["events"] == ["ambiguous_dual_trigger_skipped"]


def test_forced_active_chase_blocks_opposite() -> None:
    result = replay.replay_active_chase_block()
    assert result["ok"] is True
    assert result["events"] == ["trigger_blocked_active_chase"]


def test_forced_position_blocks_entry() -> None:
    result = replay.replay_position_block()
    assert result["ok"] is True
    assert result["events"] == ["ignored_due_to_position"]


def test_forced_missed_trigger_logged() -> None:
    result = replay.replay_missed_trigger()
    assert result["ok"] is True
    assert "missed_long_trigger_on_closed_candle" in result["long_events"]
    assert "missed_short_trigger_on_closed_candle" in result["short_events"]


def test_forced_replay_report_generated(tmp_path: Path, monkeypatch) -> None:
    json_report = tmp_path / "forced_original_pivot_trigger_replay.json"
    md_report = tmp_path / "forced_original_pivot_trigger_replay_report.md"
    monkeypatch.setattr(replay, "JSON_REPORT", json_report)
    monkeypatch.setattr(replay, "MD_REPORT", md_report)
    monkeypatch.setattr(replay, "REPORTS", tmp_path)
    monkeypatch.setattr(replay, "DOCS", tmp_path)
    payload = run(replay.run_forced_replay())
    replay.write_reports(payload)
    assert json_report.exists()
    assert md_report.exists()
    assert "Forced Original Pivot Trigger Replay Report" in md_report.read_text(encoding="utf-8")
