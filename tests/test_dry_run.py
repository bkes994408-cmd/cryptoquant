from __future__ import annotations

from datetime import datetime, timezone

from cryptoquant.execution import (
    DryRunRequest,
    LiveOrderAck,
    OrderGateway,
    run_testnet_dry_run,
    run_testnet_dry_run_batch,
)
from cryptoquant.oms import OrderStatus


class FakeGateway(OrderGateway):
    def place_market_order(self, *, symbol: str, qty: float, client_order_id: str) -> LiveOrderAck:
        return LiveOrderAck(
            client_order_id=client_order_id,
            exchange_order_id="ex-1",
            accepted_at=datetime(2026, 3, 5, 0, 0, tzinfo=timezone.utc),
        )


def test_run_testnet_dry_run_reaches_filled_and_emits_alert() -> None:
    result = run_testnet_dry_run(
        gateway=FakeGateway(),
        symbol="BTCUSDT",
        qty=0.001,
        client_order_id="dry-1",
        simulate_fill_event=True,
    )

    assert result.exchange_order_id == "ex-1"
    assert result.final_status == OrderStatus.FILLED
    assert result.alerts[-1].code == "order.filled"


def test_run_testnet_dry_run_without_fill_event_stays_new() -> None:
    result = run_testnet_dry_run(
        gateway=FakeGateway(),
        symbol="BTCUSDT",
        qty=0.001,
        client_order_id="dry-2",
        simulate_fill_event=False,
    )

    assert result.final_status == OrderStatus.NEW


def test_run_testnet_dry_run_batch_supports_multiple_symbols() -> None:
    results = run_testnet_dry_run_batch(
        gateway=FakeGateway(),
        requests=[
            DryRunRequest(symbol="BTCUSDT", qty=0.001, client_order_id="dry-btc"),
            DryRunRequest(symbol="ETHUSDT", qty=-0.01, client_order_id="dry-eth"),
        ],
        simulate_fill_event=True,
    )

    assert [r.client_order_id for r in results] == ["dry-btc", "dry-eth"]
    assert all(r.final_status == OrderStatus.FILLED for r in results)
    assert all(r.alerts[-1].code == "order.filled" for r in results)


def test_run_testnet_dry_run_batch_requires_non_empty_requests() -> None:
    try:
        run_testnet_dry_run_batch(gateway=FakeGateway(), requests=[])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "requests cannot be empty" in str(exc)
