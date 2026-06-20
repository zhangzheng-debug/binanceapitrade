from __future__ import annotations

import asyncio
import json
import subprocess
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from bot.binance_client import BinanceClient
from bot.config import load_settings
from bot.live_position_state import load_managed_position_marker


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
JSON_REPORT = REPORTS / "live_monitor_status.json"
MD_REPORT = DOCS / "live_monitor_status.md"
EVENTS_LOG = ROOT / "logs" / "events.jsonl"
SERVICE_NAME = "ethusdc-pivot-bot-live-strategy.service"
ABNORMAL_EVENTS = {
    "entry_chase_started",
    "entry_order_placed",
    "entry_order_modified",
    "entry_order_filled",
    "entry_order_partially_filled",
    "entry_order_cancelled",
    "live_entry_chase_finished",
    "live_strategy_entry_fill_limit_reached",
    "live_trigger_blocked_entry_fill_limit",
    "live_trigger_blocked_risk",
    "ignored_due_to_position",
    "stop_fallback_market",
    "live_stop_triggered",
    "live_stop_chase_finished",
    "api_error",
}
MARKET_EVENTS = {
    "book_ticker_summary",
    "candle_closed_received",
    "book_ticker_ws_connected",
    "websocket_connected",
}


def run_cmd(args: list[str]) -> str:
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    return result.stdout.strip()


def systemd_status() -> dict[str, str]:
    status = {
        "active": run_cmd(["systemctl", "--user", "is-active", SERVICE_NAME]),
        "enabled": run_cmd(["systemctl", "--user", "is-enabled", SERVICE_NAME]),
        "linger": run_cmd(["loginctl", "show-user", "root", "-p", "Linger", "--value"]),
    }
    show = run_cmd(
        [
            "systemctl",
            "--user",
            "show",
            SERVICE_NAME,
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "MainPID",
            "-p",
            "ExecMainStatus",
            "-p",
            "NRestarts",
            "-p",
            "Restart",
            "-p",
            "RuntimeMaxUSec",
            "--no-pager",
        ]
    )
    for line in show.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            status[key] = value
    return status


def previous_status() -> dict[str, Any]:
    if not JSON_REPORT.exists():
        return {}
    try:
        return json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def read_recent_events(cutoff_epoch: float) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    abnormal: list[dict[str, Any]] = []
    latest_market: dict[str, Any] | None = None
    if not EVENTS_LOG.exists():
        return abnormal, latest_market
    lines = EVENTS_LOG.read_text(encoding="utf-8").splitlines()[-20000:]
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        created = float(event.get("created") or 0)
        event_type = str(event.get("event") or "")
        if event_type in MARKET_EVENTS:
            latest_market = event
        if created < cutoff_epoch:
            continue
        if event_type in ABNORMAL_EVENTS or event.get("level") == "ERROR" or "Traceback" in str(event):
            abnormal.append(event)
    return abnormal, latest_market


async def read_exchange_state(settings) -> dict[str, Any]:
    client = BinanceClient(settings)
    try:
        open_orders = await client.get_open_orders(settings.binance_symbol)
        position = await client.get_position(settings.binance_symbol)
    finally:
        await client.close()
    signed_error = None
    return {
        "signed_error": signed_error,
        "open_orders": len(open_orders),
        "position_symbol": position.symbol,
        "position_side": position.side.value,
        "position_quantity": str(position.quantity),
        "position_entry_price": str(position.entry_price) if position.entry_price is not None else "",
    }


def compare_marker(settings, exchange: dict[str, Any]) -> dict[str, Any]:
    marker = load_managed_position_marker(settings.live_managed_position_marker_path)
    if marker is None:
        return {"present": False, "matches_exchange": False}
    position_quantity = Decimal(str(exchange["position_quantity"]))
    return {
        "present": True,
        "symbol": marker.symbol,
        "side": marker.side.value,
        "quantity": str(marker.quantity),
        "entry_price": str(marker.entry_price) if marker.entry_price is not None else "",
        "signal_id": marker.signal_id,
        "matches_exchange": (
            marker.symbol == exchange["position_symbol"]
            and marker.side.value == exchange["position_side"]
            and marker.quantity == position_quantity
        ),
    }


