from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal
from urllib.parse import urlencode

import httpx

from bot.config import Settings
from bot.dry_run_exchange import (
    ExchangeError,
    ExchangeFilterFailure,
    NetworkTimeout,
    RateLimit,
    TimestampDrift,
    UnknownExchangeError,
)
from bot.models import BookTicker, OrderRequest, OrderState, OrderStatus, OrderType, Position, PositionSide, Side, TimeInForce
from bot.safety import SignedOrderForbiddenInDryRun, assert_no_signed_order_allowed


class LiveTradingDisabled(SignedOrderForbiddenInDryRun, ExchangeError):
    pass


class BinanceClient:
    """Minimal USD-M Futures REST adapter.

    Docs checked 2026-06-20:
    - New Order: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api
    - Modify Order: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Modify-Order
    - Exchange Info: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(base_url=settings.rest_base_url, timeout=10)

    async def close(self) -> None:
        await self.client.aclose()

    async def exchange_info(self) -> dict:
        response = await self.client.get("/fapi/v1/exchangeInfo")
        response.raise_for_status()
        return response.json()

    async def book_ticker(self, symbol: str) -> dict:
        response = await self.client.get("/fapi/v1/ticker/bookTicker", params={"symbol": symbol})
        response.raise_for_status()
        return response.json()

    async def get_book_ticker(self, symbol: str) -> BookTicker:
        payload = await self.book_ticker(symbol)
        return BookTicker(
            symbol=str(payload["symbol"]),
            bid_price=Decimal(str(payload["bidPrice"])),
            bid_qty=Decimal(str(payload["bidQty"])),
            ask_price=Decimal(str(payload["askPrice"])),
            ask_qty=Decimal(str(payload["askQty"])),
        )

    async def server_time(self) -> int:
        response = await self.client.get("/fapi/v1/time")
        response.raise_for_status()
        return int(response.json()["serverTime"])

    async def place_limit_gtx(self, request: OrderRequest) -> OrderState:
        self._assert_live_order_allowed()
        if request.order_type != OrderType.LIMIT or request.time_in_force != TimeInForce.GTX:
            raise ExchangeFilterFailure("live entry orders must be LIMIT GTX")
        params = {
            "symbol": request.symbol,
            "side": request.side.value,
            "positionSide": request.position_side.value if request.position_side and request.position_side != PositionSide.NONE else None,
            "type": "LIMIT",
            "timeInForce": "GTX",
            "quantity": _decimal_str(request.quantity),
            "price": _decimal_str(request.price),
            "reduceOnly": "true" if request.reduce_only else "false",
            "newClientOrderId": request.client_order_id,
        }
        payload = await self._signed_request("POST", "/fapi/v1/order", params)
        return _order_from_payload(payload)

    async def modify_order(self, order_id: str, side: Side, price: Decimal, quantity: Decimal) -> OrderState:
        self._assert_live_order_allowed()
        params = {
            "symbol": self.settings.binance_symbol,
            "side": side.value,
            "orderId": order_id,
            "quantity": _decimal_str(quantity),
            "price": _decimal_str(price),
        }
        payload = await self._signed_request("PUT", "/fapi/v1/order", params)
        return _order_from_payload(payload)

    async def cancel_order(self, order_id: str) -> OrderState:
        self._assert_live_order_allowed()
        payload = await self._signed_request(
            "DELETE",
            "/fapi/v1/order",
            {"symbol": self.settings.binance_symbol, "orderId": order_id},
        )
        return _order_from_payload(payload)

    async def query_order(self, order_id: str) -> OrderState:
        self._assert_live_order_allowed()
        payload = await self._signed_request(
            "GET",
            "/fapi/v1/order",
            {"symbol": self.settings.binance_symbol, "orderId": order_id},
        )
        return _order_from_payload(payload)

    async def get_open_orders(self, symbol: str) -> list[OrderState]:
        self._assert_live_order_allowed()
        payload = await self._signed_request("GET", "/fapi/v1/openOrders", {"symbol": symbol})
        return [_order_from_payload(item) for item in payload]

    async def account(self) -> dict:
        self._assert_live_order_allowed()
        payload = await self._signed_request("GET", "/fapi/v3/account", {})
        if not isinstance(payload, dict):
            raise UnknownExchangeError("account payload is not an object")
        return payload

    async def position_mode_dual_side(self) -> bool:
        self._assert_live_order_allowed()
        payload = await self._signed_request("GET", "/fapi/v1/positionSide/dual", {})
        if not isinstance(payload, dict):
            raise UnknownExchangeError("position mode payload is not an object")
        return str(payload.get("dualSidePosition", "")).lower() == "true"

    async def get_position(self, symbol: str) -> Position:
        self._assert_live_order_allowed()
        payload = await self._signed_request("GET", "/fapi/v3/positionRisk", {"symbol": symbol})
        for item in payload:
            amount = Decimal(item.get("positionAmt", "0"))
            if amount > 0:
                return Position(symbol=symbol, side=PositionSide.LONG, quantity=amount, entry_price=Decimal(item["entryPrice"]))
            if amount < 0:
                return Position(symbol=symbol, side=PositionSide.SHORT, quantity=abs(amount), entry_price=Decimal(item["entryPrice"]))
        return Position(symbol=symbol)

    async def market_reduce_only(self, symbol: str, side: Side, quantity: Decimal) -> OrderState:
        self._assert_live_order_allowed()
        params = {
            "symbol": symbol,
            "side": side.value,
            "type": "MARKET",
            "quantity": _decimal_str(quantity),
            "reduceOnly": "true",
        }
        payload = await self._signed_request("POST", "/fapi/v1/order", params)
        return _order_from_payload(payload)

    def _assert_live_order_allowed(self) -> None:
        try:
            assert_no_signed_order_allowed(self.settings)
        except SignedOrderForbiddenInDryRun as exc:
            raise LiveTradingDisabled(str(exc)) from exc
        if not self.settings.live_trading:
            raise LiveTradingDisabled("real order path is disabled unless LIVE_TRADING=true and DRY_RUN=false")

    async def _signed_request(self, method: str, path: str, params: dict) -> dict | list:
        self._assert_live_order_allowed()
        if not self.settings.binance_api_key or not self.settings.binance_api_secret:
            raise LiveTradingDisabled("signed Binance requests require API credentials")
        clean_params = {k: v for k, v in params.items() if v is not None}
        clean_params["timestamp"] = int(time.time() * 1000)
        query = urlencode(clean_params)
        signature = hmac.new(
            self.settings.binance_api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signed_query = f"{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self.settings.binance_api_key}
        try:
            response = await self.client.request(method, f"{path}?{signed_query}", headers=headers)
        except httpx.TimeoutException as exc:
            raise NetworkTimeout(str(exc)) from exc
        if response.status_code == 429:
            raise RateLimit(response.text)
        if response.status_code in {400, 401} and "-1021" in response.text:
            raise TimestampDrift(response.text)
        if response.status_code >= 400:
            raise UnknownExchangeError(response.text)
        response.raise_for_status()
        return response.json()


def _decimal_str(value: Decimal | None) -> str:
    if value is None:
        raise ExchangeFilterFailure("decimal value is required")
    return format(value.normalize(), "f")


def _order_from_payload(payload: dict) -> OrderState:
    return OrderState(
        symbol=payload["symbol"],
        side=Side(payload["side"]),
        order_type=OrderType(payload["type"]),
        quantity=Decimal(str(payload.get("origQty", payload.get("quantity", "0")))),
        executed_qty=Decimal(str(payload.get("executedQty", "0"))),
        price=Decimal(str(payload["price"])) if "price" in payload else None,
        avg_price=Decimal(str(payload["avgPrice"])) if payload.get("avgPrice") else None,
        status=OrderStatus(payload["status"]),
        time_in_force=TimeInForce(payload["timeInForce"]) if payload.get("timeInForce") in TimeInForce._value2member_map_ else None,
        reduce_only=bool(payload.get("reduceOnly", False)),
        position_side=PositionSide(payload["positionSide"]) if payload.get("positionSide") in PositionSide._value2member_map_ else None,
        order_id=str(payload.get("orderId")) if payload.get("orderId") is not None else None,
        client_order_id=payload.get("clientOrderId"),
        raw_response_summary={
            "status": str(payload.get("status")),
            "orderId": str(payload.get("orderId")),
            "clientOrderId": str(payload.get("clientOrderId")),
        },
    )
