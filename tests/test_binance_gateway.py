from __future__ import annotations

import urllib.parse

import pytest

from cryptoquant.execution import BinanceFuturesOrderGateway, BinanceGatewayConfig


class FakeTransport:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.last_url = ""
        self.last_headers: dict[str, str] = {}
        self.last_body: bytes = b""

    def post(self, *, url: str, headers: dict[str, str], body: bytes) -> dict:
        self.last_url = url
        self.last_headers = headers
        self.last_body = body
        return self.payload


def test_binance_gateway_posts_signed_market_order_payload() -> None:
    transport = FakeTransport({"orderId": 123, "updateTime": 1_700_000_000_000})
    gateway = BinanceFuturesOrderGateway(
        BinanceGatewayConfig(api_key="k", api_secret="s", base_url="https://example.com"),
        transport=transport,
        timestamp_ms_fn=lambda: 1111111111111,
    )

    ack = gateway.place_market_order(symbol="BTCUSDT", qty=2.5, client_order_id="cid-1")

    assert ack.client_order_id == "cid-1"
    assert ack.exchange_order_id == "123"
    assert transport.last_url == "https://example.com/fapi/v1/order"
    assert transport.last_headers["X-MBX-APIKEY"] == "k"

    body = transport.last_body.decode("utf-8")
    assert "signature=" in body
    parsed = urllib.parse.parse_qs(body)
    assert parsed["symbol"] == ["BTCUSDT"]
    assert parsed["side"] == ["BUY"]
    assert parsed["type"] == ["MARKET"]
    assert parsed["quantity"] == ["2.5"]
    assert parsed["newClientOrderId"] == ["cid-1"]
    assert parsed["timestamp"] == ["1111111111111"]


def test_binance_gateway_uses_sell_side_for_negative_qty() -> None:
    transport = FakeTransport({"orderId": 456, "transactTime": 1_700_000_000_000})
    gateway = BinanceFuturesOrderGateway(
        BinanceGatewayConfig(api_key="k", api_secret="s"),
        transport=transport,
        timestamp_ms_fn=lambda: 2222222222222,
    )

    gateway.place_market_order(symbol="ETHUSDT", qty=-1.0, client_order_id="cid-2")
    parsed = urllib.parse.parse_qs(transport.last_body.decode("utf-8"))
    assert parsed["side"] == ["SELL"]
    assert parsed["quantity"] == ["1.0"]


def test_binance_gateway_rejects_missing_order_id() -> None:
    transport = FakeTransport({"status": "NEW"})
    gateway = BinanceFuturesOrderGateway(
        BinanceGatewayConfig(api_key="k", api_secret="s"),
        transport=transport,
    )

    with pytest.raises(ValueError, match="missing orderId"):
        gateway.place_market_order(symbol="BTCUSDT", qty=1.0, client_order_id="cid-3")


def test_binance_gateway_requires_https_base_url() -> None:
    with pytest.raises(ValueError, match="https URL"):
        BinanceFuturesOrderGateway(BinanceGatewayConfig(api_key="k", api_secret="s", base_url="http://x"))
