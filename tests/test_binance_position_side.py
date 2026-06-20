import asyncio
from decimal import Decimal
from typing import Any

from bot.binance_client import BinanceClient
from bot.config import Settings
from bot.models import OrderRequest, OrderType, PositionSide, Side, TimeInForce


class RecordingBinanceClient(BinanceClient):
    def __init__(self) -> None:
        settings = Settings(
            DRY_RUN=False,
            LIVE_TRADING=True,
            BINANCE_API_KEY="key",
            BINANCE_API_SECRET="secret",
            BINANCE_ENV="mainnet",
            _env_file=None,
        )
        super().__init__(settings)
        self.recorded: tuple[str, str, dict[str, Any]] | None = None

    async def _signed_request(self, method: str, path: str, params: dict) -> dict:
        self.recorded = (method, path, params)
        return {
            "symbol": "ETHUSDC",
            "side": params["side"],
            "positionSide": params.get("positionSide", "BOTH"),
            "type": "LIMIT",
            "timeInForce": "GTX",
            "origQty": params["quantity"],
            "executedQty": "0",
            "price": params["price"],
            "reduceOnly": params.get("reduceOnly") == "true",
            "orderId": 123,
            "clientOrderId": params.get("newClientOrderId"),
            "status": "NEW",
        }


def test_place_limit_gtx_passes_position_side_when_requested() -> None:
    client = RecordingBinanceClient()
    try:
        order = asyncio.run(
            client.place_limit_gtx(
                OrderRequest(
                    symbol="ETHUSDC",
                    side=Side.BUY,
                    order_type=OrderType.LIMIT,
                    quantity=Decimal("0.01"),
                    price=Decimal("3000"),
                    time_in_force=TimeInForce.GTX,
                    position_side=PositionSide.LONG,
                    client_order_id="test-client",
                )
            )
        )
    finally:
        asyncio.run(client.close())

    assert client.recorded is not None
    method, path, params = client.recorded
    assert method == "POST"
    assert path == "/fapi/v1/order"
    assert params["positionSide"] == "LONG"
    assert order.position_side == PositionSide.LONG