def build_payload() -> dict[str, Any]:
    now = time.time()
    previous = previous_status()
    cutoff = float(previous.get("checked_at_epoch") or (now - 20 * 60))
    settings = load_settings()
    service = systemd_status()
    exchange = asyncio.run(read_exchange_state(settings))
    marker = compare_marker(settings, exchange)
    abnormal_events, latest_market = read_recent_events(cutoff)

    alerts: list[str] = []
    if service.get("active") != "active" or service.get("ActiveState") != "active":
        alerts.append("service is not active")
    if service.get("enabled") != "enabled":
        alerts.append("service is not enabled")
    if service.get("RuntimeMaxUSec") != "infinity":
        alerts.append("runtime cap is not infinity")
    if service.get("linger") != "yes":
        alerts.append("root linger is not yes")
    previous_restarts = previous.get("service", {}).get("NRestarts")
    if previous_restarts is not None and service.get("NRestarts") != str(previous_restarts):
        alerts.append("service restart count changed")
    if exchange["open_orders"] != 0:
        alerts.append("ETHUSDC open orders are nonzero")
    if exchange["position_side"] == "NONE" or Decimal(exchange["position_quantity"]) <= 0:
        alerts.append("ETHUSDC position is flat")
    if not marker.get("present"):
        alerts.append("managed position marker is missing")
    elif not marker.get("matches_exchange"):
        alerts.append("managed position marker does not match exchange position")
    if latest_market is None:
        alerts.append("market heartbeat is missing")
    else:
        age_seconds = now - float(latest_market.get("created") or 0)
        if age_seconds > 180:
            alerts.append("market heartbeat is stale")
    if abnormal_events:
        alerts.append("new abnormal order/stop/error events found")

    return {
        "checked_at_utc": datetime.now(tz=UTC).isoformat(),
        "checked_at_epoch": now,
        "status": "ALERT" if alerts else "OK",
        "alerts": alerts,
        "service": service,
        "exchange": exchange,
        "marker": marker,
        "latest_market_heartbeat": latest_market,
        "abnormal_event_count": len(abnormal_events),
        "abnormal_events_tail": abnormal_events[-10:],
    }


def write_markdown(payload: dict[str, Any]) -> None:
    exchange = payload["exchange"]
    marker = payload["marker"]
    service = payload["service"]
    lines = [
        "# Live Monitor Status",
        "",
        f"Checked UTC: `{payload['checked_at_utc']}`",
        f"Status: `{payload['status']}`",
        "",
        "## Service",
        "",
        f"- active: `{service.get('active')}`",
        f"- enabled: `{service.get('enabled')}`",
        f"- ActiveState: `{service.get('ActiveState')}`",
        f"- SubState: `{service.get('SubState')}`",
        f"- MainPID: `{service.get('MainPID')}`",
        f"- NRestarts: `{service.get('NRestarts')}`",
        f"- RuntimeMaxUSec: `{service.get('RuntimeMaxUSec')}`",
        f"- linger: `{service.get('linger')}`",
        "",
        "## Position",
        "",
        f"- open orders: `{exchange['open_orders']}`",
        f"- position: `{exchange['position_side']} {exchange['position_quantity']}`",
        f"- entry price: `{exchange['position_entry_price']}`",
        f"- marker present: `{marker.get('present')}`",
        f"- marker matches exchange: `{marker.get('matches_exchange')}`",
        f"- marker: `{marker.get('side', '')} {marker.get('quantity', '')} @ {marker.get('entry_price', '')}`",
        "",
        "## Alerts",
        "",
    ]
    if payload["alerts"]:
        lines.extend(f"- {item}" for item in payload["alerts"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            f"Abnormal event count since previous check: `{payload['abnormal_event_count']}`",
        ]
    )
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    payload = build_payload()
    JSON_REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    write_markdown(payload)
    print(f"status={payload['status']}")
    print(f"json_report={JSON_REPORT}")
    print(f"markdown_report={MD_REPORT}")
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
