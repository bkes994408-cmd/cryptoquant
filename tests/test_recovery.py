from __future__ import annotations

import pytest

from cryptoquant.execution import RecoverySnapshot, UserStreamEvent, recover_state
from cryptoquant.oms import OrderStatus


def test_recover_state_applies_user_stream_over_rest_snapshot() -> None:
    snapshot = RecoverySnapshot(
        positions={"BTCUSDT": 1.0, "ETHUSDT": 0.5},
        orders={"o-1": OrderStatus.NEW, "o-2": OrderStatus.NEW},
    )
    events = [
        UserStreamEvent(kind="position", key="BTCUSDT", value=2.0),
        UserStreamEvent(kind="order", key="o-1", value=OrderStatus.FILLED),
        UserStreamEvent(kind="order", key="o-2", value=OrderStatus.CANCELED),
    ]

    recovered = recover_state(snapshot, events)

    assert recovered.positions["BTCUSDT"] == 2.0
    assert recovered.positions["ETHUSDT"] == 0.5
    assert recovered.orders["o-1"] == OrderStatus.FILLED
    assert recovered.orders["o-2"] == OrderStatus.CANCELED


def test_recover_state_latest_user_stream_event_wins() -> None:
    snapshot = RecoverySnapshot(positions={"BTCUSDT": 1.0}, orders={"o-1": OrderStatus.NEW})
    events = [
        UserStreamEvent(kind="order", key="o-1", value=OrderStatus.NEW),
        UserStreamEvent(kind="order", key="o-1", value=OrderStatus.FILLED),
        UserStreamEvent(kind="position", key="BTCUSDT", value=0.0),
    ]

    recovered = recover_state(snapshot, events)

    assert recovered.orders["o-1"] == OrderStatus.FILLED
    assert recovered.positions["BTCUSDT"] == 0.0


def test_recover_state_rejects_unknown_event_kind() -> None:
    snapshot = RecoverySnapshot(positions={}, orders={})

    with pytest.raises(ValueError, match="unsupported user stream event kind"):
        recover_state(snapshot, [UserStreamEvent(kind="balance", key="USDT", value=1000.0)])
