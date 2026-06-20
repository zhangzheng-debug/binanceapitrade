from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bot.config import ConfigError, load_settings  # noqa: E402
from bot.exchange_filters import SymbolFilters, decimal_ceil_to_step, decimal_floor_to_step  # noqa: E402

REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
JSON_REPORT = REPORTS / "live_canary_order_control.json"
MD_REPORT = DOCS / "live_canary_order_control_report.md"

APPROVAL_ENV = "I_APPROVE_LIVE_ORDER_CONTROL_CANARY"
HEDGE_APPROVAL_ENV = "I_APPROVE_HEDGE_MODE_ORDER_CONTROL_CANARY"
EXPECTED_APPROVAL = "YES"
SYMBOL = "ETHUSDC"


@dataclass(slots=True)
class SignedCall:
    method: str
    path: str
    ok: bool
    status_code: int | None
    classification: str
    error: str = ""


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def compact_error(value: object, limit: int = 240) -> str:
    text = " ".join(str(value).replace("\r", " ").replace("\n", " ").split())
    return text.replace("signature=", "signature=<redacted>").replace("X-MBX-APIKEY", "X-MBX-APIKEY=<redacted>")[:limit]


def dec(value: Any) -> Decimal:
    return Decimal(str(value))


def fmt_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def order_id_tail(value: object) -> str:
    text = str(value or "")
    if len(text) <= 6:
        return text
    return f"...{text[-6:]}"


def client_id(prefix: str) -> str:
    return f"ec{prefix}{int(time.time() * 1000)}"


def hedge_position_side_for_order_side(side: str) -> str:
    if side == "BUY":
        return "LONG"
    if side == "SELL":
        return "SHORT"
    raise ValueError(f"unsupported side {side}")


def hedge_cleanup_order_for_row(row: dict[str, Any]) -> tuple[str, str, Decimal] | None:
    position_side = str(row.get("position_side", "")).upper()
    amount = dec(row.get("position_amt", "0"))
    if amount == 0:
        return None
    if position_side == "LONG" and amount > 0:
        return ("SELL", "LONG", amount)
    if position_side == "SHORT" and amount < 0:
        return ("BUY", "SHORT", abs(amount))
    return None


def side_safe_price(side: str, bid: Decimal, ask: Decimal, filters: SymbolFilters, *, modify: bool = False) -> Decimal:
    tick = filters.tick_size
    if bid <= 0 or ask <= 0 or bid >= ask:
        raise ValueError("invalid bid/ask for canary")
    distance = max(tick * Decimal("100"), (bid if side == "BUY" else ask) * Decimal("0.002"))
    if modify:
        distance += max(tick * Decimal("20"), (bid if side == "BUY" else ask) * Decimal("0.0005"))
    if side == "BUY":
        return decimal_floor_to_step(bid - distance, tick)
    if side == "SELL":
        return decimal_ceil_to_step(ask + distance, tick)
    raise ValueError(f"unsupported side {side}")


def canary_quantity(price: Decimal, filters: SymbolFilters, configured_notional: Decimal) -> Decimal:
    target_notional = max(configured_notional, filters.min_notional * Decimal("1.05"))
    raw_qty = target_notional / price
    qty = decimal_ceil_to_step(raw_qty, filters.step_size)
    if qty < filters.min_qty:
        qty = filters.min_qty
    if qty * price < filters.min_notional:
        qty = decimal_ceil_to_step(filters.min_notional / price, filters.step_size)
    return qty


