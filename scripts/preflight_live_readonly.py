from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bot.config import ConfigError, load_settings  # noqa: E402
from bot.exchange_filters import SymbolFilters  # noqa: E402

REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
JSON_REPORT = REPORTS / "live_readonly_preflight.json"
MD_REPORT = DOCS / "live_readonly_preflight_report.md"

READONLY_SIGNED_ENDPOINTS = {
    ("GET", "/fapi/v3/account"),
    ("GET", "/fapi/v3/positionRisk"),
    ("GET", "/fapi/v1/openOrders"),
}
FORBIDDEN_ENDPOINT_FRAGMENTS = (
    "POST /fapi/v1/order",
    "PUT /fapi/v1/order",
    "DELETE /fapi/v1/order",
    "POST /fapi/v1/batchOrders",
    "POST /fapi/v1/algoOrder",
    "DELETE /fapi/v1/algoOrder",
    "DELETE /fapi/v1/algoOpenOrders",
    "POST /fapi/v1/leverage",
    "POST /fapi/v1/marginType",
    "POST /fapi/v1/positionSide/dual",
)


@dataclass(slots=True)
class RequestAudit:
    method: str
    path: str
    signed: bool
    ok: bool
    status_code: int | None
    classification: str
    error: str


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def redact_message(value: object, limit: int = 220) -> str:
    text = " ".join(str(value).replace("\r", " ").replace("\n", " ").split())
    for token in ("signature=", "X-MBX-APIKEY"):
        text = text.replace(token, f"{token}<redacted>")
    return text[:limit]


def assert_readonly_signed_endpoint(method: str, path: str) -> None:
    normalized = (method.upper(), path)
    if normalized not in READONLY_SIGNED_ENDPOINTS:
        raise RuntimeError(f"forbidden signed endpoint for read-only preflight: {method.upper()} {path}")


def order_endpoint_called(calls: list[RequestAudit]) -> bool:
    return any(
        f"{call.method.upper()} {call.path}" in FORBIDDEN_ENDPOINT_FRAGMENTS
        or (call.method.upper() in {"POST", "PUT", "DELETE"} and "/order" in call.path)
        for call in calls
    )


def position_amount_from_payload(payload: Any, symbol: str) -> Decimal:
    if not isinstance(payload, list):
        return Decimal("0")
    total = Decimal("0")
    for item in payload:
        if str(item.get("symbol", "")).upper() != symbol.upper():
            continue
        total += Decimal(str(item.get("positionAmt", "0")))
    return total


def account_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"account_query_shape": type(payload).__name__}
    assets = payload.get("assets") if isinstance(payload.get("assets"), list) else []
    positions = payload.get("positions") if isinstance(payload.get("positions"), list) else []
    return {
        "account_query_shape": "dict",
        "assets_count": len(assets),
        "positions_count": len(positions),
        "assets_present": sorted(str(asset.get("asset", "")) for asset in assets if asset.get("asset")),
        "can_trade": payload.get("canTrade"),
        "multi_assets_margin": payload.get("multiAssetsMargin"),
    }


