from __future__ import annotations

import pytest

from cryptoquant.execution import (
    ExchangeAccountConfig,
    MultiAccountBinanceGateway,
    MultiAccountLiveExecutor,
    MultiAccountOrderRequest,
)
from cryptoquant.oms import OMS


class SequenceTransport:
    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = payloads
        self.calls: list[tuple[str, dict[str, str], bytes]] = []

    def post(self, *, url: str, headers: dict[str, str], body: bytes) -> dict:
        self.calls.append((url, headers, body))
        if not self._payloads:
            raise AssertionError("no payload available")
        return self._payloads.pop(0)


def test_multi_account_gateway_routes_by_account_id() -> None:
    transport = SequenceTransport(
        [
            {"orderId": 101, "updateTime": 1_700_000_000_000},
            {"orderId": 202, "updateTime": 1_700_000_000_100},
        ]
    )
    gateway = MultiAccountBinanceGateway(
        [
            ExchangeAccountConfig(
                account_id="acct-a",
                exchange="binance",
                api_key="key-a",
                api_secret="secret-a",
                base_url="https://example.com",
            ),
            ExchangeAccountConfig(
                account_id="acct-b",
                exchange="binance",
                api_key="key-b",
                api_secret="secret-b",
                base_url="https://example.com",
            ),
        ],
        transport=transport,
        timestamp_ms_fn=lambda: 1_700_000_000_999,
    )

    ack_a = gateway.place_market_order(
        account_id="acct-a", symbol="BTCUSDT", qty=1.0, client_order_id="cid-a"
    )
    ack_b = gateway.place_market_order(
        account_id="acct-b", symbol="ETHUSDT", qty=-2.0, client_order_id="cid-b"
    )

    assert ack_a.exchange_order_id == "101"
    assert ack_b.exchange_order_id == "202"
    assert transport.calls[0][1]["X-MBX-APIKEY"] == "key-a"
    assert transport.calls[1][1]["X-MBX-APIKEY"] == "key-b"


def test_multi_account_gateway_rejects_unknown_or_duplicate_account() -> None:
    with pytest.raises(ValueError, match="duplicate account_id"):
        MultiAccountBinanceGateway(
            [
                ExchangeAccountConfig("acct-a", "binance", "k1", "s1"),
                ExchangeAccountConfig("acct-a", "binance", "k2", "s2"),
            ]
        )

    gateway = MultiAccountBinanceGateway([ExchangeAccountConfig("acct-a", "binance", "k1", "s1")])
    with pytest.raises(ValueError, match="unknown account_id"):
        gateway.place_market_order(
            account_id="acct-x", symbol="BTCUSDT", qty=1.0, client_order_id="cid"
        )


def test_multi_account_live_executor_scopes_idempotency_per_account() -> None:
    transport = SequenceTransport(
        [
            {"orderId": 1, "updateTime": 1_700_000_000_000},
            {"orderId": 2, "updateTime": 1_700_000_000_001},
        ]
    )
    gateway = MultiAccountBinanceGateway(
        [
            ExchangeAccountConfig("acct-a", "binance", "key-a", "secret-a", base_url="https://example.com"),
            ExchangeAccountConfig("acct-b", "binance", "key-b", "secret-b", base_url="https://example.com"),
        ],
        transport=transport,
    )
    executor = MultiAccountLiveExecutor(
        oms_by_account={"acct-a": OMS(), "acct-b": OMS()},
        gateway=gateway,
    )

    req_a = MultiAccountOrderRequest("acct-a", "cid-1", "BTCUSDT", 1.0)
    req_b = MultiAccountOrderRequest("acct-b", "cid-1", "BTCUSDT", 1.0)
    ack_a1 = executor.execute_market(req_a)
    ack_a2 = executor.execute_market(req_a)
    ack_b1 = executor.execute_market(req_b)

    assert ack_a1 == ack_a2
    assert ack_a1.exchange_order_id == "1"
    assert ack_b1.exchange_order_id == "2"
    assert len(transport.calls) == 2


def test_multi_account_live_executor_rejects_unknown_account() -> None:
    gateway = MultiAccountBinanceGateway(
        [ExchangeAccountConfig("acct-a", "binance", "k", "s", base_url="https://example.com")],
        transport=SequenceTransport([{"orderId": 1, "updateTime": 1_700_000_000_000}]),
    )
    executor = MultiAccountLiveExecutor(oms_by_account={"acct-a": OMS()}, gateway=gateway)

    with pytest.raises(ValueError, match="unknown account_id"):
        executor.execute_market(MultiAccountOrderRequest("acct-x", "cid", "BTCUSDT", 1.0))