def position_rows(payload: Any, symbol: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if str(item.get("symbol", "")).upper() == symbol.upper():
            amount = dec(item.get("positionAmt", "0"))
            rows.append(
                {
                    "symbol": symbol.upper(),
                    "position_side": str(item.get("positionSide", "BOTH")),
                    "position_amt": str(amount),
                    "abs_position_amt": str(abs(amount)),
                    "entry_price": str(item.get("entryPrice", "0")),
                }
            )
    return rows


def is_flat(rows: list[dict[str, Any]]) -> bool:
    return all(dec(row["position_amt"]) == 0 for row in rows)


def net_position_amount(rows: list[dict[str, Any]]) -> Decimal:
    total = Decimal("0")
    for row in rows:
        total += dec(row["position_amt"])
    return total


class CanaryClient:
    def __init__(self, *, base_url: str, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.calls: list[SignedCall] = []
        self.client = httpx.AsyncClient(base_url=base_url, timeout=10, trust_env=False)

    async def close(self) -> None:
        await self.client.aclose()

    async def public_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self.client.get(path, params=params or {})
        response.raise_for_status()
        return response.json()

    async def signed(self, method: str, path: str, params: dict[str, Any]) -> Any:
        clean = {key: value for key, value in params.items() if value is not None}
        clean["timestamp"] = int(time.time() * 1000)
        query = urlencode(clean)
        signature = hmac.new(self.api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
        headers = {"X-MBX-APIKEY": self.api_key}
        try:
            response = await self.client.request(method, f"{path}?{query}&signature={signature}", headers=headers)
            response.raise_for_status()
            self.calls.append(SignedCall(method, path, True, response.status_code, "ok"))
            return response.json()
        except httpx.HTTPStatusError as exc:
            classification = f"http_{exc.response.status_code}"
            self.calls.append(SignedCall(method, path, False, exc.response.status_code, classification, compact_error(exc.response.text)))
            raise
        except Exception as exc:
            self.calls.append(SignedCall(method, path, False, None, exc.__class__.__name__, compact_error(exc)))
            raise

    async def account(self) -> Any:
        return await self.signed("GET", "/fapi/v3/account", {})

    async def position_mode(self) -> Any:
        return await self.signed("GET", "/fapi/v1/positionSide/dual", {})

    async def positions(self, symbol: str) -> Any:
        return await self.signed("GET", "/fapi/v3/positionRisk", {"symbol": symbol})

    async def open_orders(self, symbol: str) -> Any:
        return await self.signed("GET", "/fapi/v1/openOrders", {"symbol": symbol})

    async def query_order(self, symbol: str, order_id: str) -> Any:
        return await self.signed("GET", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id})

    async def place_limit_gtx(
        self,
        *,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        cid: str,
        position_side: str | None = None,
    ) -> Any:
        return await self.signed(
            "POST",
            "/fapi/v1/order",
            {
                "symbol": symbol,
                "side": side,
                "positionSide": position_side,
                "type": "LIMIT",
                "timeInForce": "GTX",
                "quantity": fmt_decimal(quantity),
                "price": fmt_decimal(price),
                "newClientOrderId": cid,
            },
        )

    async def modify_order(self, *, symbol: str, side: str, order_id: str, quantity: Decimal, price: Decimal) -> Any:
        return await self.signed(
            "PUT",
            "/fapi/v1/order",
            {
                "symbol": symbol,
                "side": side,
                "orderId": order_id,
                "quantity": fmt_decimal(quantity),
                "price": fmt_decimal(price),
            },
        )

    async def cancel_order(self, *, symbol: str, order_id: str) -> Any:
        return await self.signed("DELETE", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id})

    async def market_reduce_only(self, *, symbol: str, side: str, quantity: Decimal) -> Any:
        return await self.signed(
            "POST",
            "/fapi/v1/order",
            {
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                "quantity": fmt_decimal(quantity),
                "reduceOnly": "true",
            },
        )

    async def market_close_hedge_position(self, *, symbol: str, side: str, position_side: str, quantity: Decimal) -> Any:
        return await self.signed(
            "POST",
            "/fapi/v1/order",
            {
                "symbol": symbol,
                "side": side,
                "positionSide": position_side,
                "type": "MARKET",
                "quantity": fmt_decimal(quantity),
            },
        )


async def get_public_ip() -> str:
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        response = await client.get("https://api.ipify.org")
        response.raise_for_status()
        return response.text.strip()


async def cleanup_if_needed(client: CanaryClient, symbol: str, payload: dict[str, Any], *, hedge_mode: bool) -> None:
    rows = position_rows(await client.positions(symbol), symbol)
    payload["cleanup"]["position_rows_before_cleanup"] = rows
    if is_flat(rows):
        return
    if hedge_mode:
        cleanup_orders = [order for row in rows if (order := hedge_cleanup_order_for_row(row)) is not None]
        if not cleanup_orders:
            payload["cleanup"]["error"] = "non-flat hedge rows could not be mapped to close orders; manual reconciliation required"
            return
        for side, position_side, qty in cleanup_orders:
            payload["hedge_mode_market_cleanup_count"] += 1
            await client.market_close_hedge_position(symbol=symbol, side=side, position_side=position_side, quantity=qty)
        final_rows = position_rows(await client.positions(symbol), symbol)
        payload["cleanup"]["position_rows_after_cleanup"] = final_rows
        return
    net = net_position_amount(rows)
    if net == 0:
        payload["cleanup"]["error"] = "non-flat hedge rows with zero net; manual reconciliation required"
        return
    side = "SELL" if net > 0 else "BUY"
    qty = abs(net)
    payload["reduceOnly_market_cleanup_count"] += 1
    await client.market_reduce_only(symbol=symbol, side=side, quantity=qty)
    final_rows = position_rows(await client.positions(symbol), symbol)
    payload["cleanup"]["position_rows_after_cleanup"] = final_rows


async def run_side(
    client: CanaryClient,
    *,
    symbol: str,
    side: str,
    filters: SymbolFilters,
    configured_notional: Decimal,
    hedge_mode: bool,
) -> dict[str, Any]:
    ticker = await client.public_get("/fapi/v1/ticker/bookTicker", {"symbol": symbol})
    bid = dec(ticker["bidPrice"])
    ask = dec(ticker["askPrice"])
    price = side_safe_price(side, bid, ask, filters, modify=False)
    modified_price = side_safe_price(side, bid, ask, filters, modify=True)
    qty = canary_quantity(price, filters, configured_notional)
    result: dict[str, Any] = {
        "side": side,
        "position_side": hedge_position_side_for_order_side(side) if hedge_mode else "BOTH",
        "best_bid": str(bid),
        "best_ask": str(ask),
        "place_price": str(price),
        "modify_price": str(modified_price),
        "quantity": str(qty),
        "target_notional": str(qty * price),
        "place_status": "",
        "modify_status": "",
        "cancel_status": "",
        "order_id_tail": "",
        "executed_qty": "0",
        "unexpected_fill": False,
        "place_attempt_count": 0,
        "modify_attempt_count": 0,
        "cancel_attempt_count": 0,
        "ok": False,
    }
    order_id = ""
    try:
        result["place_attempt_count"] += 1
        placed = await client.place_limit_gtx(
            symbol=symbol,
            side=side,
            quantity=qty,
            price=price,
            cid=client_id("B" if side == "BUY" else "S"),
            position_side=hedge_position_side_for_order_side(side) if hedge_mode else None,
        )
        order_id = str(placed.get("orderId"))
        result["order_id_tail"] = order_id_tail(order_id)
        result["place_status"] = str(placed.get("status", ""))
        result["executed_qty"] = str(placed.get("executedQty", "0"))
        query1 = await client.query_order(symbol, order_id)
        result["query_status"] = str(query1.get("status", ""))
        result["query_executed_qty"] = str(query1.get("executedQty", "0"))
        result["modify_attempt_count"] += 1
        modified = await client.modify_order(symbol=symbol, side=side, order_id=order_id, quantity=qty, price=modified_price)
        result["modify_status"] = str(modified.get("status", ""))
        result["modify_executed_qty"] = str(modified.get("executedQty", "0"))
        query2 = await client.query_order(symbol, order_id)
        result["query_after_modify_status"] = str(query2.get("status", ""))
        result["cancel_attempt_count"] += 1
        canceled = await client.cancel_order(symbol=symbol, order_id=order_id)
        result["cancel_status"] = str(canceled.get("status", ""))
        result["cancel_executed_qty"] = str(canceled.get("executedQty", "0"))
    except Exception as exc:
        result["error"] = {"type": exc.__class__.__name__, "message": compact_error(exc)}
        if order_id and result.get("cancel_status") != "CANCELED":
            try:
                result["cancel_attempt_count"] += 1
                canceled = await client.cancel_order(symbol=symbol, order_id=order_id)
                result["cancel_status"] = str(canceled.get("status", ""))
                result["cancel_executed_qty"] = str(canceled.get("executedQty", "0"))
            except Exception as cancel_exc:
                result["cancel_error"] = {"type": cancel_exc.__class__.__name__, "message": compact_error(cancel_exc)}
    executed_values = [
        dec(result.get("executed_qty", "0")),
        dec(result.get("query_executed_qty", "0")),
        dec(result.get("modify_executed_qty", "0")),
        dec(result.get("cancel_executed_qty", "0")),
    ]
    result["unexpected_fill"] = any(value > 0 for value in executed_values)
    result["ok"] = result["place_status"] in {"NEW", "PARTIALLY_FILLED"} and result["modify_status"] in {"NEW", "PARTIALLY_FILLED"} and result["cancel_status"] == "CANCELED" and not result["unexpected_fill"] and "error" not in result
    return result


async def run_canary() -> dict[str, Any]:
    settings = load_settings()
    payload: dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "server_public_ip": "",
        "expected_whitelist_ip": settings.api_key_ip_whitelist_expected or "167.172.69.16",
        "ip_match": False,
        "symbol": settings.binance_symbol,
        "live_trading_started": False,
        "full_strategy_started": False,
        "key_secret_printed": False,
        "approval_env_present": os.environ.get(APPROVAL_ENV) == EXPECTED_APPROVAL,
        "order_mode": settings.order_mode,
        "position_size_pct": str(settings.position_size_pct),
        "exchange_info_source": "",
        "filters": {},
        "position_mode_dual_side": None,
        "hedge_mode_approval_env_present": os.environ.get(HEDGE_APPROVAL_ENV) == EXPECTED_APPROVAL,
        "account_can_trade": None,
        "initial_open_orders_count": None,
        "initial_position_rows": [],
        "buy": None,
        "sell": None,
        "final_open_orders_count": None,
        "final_position_rows": [],
        "unexpected_fill": False,
        "emergency_cleanup_triggered": False,
        "cleanup": {},
        "real_order_attempt_count": 0,
        "limit_gtx_order_attempt_count": 0,
        "modify_order_attempt_count": 0,
        "cancel_order_attempt_count": 0,
        "market_entry_attempt_count": 0,
        "stop_market_entry_attempt_count": 0,
        "reduceOnly_market_cleanup_count": 0,
        "hedge_mode_market_cleanup_count": 0,
        "signed_calls": [],
        "final_verdict": "LIVE_ORDER_CONTROL_CANARY_NO_GO",
    }
    if os.environ.get(APPROVAL_ENV) != EXPECTED_APPROVAL:
        payload["error"] = f"missing {APPROVAL_ENV}=YES"
        return payload
    if settings.live_trading:
        payload["error"] = "LIVE_TRADING must remain false for order-control canary"
        return payload
    if settings.binance_symbol != SYMBOL or settings.binance_interval != "15m":
        payload["error"] = "canary only supports ETHUSDC 15m configuration"
        return payload
    if not settings.binance_api_key or not settings.binance_api_secret:
        payload["error"] = "API credentials are required"
        return payload

    client = CanaryClient(base_url=settings.rest_base_url, api_key=settings.binance_api_key, api_secret=settings.binance_api_secret)
    hedge_mode = False
    try:
        public_ip = await get_public_ip()
        payload["server_public_ip"] = public_ip
        payload["ip_match"] = public_ip == payload["expected_whitelist_ip"]
        if not payload["ip_match"]:
            payload["error"] = "server public IP does not match expected whitelist"
            return payload

        exchange_info = await client.public_get("/fapi/v1/exchangeInfo")
        filters = SymbolFilters.from_exchange_info(exchange_info, settings.binance_symbol)
        payload["exchange_info_source"] = filters.source.value
        payload["filters"] = {
            "tick_size": str(filters.tick_size),
            "step_size": str(filters.step_size),
            "min_qty": str(filters.min_qty),
            "min_notional": str(filters.min_notional),
        }

        account = await client.account()
        payload["account_can_trade"] = account.get("canTrade") if isinstance(account, dict) else None
        position_mode = await client.position_mode()
        dual_side = bool(position_mode.get("dualSidePosition")) if isinstance(position_mode, dict) else None
        hedge_mode = bool(dual_side)
        payload["position_mode_dual_side"] = dual_side
        initial_orders = await client.open_orders(settings.binance_symbol)
        initial_positions = position_rows(await client.positions(settings.binance_symbol), settings.binance_symbol)
        payload["initial_open_orders_count"] = len(initial_orders) if isinstance(initial_orders, list) else -1
        payload["initial_position_rows"] = initial_positions
        payload["final_open_orders_count"] = payload["initial_open_orders_count"]
        payload["final_position_rows"] = initial_positions
        if hedge_mode and not payload["hedge_mode_approval_env_present"]:
            payload["error"] = (
                f"hedge mode account detected; set {HEDGE_APPROVAL_ENV}=YES to explicitly approve the Hedge Mode "
                "order-control canary. Without that second gate this script only performs signed read-only checks."
            )
            return payload
        if payload["initial_open_orders_count"] != 0:
            payload["error"] = "initial ETHUSDC open orders not zero"
            return payload
        if not is_flat(initial_positions):
            payload["error"] = "initial ETHUSDC position not flat"
            return payload

        configured_notional = Decimal(str(os.environ.get("LIVE_CANARY_NOTIONAL_USDC") or "10"))
        buy_result = await run_side(
            client,
            symbol=settings.binance_symbol,
            side="BUY",
            filters=filters,
            configured_notional=configured_notional,
            hedge_mode=hedge_mode,
        )
        payload["buy"] = buy_result
        payload["limit_gtx_order_attempt_count"] += int(buy_result.get("place_attempt_count", 0))
        payload["real_order_attempt_count"] += int(buy_result.get("place_attempt_count", 0))
        payload["modify_order_attempt_count"] += int(buy_result.get("modify_attempt_count", 0))
        payload["cancel_order_attempt_count"] += int(buy_result.get("cancel_attempt_count", 0))
        if buy_result["unexpected_fill"]:
            payload["unexpected_fill"] = True
            payload["emergency_cleanup_triggered"] = True
            await cleanup_if_needed(client, settings.binance_symbol, payload, hedge_mode=hedge_mode)

        sell_result = await run_side(
            client,
            symbol=settings.binance_symbol,
            side="SELL",
            filters=filters,
            configured_notional=configured_notional,
            hedge_mode=hedge_mode,
        )
        payload["sell"] = sell_result
        payload["limit_gtx_order_attempt_count"] += int(sell_result.get("place_attempt_count", 0))
        payload["real_order_attempt_count"] += int(sell_result.get("place_attempt_count", 0))
        payload["modify_order_attempt_count"] += int(sell_result.get("modify_attempt_count", 0))
        payload["cancel_order_attempt_count"] += int(sell_result.get("cancel_attempt_count", 0))
        if sell_result["unexpected_fill"]:
            payload["unexpected_fill"] = True
            payload["emergency_cleanup_triggered"] = True
            await cleanup_if_needed(client, settings.binance_symbol, payload, hedge_mode=hedge_mode)

        final_orders = await client.open_orders(settings.binance_symbol)
        final_positions = position_rows(await client.positions(settings.binance_symbol), settings.binance_symbol)
        payload["final_open_orders_count"] = len(final_orders) if isinstance(final_orders, list) else -1
        payload["final_position_rows"] = final_positions
        payload["signed_calls"] = [asdict(call) for call in client.calls]
        if (
            buy_result.get("ok")
            and sell_result.get("ok")
            and payload["final_open_orders_count"] == 0
            and is_flat(final_positions)
            and not payload["unexpected_fill"]
            and payload["market_entry_attempt_count"] == 0
            and payload["stop_market_entry_attempt_count"] == 0
            and (not hedge_mode or payload["hedge_mode_approval_env_present"])
        ):
            payload["final_verdict"] = "LIVE_ORDER_CONTROL_CANARY_GO"
        return payload
    except Exception as exc:
        payload["error"] = {"type": exc.__class__.__name__, "message": compact_error(exc)}
        try:
            payload["emergency_cleanup_triggered"] = True
            await cleanup_if_needed(client, settings.binance_symbol, payload, hedge_mode=hedge_mode)
            final_orders = await client.open_orders(settings.binance_symbol)
            final_positions = position_rows(await client.positions(settings.binance_symbol), settings.binance_symbol)
            payload["final_open_orders_count"] = len(final_orders) if isinstance(final_orders, list) else -1
            payload["final_position_rows"] = final_positions
        except Exception as cleanup_exc:
            payload["cleanup_error"] = {"type": cleanup_exc.__class__.__name__, "message": compact_error(cleanup_exc)}
        return payload
    finally:
        payload["signed_calls"] = [asdict(call) for call in client.calls]
        await client.close()


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# Live Order-Control Canary Report",
        "",
        f"Generated UTC: `{payload.get('generated_at_utc')}`",
        "",
        "- Scope: direct ETHUSDC order-control canary only; full strategy was not started.",
        "- Entry order type: `LIMIT + GTX` only.",
        "- MARKET is forbidden for entry. Emergency cleanup is reduceOnly in One-way Mode; in Hedge Mode it requires explicit approval and exact `positionSide` close orders because Binance disallows reduceOnly there.",
        "",
        f"- Server public IP: `{payload.get('server_public_ip')}`",
        f"- Expected whitelist IP: `{payload.get('expected_whitelist_ip')}`",
        f"- IP match: `{payload.get('ip_match')}`",
        f"- ExchangeInfo source: `{payload.get('exchange_info_source')}`",
        f"- Position mode dual-side: `{payload.get('position_mode_dual_side')}`",
        f"- Hedge Mode approval env present: `{payload.get('hedge_mode_approval_env_present')}`",
        f"- Account can trade: `{payload.get('account_can_trade')}`",
        f"- Initial open orders count: `{payload.get('initial_open_orders_count')}`",
        f"- Final open orders count: `{payload.get('final_open_orders_count')}`",
        f"- Final position rows: `{payload.get('final_position_rows')}`",
        "",
        "## Orders",
        "",
        f"- BUY result: `{payload.get('buy')}`",
        f"- SELL result: `{payload.get('sell')}`",
        "",
        "## Safety Counters",
        "",
        f"- Real order attempts: `{payload.get('real_order_attempt_count')}`",
        f"- LIMIT GTX order attempts: `{payload.get('limit_gtx_order_attempt_count')}`",
        f"- Modify attempts: `{payload.get('modify_order_attempt_count')}`",
        f"- Cancel attempts: `{payload.get('cancel_order_attempt_count')}`",
        f"- Market entry attempts: `{payload.get('market_entry_attempt_count')}`",
        f"- STOP_MARKET entry attempts: `{payload.get('stop_market_entry_attempt_count')}`",
        f"- reduceOnly MARKET cleanup count: `{payload.get('reduceOnly_market_cleanup_count')}`",
        f"- Hedge Mode non-reduceOnly MARKET cleanup count: `{payload.get('hedge_mode_market_cleanup_count')}`",
        f"- Unexpected fill: `{payload.get('unexpected_fill')}`",
        f"- Emergency cleanup triggered: `{payload.get('emergency_cleanup_triggered')}`",
        f"- Full strategy started: `{payload.get('full_strategy_started')}`",
        f"- Live trading started by bot.main: `{payload.get('live_trading_started')}`",
        f"- Key/secret printed: `{payload.get('key_secret_printed')}`",
        "",
        f"Final verdict: `{payload.get('final_verdict')}`",
    ]
    if payload.get("error"):
        lines.extend(["", "## Error", "", f"`{payload['error']}`"])
    if payload.get("cleanup_error"):
        lines.extend(["", "## Cleanup Error", "", f"`{payload['cleanup_error']}`"])
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    payload = asyncio.run(run_canary())
    JSON_REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(payload)
    print(f"json_report={JSON_REPORT}")
    print(f"markdown_report={MD_REPORT}")
    print(f"final_verdict={payload['final_verdict']}")
    print(f"final_open_orders_count={payload.get('final_open_orders_count')}")
    print(f"unexpected_fill={payload.get('unexpected_fill')}")
    print(f"reduceOnly_market_cleanup_count={payload.get('reduceOnly_market_cleanup_count')}")
    print(f"hedge_mode_market_cleanup_count={payload.get('hedge_mode_market_cleanup_count')}")
    return 0 if payload["final_verdict"] == "LIVE_ORDER_CONTROL_CANARY_GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
