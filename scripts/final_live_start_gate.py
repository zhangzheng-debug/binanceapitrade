from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bot.config import ConfigError, load_settings  # noqa: E402

REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
JSON_REPORT = REPORTS / "final_live_start_gate.json"
MD_REPORT = DOCS / "final_live_start_gate.md"

FINAL_APPROVAL_ENV = "I_APPROVE_FINAL_LIVE_STRATEGY_START"
EXPECTED_APPROVAL = "YES"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(summary: dict[str, Any], config: dict[str, Any], capability: dict[str, Any], final_approval: bool) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {
        "final_human_approval": {
            "ok": final_approval,
            "detail": f"{FINAL_APPROVAL_ENV}=YES" if final_approval else f"missing {FINAL_APPROVAL_ENV}=YES",
        },
        "signed_readonly_preflight": {
            "ok": summary.get("signed_readonly_preflight_go") is True,
            "detail": summary.get("readonly_final_verdict", "MISSING"),
        },
        "order_control_canary": {
            "ok": summary.get("order_control_final_verdict") == "LIVE_ORDER_CONTROL_CANARY_GO",
            "detail": summary.get("order_control_final_verdict", "MISSING"),
        },
        "live_strategy_capability": {
            "ok": capability.get("final_verdict") == "LIVE_STRATEGY_CAPABILITY_GO",
            "detail": capability.get("final_verdict", "MISSING"),
        },
        "final_readiness_gate": {
            "ok": summary.get("final_gate") == "READY_FOR_FINAL_LIVE_STRATEGY_DECISION",
            "detail": summary.get("final_gate", "MISSING"),
        },
        "one_way_position_mode_for_strategy": {
            "ok": summary.get("position_mode_dual_side") is False,
            "detail": summary.get("position_mode_dual_side", "MISSING"),
        },
        "exchange_info_rest": {
            "ok": summary.get("exchange_info_source") == "EXCHANGE_INFO_REST",
            "detail": summary.get("exchange_info_source", ""),
        },
        "no_open_orders_after_canary": {
            "ok": summary.get("final_open_orders_count") == 0,
            "detail": summary.get("final_open_orders_count"),
        },
        "no_unexpected_fill": {
            "ok": summary.get("unexpected_fill") is False,
            "detail": summary.get("unexpected_fill"),
        },
        "order_mode": {
            "ok": summary.get("order_mode") == "account_equity_pct",
            "detail": summary.get("order_mode", ""),
        },
        "position_size_pct": {
            "ok": str(summary.get("position_size_pct", "")) == "100",
            "detail": summary.get("position_size_pct", ""),
        },
        "config_symbol": {
            "ok": config.get("binance_symbol") in {"ETHUSDC", "BTCUSDC", "XRPUSDC"},
            "detail": config.get("binance_symbol", ""),
        },
        "config_interval": {
            "ok": config.get("binance_interval") in {"15m", "1h"},
            "detail": config.get("binance_interval", ""),
        },
        "config_mainnet": {
            "ok": config.get("binance_env") == "mainnet",
            "detail": config.get("binance_env", ""),
        },
        "config_live_trading_false_until_start": {
            "ok": config.get("live_trading") is False,
            "detail": config.get("live_trading"),
        },
        "api_credentials_present": {
            "ok": config.get("has_api_key") is True and config.get("has_api_secret") is True,
            "detail": {"has_api_key": config.get("has_api_key"), "has_api_secret": config.get("has_api_secret")},
        },
    }
    approved = all(item["ok"] for item in checks.values())
    return {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "approved_for_final_live_strategy_start": approved,
        "final_verdict": "FINAL_LIVE_START_GATE_GO" if approved else "FINAL_LIVE_START_GATE_NO_GO",
        "checks": checks,
        "next_required_human_instruction": (
            "start the final tiny live strategy canary"
            if approved
            else (
                "implement and validate the live strategy runner before final live start"
                if capability.get("final_verdict") != "LIVE_STRATEGY_CAPABILITY_GO"
                else "switch Binance Futures Position Mode to One-way before final live strategy start"
                if summary.get("position_mode_dual_side") is not False
                else summary.get("next_required_human_instruction", f"set {FINAL_APPROVAL_ENV}=YES only after all gates are GO")
            )
        ),
    }


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# Final Live Start Gate",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        f"Final verdict: `{payload['final_verdict']}`",
        f"Approved for final live strategy start: `{payload['approved_for_final_live_strategy_start']}`",
        "",
        "## Checks",
        "",
    ]
    for name, item in payload["checks"].items():
        lines.append(f"- {name}: `{item['ok']}` ({item['detail']})")
    lines.extend(
        [
            "",
            f"Next required human instruction: `{payload['next_required_human_instruction']}`",
        ]
    )
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    try:
        config = load_settings().safe_summary()
    except ConfigError as exc:
        config = {"config_error": str(exc)}
    payload = evaluate(
        load_json(REPORTS / "live_readiness_gate_summary.json"),
        config,
        load_json(REPORTS / "live_strategy_capability_audit.json"),
        os.environ.get(FINAL_APPROVAL_ENV) == EXPECTED_APPROVAL,
    )
    JSON_REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(payload)
    print(f"json_report={JSON_REPORT}")
    print(f"markdown_report={MD_REPORT}")
    print(f"final_verdict={payload['final_verdict']}")
    return 0 if payload["approved_for_final_live_strategy_start"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
