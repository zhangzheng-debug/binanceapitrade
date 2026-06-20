from decimal import Decimal

import pytest

from scripts.preflight_live_readonly import (
    RequestAudit,
    assert_readonly_signed_endpoint,
    order_endpoint_called,
    position_amount_from_payload,
)


def test_readonly_preflight_allows_only_readonly_signed_endpoints() -> None:
    assert_readonly_signed_endpoint("GET", "/fapi/v3/account")
    assert_readonly_signed_endpoint("GET", "/fapi/v3/positionRisk")
    assert_readonly_signed_endpoint("GET", "/fapi/v1/openOrders")


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/fapi/v1/order"),
        ("PUT", "/fapi/v1/order"),
        ("DELETE", "/fapi/v1/order"),
        ("GET", "/fapi/v1/order"),
        ("POST", "/fapi/v1/leverage"),
        ("POST", "/fapi/v1/marginType"),
    ],
)
def test_readonly_preflight_rejects_order_and_mutation_endpoints(method: str, path: str) -> None:
    with pytest.raises(RuntimeError):
        assert_readonly_signed_endpoint(method, path)


def test_order_endpoint_called_detects_mutating_order_endpoint() -> None:
    calls = [RequestAudit("POST", "/fapi/v1/order", signed=True, ok=False, status_code=None, classification="blocked", error="")]
    assert order_endpoint_called(calls)


def test_position_amount_from_payload_sums_ethusdc_only() -> None:
    payload = [
        {"symbol": "ETHUSDC", "positionAmt": "0.25"},
        {"symbol": "BTCUSDC", "positionAmt": "1"},
        {"symbol": "ETHUSDC", "positionAmt": "-0.25"},
    ]
    assert position_amount_from_payload(payload, "ETHUSDC") == Decimal("0.00")
