from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC_MAIN = ROOT / "src" / "bot" / "main.py"
SRC_LIVE_RUNNER = ROOT / "src" / "bot" / "live_strategy_runner.py"
REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
JSON_REPORT = REPORTS / "live_strategy_capability_audit.json"
MD_REPORT = DOCS / "live_strategy_capability_audit.md"


def function_names(tree: ast.AST) -> set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def audit_main(path: Path = SRC_MAIN, live_runner_path: Path = SRC_LIVE_RUNNER) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = function_names(tree)
    live_runner_source = live_runner_path.read_text(encoding="utf-8") if live_runner_path.exists() else ""
    live_runner_tree = ast.parse(live_runner_source) if live_runner_source else ast.Module(body=[], type_ignores=[])
    live_runner_functions = function_names(live_runner_tree)
    has_live_runner = "run_live_strategy_canary" in functions or "run_live_strategy" in functions
    has_live_entry_canary_once = "run_live_entry_canary_once" in live_runner_functions
    has_public_dry_runner = "run_public_market_dry_run" in functions
    live_requested_logged = "live_trading_requested" in source
    bot_started_logged = "bot_started" in source
    account_equity_blocked_in_dry_run = "trigger_blocked_account_equity_sizing_unavailable" in source
    has_account_equity_sizing = "account_equity_pct_size" in live_runner_source
    has_maker_chaser = "MakerChaser" in live_runner_source and "chase_entry" in live_runner_source
    has_live_stop_management = "chase_stop" in source or "run_live_stop" in functions

    blockers: list[str] = []
    if not has_live_entry_canary_once:
        blockers.append("src/bot/live_strategy_runner.py has no run_live_entry_canary_once primitive")
    if has_live_entry_canary_once and not has_account_equity_sizing:
        blockers.append("live entry canary does not use account_equity_pct sizing")
    if has_live_entry_canary_once and not has_maker_chaser:
        blockers.append("live entry canary does not use MakerChaser entry execution")
    if not has_live_runner:
        blockers.append("src/bot/main.py has no run_live_strategy_canary or run_live_strategy function")
    if live_requested_logged and bot_started_logged and not has_live_runner:
        blockers.append("LIVE_TRADING=true is logged, but no live strategy loop is present")
    if not has_live_stop_management:
        blockers.append("live stop management is not wired into bot.main")

    implemented = not blockers
    return {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "live_strategy_runner_implemented": implemented,
        "main_path": str(path.relative_to(ROOT)),
        "live_runner_path": str(live_runner_path.relative_to(ROOT)) if live_runner_path.exists() else "",
        "has_live_runner": has_live_runner,
        "has_live_entry_canary_once": has_live_entry_canary_once,
        "has_account_equity_sizing": has_account_equity_sizing,
        "has_maker_chaser": has_maker_chaser,
        "has_live_stop_management": has_live_stop_management,
        "has_public_dry_runner": has_public_dry_runner,
        "live_requested_logged": live_requested_logged,
        "account_equity_blocked_in_dry_run": account_equity_blocked_in_dry_run,
        "blockers": blockers,
        "final_verdict": "LIVE_STRATEGY_CAPABILITY_GO" if implemented else "LIVE_STRATEGY_CAPABILITY_NO_GO",
    }


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# Live Strategy Capability Audit",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        f"Final verdict: `{payload['final_verdict']}`",
        f"Live strategy runner implemented: `{payload['live_strategy_runner_implemented']}`",
        f"Main path: `{payload['main_path']}`",
        f"Live runner path: `{payload['live_runner_path']}`",
        "",
        "## Evidence",
        "",
        f"- Has live runner function: `{payload['has_live_runner']}`",
        f"- Has one-shot live entry canary primitive: `{payload['has_live_entry_canary_once']}`",
        f"- Uses account-equity sizing: `{payload['has_account_equity_sizing']}`",
        f"- Uses MakerChaser: `{payload['has_maker_chaser']}`",
        f"- Has live stop management: `{payload['has_live_stop_management']}`",
        f"- Has public dry-run runner: `{payload['has_public_dry_runner']}`",
        f"- LIVE_TRADING request is logged: `{payload['live_requested_logged']}`",
        f"- account_equity_pct is blocked in public dry-run path: `{payload['account_equity_blocked_in_dry_run']}`",
        "",
        "## Blockers",
        "",
    ]
    if payload["blockers"]:
        lines.extend(f"- {blocker}" for blocker in payload["blockers"])
    else:
        lines.append("- None")
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    payload = audit_main()
    JSON_REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(payload)
    print(f"json_report={JSON_REPORT}")
    print(f"markdown_report={MD_REPORT}")
    print(f"final_verdict={payload['final_verdict']}")
    return 0 if payload["live_strategy_runner_implemented"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
