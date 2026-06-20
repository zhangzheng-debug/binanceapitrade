from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
JSON_REPORT = REPORTS / "live_readiness_gate_summary.json"
MD_REPORT = DOCS / "live_readiness_gate_summary.md"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_bundle_report() -> dict[str, Any]:
    for name in (
        "deploy_bundle_final_pre_live_gate.json",
        "deploy_bundle_live_sizing_position_side_gate.json",
        "deploy_bundle_hedge_mode_order_control_gate.json",
    ):
        payload = load_json(REPORTS / name)
        if payload:
            return payload
    return {}


def summarize(readonly: dict[str, Any], order_control: dict[str, Any], bundle: dict[str, Any], capability: dict[str, Any] | None = None) -> dict[str, Any]:
    capability = capability or {}
    readonly_go = readonly.get("final_verdict") == "SIGNED_READONLY_PREFLIGHT_GO"
    order_control_go = order_control.get("final_verdict") == "LIVE_ORDER_CONTROL_CANARY_GO"
    hedge_mode = order_control.get("position_mode_dual_side")
    hedge_approval = order_control.get("hedge_mode_approval_env_present")
    real_order_attempt_count = int(order_control.get("real_order_attempt_count") or 0)
    signed_paths = [f"{call.get('method', '')} {call.get('path', '')}" for call in order_control.get("signed_calls", [])]

    if order_control_go:
        next_instruction = "decide whether to start a tiny live strategy canary under a supervised service"
        final_gate = "READY_FOR_FINAL_LIVE_STRATEGY_DECISION"
    elif hedge_mode and not hedge_approval:
        next_instruction = (
            "either switch Binance Futures Position Mode to One-way, or explicitly approve Hedge Mode order-control "
            "canary by setting I_APPROVE_HEDGE_MODE_ORDER_CONTROL_CANARY=YES"
        )
        final_gate = "WAITING_FOR_POSITION_MODE_OR_HEDGE_CANARY_APPROVAL"
    else:
        next_instruction = "review order-control canary failure and rerun after fixing the reported cause"
        final_gate = "ORDER_CONTROL_CANARY_NOT_GO"

    return {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "signed_readonly_preflight_go": readonly_go,
        "readonly_final_verdict": readonly.get("final_verdict", "MISSING"),
        "exchange_info_source": readonly.get("checks", {}).get("exchange_info", {}).get("filters_source", ""),
        "order_mode": readonly.get("order_mode", ""),
        "position_size_pct": readonly.get("position_size_pct", ""),
        "order_control_final_verdict": order_control.get("final_verdict", "MISSING"),
        "position_mode_dual_side": hedge_mode,
        "hedge_mode_approval_env_present": hedge_approval,
        "initial_open_orders_count": order_control.get("initial_open_orders_count"),
        "final_open_orders_count": order_control.get("final_open_orders_count"),
        "real_order_attempt_count": real_order_attempt_count,
        "limit_gtx_order_attempt_count": order_control.get("limit_gtx_order_attempt_count", 0),
        "modify_order_attempt_count": order_control.get("modify_order_attempt_count", 0),
        "cancel_order_attempt_count": order_control.get("cancel_order_attempt_count", 0),
        "market_entry_attempt_count": order_control.get("market_entry_attempt_count", 0),
        "stop_market_entry_attempt_count": order_control.get("stop_market_entry_attempt_count", 0),
        "reduce_only_market_cleanup_count": order_control.get("reduceOnly_market_cleanup_count", 0),
        "hedge_mode_market_cleanup_count": order_control.get("hedge_mode_market_cleanup_count", 0),
        "unexpected_fill": order_control.get("unexpected_fill", False),
        "full_strategy_started": order_control.get("full_strategy_started", False),
        "live_trading_started": order_control.get("live_trading_started", False),
        "key_secret_printed": order_control.get("key_secret_printed", False),
        "live_strategy_capability_verdict": capability.get("final_verdict", "MISSING"),
        "live_strategy_runner_implemented": capability.get("live_strategy_runner_implemented"),
        "signed_paths": signed_paths,
        "bundle": bundle.get("bundle", ""),
        "bundle_sha256": bundle.get("sha256", ""),
        "final_gate": final_gate,
        "next_required_human_instruction": next_instruction,
    }


def write_markdown(summary: dict[str, Any]) -> None:
    lines = [
        "# Live Readiness Gate Summary",
        "",
        f"Generated UTC: `{summary['generated_at_utc']}`",
        "",
        f"- Signed read-only preflight GO: `{summary['signed_readonly_preflight_go']}`",
        f"- Read-only verdict: `{summary['readonly_final_verdict']}`",
        f"- ExchangeInfo source: `{summary['exchange_info_source']}`",
        f"- Order mode: `{summary['order_mode']}`",
        f"- Position size pct: `{summary['position_size_pct']}`",
        f"- Order-control verdict: `{summary['order_control_final_verdict']}`",
        f"- Position mode dual-side: `{summary['position_mode_dual_side']}`",
        f"- Hedge Mode approval env present: `{summary['hedge_mode_approval_env_present']}`",
        f"- Initial open orders count: `{summary['initial_open_orders_count']}`",
        f"- Final open orders count: `{summary['final_open_orders_count']}`",
        f"- Real order attempts: `{summary['real_order_attempt_count']}`",
        f"- LIMIT GTX order attempts: `{summary['limit_gtx_order_attempt_count']}`",
        f"- Modify attempts: `{summary['modify_order_attempt_count']}`",
        f"- Cancel attempts: `{summary['cancel_order_attempt_count']}`",
        f"- MARKET entry attempts: `{summary['market_entry_attempt_count']}`",
        f"- STOP_MARKET entry attempts: `{summary['stop_market_entry_attempt_count']}`",
        f"- reduceOnly MARKET cleanup count: `{summary['reduce_only_market_cleanup_count']}`",
        f"- Hedge Mode MARKET cleanup count: `{summary['hedge_mode_market_cleanup_count']}`",
        f"- Unexpected fill: `{summary['unexpected_fill']}`",
        f"- Full strategy started: `{summary['full_strategy_started']}`",
        f"- Live trading started: `{summary['live_trading_started']}`",
        f"- Key/secret printed: `{summary['key_secret_printed']}`",
        f"- Live strategy capability verdict: `{summary['live_strategy_capability_verdict']}`",
        f"- Live strategy runner implemented: `{summary['live_strategy_runner_implemented']}`",
        f"- Bundle: `{summary['bundle']}`",
        f"- Bundle SHA-256: `{summary['bundle_sha256']}`",
        "",
        f"Final gate: `{summary['final_gate']}`",
        "",
        f"Next required human instruction: `{summary['next_required_human_instruction']}`",
    ]
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    summary = summarize(
        load_json(REPORTS / "live_readonly_preflight.json"),
        load_json(REPORTS / "live_canary_order_control.json"),
        load_bundle_report(),
        load_json(REPORTS / "live_strategy_capability_audit.json"),
    )
    JSON_REPORT.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(summary)
    print(f"json_report={JSON_REPORT}")
    print(f"markdown_report={MD_REPORT}")
    print(f"final_gate={summary['final_gate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
