from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import time
import urllib.parse
from datetime import UTC, datetime
from typing import Any

from check_binance_futures_rest import JSON_REPORT, MD_REPORT, decision_codes, write_report

TARGETS = [
    (
        "mainnet_kline_ws",
        "mainnet",
        "wss://fstream.binance.com/market/stream?streams=ethusdc@kline_15m",
        "ethusdc@kline_15m",
    ),
    (
        "mainnet_bookticker_ws",
        "mainnet",
        "wss://fstream.binance.com/public/stream?streams=ethusdc@bookTicker",
        "ethusdc@bookTicker",
    ),
]

WS_ACCEPT_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def timestamp_utc() -> str:
    return datetime.now(tz=UTC).isoformat()


def redacted_error(exc: BaseException) -> str:
    return " ".join(str(exc).replace("\r", " ").replace("\n", " ").split())[:180]


def read_until(sock: ssl.SSLSocket, marker: bytes, limit: int = 65536) -> bytes:
    data = b""
    while marker not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("connection closed before websocket handshake completed")
        data += chunk
        if len(data) > limit:
            raise ConnectionError("websocket handshake response too large")
    return data


def read_exact(sock: ssl.SSLSocket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("connection closed while reading websocket frame")
        data += chunk
    return data


def read_text_frame(sock: ssl.SSLSocket, timeout_seconds: int = 30) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        sock.settimeout(max(0.1, deadline - time.monotonic()))
        first, second = read_exact(sock, 2)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", read_exact(sock, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", read_exact(sock, 8))[0]
        mask = read_exact(sock, 4) if masked else b""
        payload = read_exact(sock, length) if length else b""
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        if opcode == 0x1:
            return payload.decode("utf-8", errors="replace")
        if opcode == 0x8:
            raise ConnectionError("websocket close frame received")
    raise TimeoutError("timed out waiting for websocket message")


def websocket_message(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "wss" or not parsed.hostname:
        raise ValueError(f"unsupported websocket url: {url}")
    host = parsed.hostname
    port = parsed.port or 443
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    expected_accept = base64.b64encode(hashlib.sha1(f"{key}{WS_ACCEPT_GUID}".encode("ascii")).digest()).decode("ascii")
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "User-Agent: ethusdc-pivot-bot-f2-checker\r\n"
        "\r\n"
    )
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=10) as raw_sock:
        with context.wrap_socket(raw_sock, server_hostname=host) as sock:
            sock.settimeout(10)
            sock.sendall(request.encode("ascii"))
            header = read_until(sock, b"\r\n\r\n")
            header_text = header.decode("iso-8859-1", errors="replace")
            first_line = header_text.split("\r\n", 1)[0]
            if " 101 " not in first_line:
                raise ConnectionError(f"websocket upgrade failed: {first_line}")
            accept_header = ""
            for line in header_text.split("\r\n")[1:]:
                name, _, value = line.partition(":")
                if name.lower() == "sec-websocket-accept":
                    accept_header = value.strip()
                    break
            if accept_header and accept_header != expected_accept:
                raise ConnectionError("websocket accept header mismatch")
            return read_text_frame(sock)


def check_ws(name: str, environment: str, url: str, stream: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        payload = json.loads(websocket_message(url))
        data = payload.get("data", payload)
        details: dict[str, Any] = {"stream": stream}
        if "kline" in stream:
            kline = data.get("k", {})
            details.update({"symbol": kline.get("s"), "interval": kline.get("i"), "contains_closed_flag": "x" in kline})
        else:
            details.update({"symbol": data.get("s"), "contains_bid_ask": "b" in data and "a" in data})
        return {
            "name": name,
            "environment": environment,
            "transport": "websocket",
            "url": url,
            "ok": True,
            "status_code": None,
            "classification": "ok",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "error": "",
            "details": details,
        }
    except Exception as exc:
        return {
            "name": name,
            "environment": environment,
            "transport": "websocket",
            "url": url,
            "ok": False,
            "status_code": None,
            "classification": "websocket_error",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "error": redacted_error(exc),
            "details": {"stream": stream},
        }


def run() -> dict[str, Any]:
    if JSON_REPORT.exists():
        payload = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    else:
        payload = {
            "generated_at_utc": timestamp_utc(),
            "symbol": "ETHUSDC",
            "safety": {
                "public_only": True,
                "api_keys_read": False,
                "signed_rest": False,
                "orders": False,
                "proxy_vpn_tunnel_bypass": False,
            },
            "results": [],
        }
    existing = [result for result in payload["results"] if result.get("transport") != "websocket"]
    ws_results = [check_ws(*target) for target in TARGETS]
    payload["generated_at_utc"] = timestamp_utc()
    payload["results"] = existing + ws_results
    payload["decision_codes"] = decision_codes(payload)
    return payload


def main() -> int:
    payload = run()
    JSON_REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_report(payload)
    print(f"json_report={JSON_REPORT}")
    print(f"markdown_report={MD_REPORT}")
    print(f"decision_codes={','.join(payload['decision_codes'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
