from __future__ import annotations

import asyncio
import json
import socket
import ssl
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bot.book_ticker_stream import LOCKED_BOOK_TICKER_STREAM_NAME, snapshot_from_book_ticker_payload  # noqa: E402
from bot.market_data import LOCKED_STREAM_NAME  # noqa: E402

REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
JSON_REPORT = REPORTS / "fast_path_connectivity_diagnosis.json"
MD_REPORT = DOCS / "fast_path_connectivity_diagnosis.md"
LEGACY_JSON_REPORT = REPORTS / "binance_connectivity_diagnosis.json"
LEGACY_MD_REPORT = DOCS / "phase3a5_binance_connectivity_diagnosis.md"

MAINNET_REST = "https://fapi.binance.com"
TESTNET_REST = "https://testnet.binancefuture.com"
MAINNET_KLINE_WS = f"wss://fstream.binance.com/market/stream?streams={LOCKED_STREAM_NAME}"
MAINNET_BOOK_TICKER_WS = f"wss://fstream.binance.com/public/stream?streams={LOCKED_BOOK_TICKER_STREAM_NAME}"


@dataclass(frozen=True)
class RestTarget:
    name: str
    environment: str
    method: str
    path: str
    params: dict[str, str]
    url_kind: str


@dataclass
class DiagnosisResult:
    name: str
    environment: str
    transport: str
    url_kind: str
    status_code: int | None
    ok: bool
    error_type: str
    short_error_message: str
    elapsed_ms: int
    timestamp_utc: str
    response_snippet_redacted: str
    classification: str
    action: str
    details: dict[str, Any]


def timestamp_utc() -> str:
    return datetime.now(tz=UTC).isoformat()


def classify_http_status(status_code: int | None, message: str = "") -> tuple[str, str]:
    if status_code == 451:
        return "rest_451_blocked_no_bypass", "stop_no_testnet_no_live"
    if status_code is None:
        return "network_or_client_error", "report_only"
    if 200 <= status_code < 300:
        return "ok", "none"
    if 400 <= status_code < 500:
        return "http_4xx", "report_only"
    if status_code >= 500:
        return "http_5xx", "report_only"
    if message:
        return "unknown_with_message", "report_only"
    return "unknown", "report_only"


def _causes(exc: BaseException):
    current: BaseException | None = exc
    while current is not None:
        yield current
        current = current.__cause__ or current.__context__


