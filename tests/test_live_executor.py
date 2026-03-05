from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cryptoquant.execution import LiveExecutor, LiveOrderAck, LiveOrderRequest
from cryptoquant.oms import OMS
from cryptoquant.risk import KillSwitch


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float, str]] = []

    def place_market_order(self, *, symbol: str, qty: float, client_order_id: str) -> LiveOrderAck:
        self.calls.append((symbol, qty, client_order_id))
        return LiveOrderAck(
            client_order_id=client_order_id,
            exchange_order_id=f"ex-{client_order_id}",
            accepted_at=datetime(2026, 3, 5, 0, 0, tzinfo=timezone.utc),
        )


def test_live_executor_sends_market_order_and_returns_ack() -> None:
    oms = OMS()
    gateway = FakeGateway()
    executor = LiveExecutor(oms, gateway)

    ack = executor.execute_market(LiveOrderRequest(client_order_id="o-1", symbol="BTCUSDT", qty=1.0))

    assert ack.exchange_order_id == "ex-o-1"
    assert gateway.calls == [("BTCUSDT", 1.0, "o-1")]
    assert oms.get("o-1") is not None


def test_live_executor_idempotent_by_client_order_id() -> None:
    oms = OMS()
    gateway = FakeGateway()
    executor = LiveExecutor(oms, gateway)

    first = executor.execute_market(LiveOrderRequest(client_order_id="o-1", symbol="BTCUSDT", qty=1.0))
    second = executor.execute_market(LiveOrderRequest(client_order_id="o-1", symbol="BTCUSDT", qty=1.0))

    assert second == first
    assert len(gateway.calls) == 1


def test_live_executor_respects_kill_switch() -> None:
    oms = OMS()
    gateway = FakeGateway()
    kill = KillSwitch()
    kill.engage("incident")
    executor = LiveExecutor(oms, gateway, kill_switch=kill)

    with pytest.raises(RuntimeError, match="kill switch active"):
        executor.execute_market(LiveOrderRequest(client_order_id="o-kill", symbol="BTCUSDT", qty=1.0))

    assert gateway.calls == []
    assert oms.get("o-kill") is None