class ReadOnlyBinanceClient:
    def __init__(self, *, base_url: str, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.calls: list[RequestAudit] = []
        self.client = httpx.AsyncClient(base_url=base_url, timeout=10, trust_env=False)

    async def close(self) -> None:
        await self.client.aclose()

    async def public_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = await self.client.get(path, params=params or {})
            response.raise_for_status()
            self.calls.append(RequestAudit("GET", path, signed=False, ok=True, status_code=response.status_code, classification="ok", error=""))
            return response.json()
        except httpx.HTTPStatusError as exc:
            self.calls.append(
                RequestAudit(
                    "GET",
                    path,
                    signed=False,
                    ok=False,
                    status_code=exc.response.status_code,
                    classification=f"http_{exc.response.status_code}",
                    error=redact_message(exc.response.text),
                )
            )
            raise
        except Exception as exc:
            self.calls.append(
                RequestAudit(
                    "GET",
                    path,
                    signed=False,
                    ok=False,
                    status_code=None,
                    classification=exc.__class__.__name__,
                    error=redact_message(exc),
                )
            )
            raise

    async def signed_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        assert_readonly_signed_endpoint("GET", path)
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        clean_params["timestamp"] = int(time.time() * 1000)
        query = urlencode(clean_params)
        signature = hmac.new(self.api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
        signed_query = f"{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self.api_key}
        try:
            response = await self.client.get(f"{path}?{signed_query}", headers=headers)
            response.raise_for_status()
            self.calls.append(RequestAudit("GET", path, signed=True, ok=True, status_code=response.status_code, classification="ok", error=""))
            return response.json()
        except httpx.HTTPStatusError as exc:
            classification = f"http_{exc.response.status_code}"
            body = exc.response.text
            if "-1021" in body:
                classification = "timestamp_drift"
            elif exc.response.status_code in {401, 403}:
                classification = "permission_or_ip_whitelist_error"
            self.calls.append(
                RequestAudit(
                    "GET",
                    path,
                    signed=True,
                    ok=False,
                    status_code=exc.response.status_code,
                    classification=classification,
                    error=redact_message(body),
                )
            )
            raise
        except Exception as exc:
            self.calls.append(
                RequestAudit(
                    "GET",
                    path,
                    signed=True,
                    ok=False,
                    status_code=None,
                    classification=exc.__class__.__name__,
                    error=redact_message(exc),
                )
            )
            raise


async def get_public_ip() -> str:
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        response = await client.get("https://api.ipify.org")
        response.raise_for_status()
        return response.text.strip()


async def run_preflight() -> dict[str, Any]:
    settings = load_settings()
    if settings.live_trading:
        raise ConfigError("LIVE_TRADING must be false for signed read-only preflight")
    if not settings.binance_api_key or not settings.binance_api_secret:
        raise ConfigError("BINANCE_API_KEY and BINANCE_API_SECRET are required for signed read-only preflight")
    if settings.binance_env != "mainnet":
        raise ConfigError("signed read-only preflight must use BINANCE_ENV=mainnet")

    expected_ip = str(getattr(settings, "api_key_ip_whitelist_expected", "") or "")
    if not expected_ip:
        expected_ip = "167.172.69.16"

    payload: dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "server_public_ip": "",
        "expected_whitelist_ip": expected_ip,
        "ip_match": False,
        "symbol": settings.binance_symbol,
        "interval": settings.binance_interval,
        "strategy_variant": settings.strategy_variant,
        "live_trading_started": False,
        "key_secret_printed": False,
        "order_endpoint_called": False,
        "position_size_pct": str(settings.position_size_pct),
        "order_mode": settings.order_mode,
        "checks": {},
        "requests": [],
        "final_verdict": "SIGNED_READONLY_PREFLIGHT_NO_GO",
    }

    client = ReadOnlyBinanceClient(
        base_url=settings.rest_base_url,
        api_key=settings.binance_api_key,
        api_secret=settings.binance_api_secret,
    )
    try:
        public_ip = await get_public_ip()
        payload["server_public_ip"] = public_ip
        payload["ip_match"] = public_ip == expected_ip
        payload["checks"]["server_public_ip"] = {"ok": payload["ip_match"]}

        server_time = await client.public_get("/fapi/v1/time")
        server_time_ms = int(server_time["serverTime"])
        local_time_ms = int(time.time() * 1000)
        drift_ms = abs(server_time_ms - local_time_ms)
        payload["checks"]["server_time"] = {"ok": True, "timestamp_drift_ms": drift_ms}

        exchange_info = await client.public_get("/fapi/v1/exchangeInfo")
        filters = SymbolFilters.from_exchange_info(exchange_info, settings.binance_symbol)
        payload["checks"]["exchange_info"] = {
            "ok": True,
            "filters_source": filters.source.value,
            "safe_for_live": filters.safe_for_live,
            "tick_size": str(filters.tick_size),
            "step_size": str(filters.step_size),
            "min_qty": str(filters.min_qty),
            "min_notional": str(filters.min_notional),
        }

        account = await client.signed_get("/fapi/v3/account")
        payload["checks"]["account"] = {"ok": True, **account_summary(account)}

        position_payload = await client.signed_get("/fapi/v3/positionRisk", {"symbol": settings.binance_symbol})
        position_amt = position_amount_from_payload(position_payload, settings.binance_symbol)
        payload["checks"]["position"] = {
            "ok": True,
            "ethusdc_position_amt": str(position_amt),
            "is_flat": position_amt == 0,
        }

        open_orders = await client.signed_get("/fapi/v1/openOrders", {"symbol": settings.binance_symbol})
        open_orders_count = len(open_orders) if isinstance(open_orders, list) else -1
        payload["checks"]["open_orders"] = {
            "ok": isinstance(open_orders, list),
            "ethusdc_open_orders_count": open_orders_count,
        }

        payload["order_endpoint_called"] = order_endpoint_called(client.calls)
        payload["requests"] = [asdict(call) for call in client.calls]
        go = all(
            [
                payload["ip_match"],
                payload["checks"]["server_time"]["ok"],
                drift_ms < 5000,
                payload["checks"]["exchange_info"]["ok"],
                payload["checks"]["exchange_info"]["filters_source"] == "EXCHANGE_INFO_REST",
                payload["checks"]["account"]["ok"],
                payload["checks"]["position"]["ok"],
                payload["checks"]["position"]["is_flat"],
                payload["checks"]["open_orders"]["ok"],
                payload["checks"]["open_orders"]["ethusdc_open_orders_count"] == 0,
                not payload["order_endpoint_called"],
                not payload["live_trading_started"],
            ]
        )
        payload["final_verdict"] = "SIGNED_READONLY_PREFLIGHT_GO" if go else "SIGNED_READONLY_PREFLIGHT_NO_GO"
        return payload
    except Exception as exc:
        payload["error"] = {"type": exc.__class__.__name__, "message": redact_message(exc)}
        payload["order_endpoint_called"] = order_endpoint_called(client.calls)
        payload["requests"] = [asdict(call) for call in client.calls]
        return payload
    finally:
        await client.close()


def write_markdown(payload: dict[str, Any]) -> None:
    checks = payload.get("checks", {})
    lines = [
        "# Live Read-Only Preflight Report",
        "",
        f"Generated UTC: `{payload.get('generated_at_utc')}`",
        "",
        "- Scope: Binance USD-M Futures mainnet signed read-only preflight.",
        "- Order placement/modify/cancel endpoints are forbidden in this script.",
        "- API key and secret are not printed in this report.",
        "",
        f"- Server public IP: `{payload.get('server_public_ip')}`",
        f"- Expected whitelist IP: `{payload.get('expected_whitelist_ip')}`",
        f"- IP match: `{payload.get('ip_match')}`",
        f"- Symbol: `{payload.get('symbol')}`",
        f"- Interval: `{payload.get('interval')}`",
        f"- Strategy variant: `{payload.get('strategy_variant')}`",
        f"- Order mode configured: `{payload.get('order_mode')}`",
        f"- Position size pct configured: `{payload.get('position_size_pct')}`",
        "",
        "## Checks",
        "",
        f"- Server time OK: `{checks.get('server_time', {}).get('ok')}`",
        f"- Timestamp drift ms: `{checks.get('server_time', {}).get('timestamp_drift_ms')}`",
        f"- ExchangeInfo OK: `{checks.get('exchange_info', {}).get('ok')}`",
        f"- Filters source: `{checks.get('exchange_info', {}).get('filters_source')}`",
        f"- Tick size: `{checks.get('exchange_info', {}).get('tick_size')}`",
        f"- Step size: `{checks.get('exchange_info', {}).get('step_size')}`",
        f"- Min qty: `{checks.get('exchange_info', {}).get('min_qty')}`",
        f"- Min notional: `{checks.get('exchange_info', {}).get('min_notional')}`",
        f"- Signed account query OK: `{checks.get('account', {}).get('ok')}`",
        f"- Position query OK: `{checks.get('position', {}).get('ok')}`",
        f"- ETHUSDC position amount: `{checks.get('position', {}).get('ethusdc_position_amt')}`",
        f"- OpenOrders query OK: `{checks.get('open_orders', {}).get('ok')}`",
        f"- ETHUSDC open orders count: `{checks.get('open_orders', {}).get('ethusdc_open_orders_count')}`",
        "",
        "## Safety",
        "",
        f"- Key/secret printed: `{payload.get('key_secret_printed')}`",
        f"- Order endpoint called: `{payload.get('order_endpoint_called')}`",
        f"- Live trading started: `{payload.get('live_trading_started')}`",
        "",
        f"Final verdict: `{payload.get('final_verdict')}`",
    ]
    if payload.get("error"):
        lines.extend(["", "## Error", "", f"- Type: `{payload['error'].get('type')}`", f"- Message: `{payload['error'].get('message')}`"])
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    payload = asyncio.run(run_preflight())
    JSON_REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(payload)
    print(f"json_report={JSON_REPORT}")
    print(f"markdown_report={MD_REPORT}")
    print(f"final_verdict={payload['final_verdict']}")
    print(f"order_endpoint_called={payload['order_endpoint_called']}")
    print(f"live_trading_started={payload['live_trading_started']}")
    return 0 if payload["final_verdict"] == "SIGNED_READONLY_PREFLIGHT_GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