def classify_exception(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout", "report_only"
    for cause in _causes(exc):
        if isinstance(cause, socket.gaierror):
            return "dns_error", "report_only"
        if isinstance(cause, ssl.SSLError):
            return "tls_error", "report_only"
    message = str(exc).lower()
    if "name or service not known" in message or "nodename nor servname" in message:
        return "dns_error", "report_only"
    if "ssl" in message or "tls" in message or "certificate" in message:
        return "tls_error", "report_only"
    return "network_or_client_error", "report_only"


def redacted_snippet(text: str, limit: int = 300) -> str:
    compact = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    return compact[:limit]


def rest_targets() -> list[RestTarget]:
    targets: list[RestTarget] = []
    for environment in ("mainnet", "testnet"):
        for name, path, params in (
            ("ping", "/fapi/v1/ping", {}),
            ("time", "/fapi/v1/time", {}),
            ("exchangeInfo", "/fapi/v1/exchangeInfo", {}),
            ("bookTicker", "/fapi/v1/ticker/bookTicker", {"symbol": "ETHUSDC"}),
        ):
            targets.append(
                RestTarget(
                    name=f"{environment}_{name}",
                    environment=environment,
                    method="GET",
                    path=path,
                    params=params,
                    url_kind=f"usds_m_futures_{environment}_public_rest_{name}",
                )
            )
    return targets


def assert_public_only_targets(targets: list[RestTarget]) -> None:
    forbidden_methods = {"POST", "PUT", "DELETE"}
    forbidden_fragments = ("/order", "/openOrders", "/positionRisk", "/account", "/listenKey")
    for target in targets:
        if target.method.upper() in forbidden_methods:
            raise RuntimeError(f"forbidden method in diagnosis target: {target.method} {target.path}")
        if any(fragment in target.path for fragment in forbidden_fragments):
            raise RuntimeError(f"forbidden signed/order path in diagnosis target: {target.path}")


async def diagnose_rest_target(target: RestTarget) -> DiagnosisResult:
    base_url = MAINNET_REST if target.environment == "mainnet" else TESTNET_REST
    started = time.perf_counter()
    async with httpx.AsyncClient(base_url=base_url, timeout=10, trust_env=False) as client:
        try:
            response = await client.request(target.method, target.path, params=target.params)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            classification, action = classify_http_status(response.status_code, response.text)
            return DiagnosisResult(
                name=target.name,
                environment=target.environment,
                transport="rest",
                url_kind=target.url_kind,
                status_code=response.status_code,
                ok=200 <= response.status_code < 300,
                error_type="" if response.status_code < 400 else f"http_{response.status_code}",
                short_error_message="" if response.status_code < 400 else redacted_snippet(response.text, 160),
                elapsed_ms=elapsed_ms,
                timestamp_utc=timestamp_utc(),
                response_snippet_redacted=redacted_snippet(response.text),
                classification=classification,
                action=action,
                details={},
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            classification, action = classify_exception(exc)
            return DiagnosisResult(
                name=target.name,
                environment=target.environment,
                transport="rest",
                url_kind=target.url_kind,
                status_code=None,
                ok=False,
                error_type=exc.__class__.__name__,
                short_error_message=redacted_snippet(str(exc), 160),
                elapsed_ms=elapsed_ms,
                timestamp_utc=timestamp_utc(),
                response_snippet_redacted="",
                classification=classification,
                action=action,
                details={},
            )


async def diagnose_ws(name: str, url: str, stream: str, url_kind: str, *, timeout_seconds: int = 45) -> DiagnosisResult:
    started = time.perf_counter()
    details: dict[str, Any] = {"stream": stream}
    try:
        async with websockets.connect(url, ping_interval=180, ping_timeout=600) as ws:
            message = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
            payload = json.loads(message)
            if stream == LOCKED_STREAM_NAME:
                data = payload.get("data", payload)
                kline = data.get("k", {})
                details.update(
                    {
                        "contains_kline_closed_flag": "x" in kline,
                        "kline_x_false_seen": kline.get("x") is False,
                        "kline_x_true_seen": kline.get("x") is True,
                        "symbol": str(kline.get("s", "")).upper(),
                        "interval": str(kline.get("i", "")),
                    }
                )
            else:
                snapshot = snapshot_from_book_ticker_payload(payload)
                details.update(
                    {
                        "symbol": snapshot.symbol,
                        "contains_bid_ask_fields": True,
                        "best_bid_decimal": str(snapshot.best_bid_price),
                        "best_ask_decimal": str(snapshot.best_ask_price),
                    }
                )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return DiagnosisResult(
                name=name,
                environment="mainnet",
                transport="websocket",
                url_kind=url_kind,
                status_code=None,
                ok=True,
                error_type="",
                short_error_message="",
                elapsed_ms=elapsed_ms,
                timestamp_utc=timestamp_utc(),
                response_snippet_redacted=redacted_snippet(message),
                classification="ok",
                action="none",
                details=details,
            )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return DiagnosisResult(
            name=name,
            environment="mainnet",
            transport="websocket",
            url_kind=url_kind,
            status_code=None,
            ok=False,
            error_type=exc.__class__.__name__,
            short_error_message=redacted_snippet(str(exc), 160),
            elapsed_ms=elapsed_ms,
            timestamp_utc=timestamp_utc(),
            response_snippet_redacted="",
            classification="websocket_error",
            action="report_only",
            details=details,
        )


def skipped_testnet_ws() -> DiagnosisResult:
    return DiagnosisResult(
        name="testnet_websocket",
        environment="testnet",
        transport="websocket",
        url_kind="usds_m_futures_testnet_websocket",
        status_code=None,
        ok=False,
        error_type="skipped_not_implemented",
        short_error_message="testnet websocket diagnosis is skipped unless explicitly supported by the runtime",
        elapsed_ms=0,
        timestamp_utc=timestamp_utc(),
        response_snippet_redacted="",
        classification="skipped_not_implemented",
        action="none",
        details={},
    )


async def run_diagnosis() -> dict[str, Any]:
    targets = rest_targets()
    assert_public_only_targets(targets)
    rest_results = [await diagnose_rest_target(target) for target in targets]
    ws_results = [
        await diagnose_ws(
            "mainnet_kline_ws",
            MAINNET_KLINE_WS,
            LOCKED_STREAM_NAME,
            "usds_m_futures_mainnet_market_ws_kline",
        ),
        await diagnose_ws(
            "mainnet_bookticker_ws",
            MAINNET_BOOK_TICKER_WS,
            LOCKED_BOOK_TICKER_STREAM_NAME,
            "usds_m_futures_mainnet_public_ws_bookticker",
        ),
        skipped_testnet_ws(),
    ]
    results = rest_results + ws_results
    mainnet_rest_results = [result for result in rest_results if result.environment == "mainnet"]
    testnet_rest_results = [result for result in rest_results if result.environment == "testnet"]
    mainnet_rest_ok = all(result.ok for result in mainnet_rest_results)
    testnet_rest_ok = all(result.ok for result in testnet_rest_results)
    mainnet_rest_451_present = any(result.classification == "rest_451_blocked_no_bypass" for result in mainnet_rest_results)
    testnet_rest_451_present = any(result.classification == "rest_451_blocked_no_bypass" for result in testnet_rest_results)
    rest_451_present = mainnet_rest_451_present or testnet_rest_451_present
    if rest_451_present:
        gate_status = "blocked_rest_451_stop"
        fastest_safe_path = "change to a lawful server/location with Binance Futures REST access, then rerun F2"
    elif mainnet_rest_ok and testnet_rest_ok:
        gate_status = "passed_public_rest_may_request_f3"
        fastest_safe_path = "request explicit testnet signed-order preflight approval; do not place orders yet"
    elif testnet_rest_ok and not mainnet_rest_ok:
        gate_status = "blocked_live_mainnet_public_rest_failed"
        fastest_safe_path = "testnet may be considered only with explicit approval; live remains NO-GO"
    else:
        gate_status = "blocked_public_rest_failed"
        fastest_safe_path = "fix public REST reachability before signed-order or live work"
    return {
        "generated_at_utc": timestamp_utc(),
        "symbol": "ETHUSDC",
        "interval": "15m",
        "safety": {
            "public_only": True,
            "signed_requests": False,
            "order_requests": False,
            "proxy_or_bypass": False,
            "timeout_seconds_max": 10,
        },
        "results": [asdict(result) for result in results],
        "rest_451_present": rest_451_present,
        "mainnet_rest_451_present": mainnet_rest_451_present,
        "testnet_rest_451_present": testnet_rest_451_present,
        "mainnet_public_rest_ok": mainnet_rest_ok,
        "testnet_public_rest_ok": testnet_rest_ok,
        "websocket_kline_ok": any(result.name == "mainnet_kline_ws" and result.ok for result in results),
        "websocket_bookticker_ok": any(result.name == "mainnet_bookticker_ws" and result.ok for result in results),
        "gate_f2_status": gate_status,
        "fastest_safe_path": fastest_safe_path,
        "go_no_go": {
            "full_live_bot": "NO-GO",
            "testnet_order": "NO-GO" if rest_451_present else ("GO only for F3 preflight after explicit approval" if testnet_rest_ok else "NO-GO"),
            "live_canary": "NO-GO",
            "ws_only_dry_run": "GO" if any(result.name == "mainnet_kline_ws" and result.ok for result in results) else "NO-GO",
        },
    }


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# Fast Path Connectivity Diagnosis",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        "This diagnosis uses public endpoints only. It does not read API keys, sign requests, place orders, or bypass HTTP 451.",
        "",
        f"- REST 451 present: `{payload['rest_451_present']}`",
        f"- Mainnet public REST ok: `{payload['mainnet_public_rest_ok']}`",
        f"- Testnet public REST ok: `{payload['testnet_public_rest_ok']}`",
        f"- Gate F2 status: `{payload['gate_f2_status']}`",
        f"- Mainnet kline WebSocket ok: `{payload['websocket_kline_ok']}`",
        f"- Mainnet bookTicker WebSocket ok: `{payload['websocket_bookticker_ok']}`",
        f"- Fastest safe path: {payload['fastest_safe_path']}",
        "",
        "| Name | Env | Transport | OK | Status | Classification | Action | Error |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in payload["results"]:
        lines.append(
            "| {name} | {environment} | {transport} | {ok} | {status_code} | {classification} | {action} | {error_type} |".format(
                **result
            )
        )
    lines.extend(
        [
            "",
            "REST 451 classification: `rest_451_blocked_no_bypass`. No proxy, VPN, tunnel, or other bypass is allowed.",
            "",
            "Official API references checked for this gate:",
            "",
            "- Binance USD-M Futures Exchange Information: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information",
            "- Binance USD-M Futures New Order: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order",
            "- Binance USD-M Futures Kline WebSocket stream: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Kline-Candlestick-Streams",
            "- Binance USD-M Futures bookTicker WebSocket stream: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Individual-Symbol-Book-Ticker-Streams",
        ]
    )
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LEGACY_MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    payload = asyncio.run(run_diagnosis())
    JSON_REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    LEGACY_JSON_REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(payload)
    print(f"json_report={JSON_REPORT}")
    print(f"markdown_report={MD_REPORT}")
    print(f"rest_451_present={payload['rest_451_present']}")
    print(f"websocket_kline_ok={payload['websocket_kline_ok']}")
    print(f"websocket_bookticker_ok={payload['websocket_bookticker_ok']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
