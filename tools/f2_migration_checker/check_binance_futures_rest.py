from __future__ import annotations

import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
JSON_REPORT = ROOT / "f2_migration_check_result.json"
MD_REPORT = ROOT / "f2_migration_check_report.md"

TARGETS = [
    ("mainnet_ping", "mainnet", "https://fapi.binance.com/fapi/v1/ping"),
    ("mainnet_time", "mainnet", "https://fapi.binance.com/fapi/v1/time"),
    ("mainnet_exchangeInfo", "mainnet", "https://fapi.binance.com/fapi/v1/exchangeInfo"),
    ("mainnet_bookTicker", "mainnet", "https://fapi.binance.com/fapi/v1/ticker/bookTicker?symbol=ETHUSDC"),
    ("testnet_ping", "testnet", "https://demo-fapi.binance.com/fapi/v1/ping"),
    ("testnet_time", "testnet", "https://demo-fapi.binance.com/fapi/v1/time"),
    ("testnet_exchangeInfo", "testnet", "https://demo-fapi.binance.com/fapi/v1/exchangeInfo"),
    ("testnet_bookTicker", "testnet", "https://demo-fapi.binance.com/fapi/v1/ticker/bookTicker?symbol=ETHUSDC"),
]


def timestamp_utc() -> str:
    return datetime.now(tz=UTC).isoformat()


def classify_status(status_code: int | None, error: BaseException | None = None) -> str:
    if status_code == 451:
        return "rest_451_blocked_no_bypass"
    if status_code is not None and 200 <= status_code < 300:
        return "ok"
    if status_code is not None and 400 <= status_code < 500:
        return "http_4xx"
    if status_code is not None and status_code >= 500:
        return "http_5xx"
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, socket.gaierror):
        return "dns_error"
    if isinstance(error, ssl.SSLError):
        return "tls_error"
    message = str(error or "").lower()
    if "timed out" in message or "timeout" in message:
        return "timeout"
    if "name or service not known" in message or "getaddrinfo" in message:
        return "dns_error"
    if "ssl" in message or "tls" in message or "certificate" in message:
        return "tls_error"
    return "network_or_client_error"


def redacted_snippet(value: str, limit: int = 180) -> str:
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())[:limit]


def check_url(name: str, environment: str, url: str) -> dict[str, Any]:
    started = time.perf_counter()
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "ethusdc-pivot-bot-f2-checker"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read(300).decode("utf-8", errors="replace")
            status_code = int(response.status)
            return {
                "name": name,
                "environment": environment,
                "transport": "rest",
                "url": url,
                "ok": 200 <= status_code < 300,
                "status_code": status_code,
                "classification": classify_status(status_code),
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "error": "",
                "response_snippet_redacted": redacted_snippet(body),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(300).decode("utf-8", errors="replace")
        return {
            "name": name,
            "environment": environment,
            "transport": "rest",
            "url": url,
            "ok": False,
            "status_code": int(exc.code),
            "classification": classify_status(int(exc.code)),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "error": redacted_snippet(str(exc)),
            "response_snippet_redacted": redacted_snippet(body),
        }
    except Exception as exc:
        return {
            "name": name,
            "environment": environment,
            "transport": "rest",
            "url": url,
            "ok": False,
            "status_code": None,
            "classification": classify_status(None, exc),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "error": redacted_snippet(str(exc)),
            "response_snippet_redacted": "",
        }


def decision_codes(payload: dict[str, Any]) -> list[str]:
    rest_results = [result for result in payload.get("results", []) if result.get("transport") == "rest"]
    mainnet = [result for result in rest_results if result.get("environment") == "mainnet"]
    testnet = [result for result in rest_results if result.get("environment") == "testnet"]
    ws_results = [result for result in payload.get("results", []) if result.get("transport") == "websocket"]
    codes: list[str] = []
    mainnet_all_ok = bool(mainnet) and all(result.get("ok") for result in mainnet)
    testnet_all_ok = bool(testnet) and all(result.get("ok") for result in testnet)
    mainnet_451 = any(result.get("status_code") == 451 for result in mainnet)
    ws_all_ok = bool(ws_results) and all(result.get("ok") for result in ws_results)
    network_issue = any(result.get("classification") in {"dns_error", "tls_error", "timeout", "network_or_client_error"} for result in rest_results)
    if mainnet_all_ok:
        codes.append("F2_MAINNET_REST_GO")
    if mainnet_451:
        codes.append("F2_MAINNET_REST_NO_GO")
    if testnet_all_ok and mainnet_451:
        codes.append("TESTNET_ONLY_POSSIBLE_BUT_LIVE_NO_GO")
    if ws_all_ok and mainnet_451:
        codes.append("PUBLIC_WS_DRY_RUN_ONLY")
    if network_issue:
        codes.append("NETWORK_ISSUE_DIAGNOSE")
    return codes or ["NETWORK_ISSUE_DIAGNOSE"]


def write_report(payload: dict[str, Any]) -> None:
    codes = payload.get("decision_codes", [])
    lines = [
        "# F2 Migration Check Report",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        "Public endpoints only. No API keys, signed REST, orders, proxy, VPN, or tunnel behavior.",
        "",
        f"- Decision codes: `{', '.join(codes)}`",
        "",
        "| Name | Env | Transport | OK | Status | Classification |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in payload.get("results", []):
        lines.append(
            f"| {result['name']} | {result['environment']} | {result['transport']} | {result['ok']} | {result.get('status_code')} | {result['classification']} |"
        )
    lines.extend(
        [
            "",
            "If mainnet REST returns 451, this server cannot be used for Binance Futures live. Do not bypass with proxy, VPN, or tunnel. Use a lawful server environment where Binance Futures REST is reachable.",
        ]
    )
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    results = [check_url(*target) for target in TARGETS]
    payload: dict[str, Any] = {
        "generated_at_utc": timestamp_utc(),
        "symbol": "ETHUSDC",
        "safety": {
            "public_only": True,
            "api_keys_read": False,
            "signed_rest": False,
            "orders": False,
            "proxy_vpn_tunnel_bypass": False,
        },
        "results": results,
    }
    payload["decision_codes"] = decision_codes(payload)
    JSON_REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_report(payload)
    print(f"json_report={JSON_REPORT}")
    print(f"markdown_report={MD_REPORT}")
    print(f"decision_codes={','.join(payload['decision_codes'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
