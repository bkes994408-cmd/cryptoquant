from __future__ import annotations

import pytest

from cryptoquant.oms import OMS, OrderStatus


def test_oms_state_machine_new_to_filled() -> None:
    oms = OMS()
    order = oms.submit(client_order_id="o-filled", symbol="BTCUSDT", qty=1)

    assert order.status == OrderStatus.NEW

    filled = oms.fill("o-filled")
    assert filled.status == OrderStatus.FILLED


def test_oms_state_machine_new_to_canceled() -> None:
    oms = OMS()
    order = oms.submit(client_order_id="o-canceled", symbol="BTCUSDT", qty=1)

    assert order.status == OrderStatus.NEW

    canceled = oms.cancel("o-canceled")
    assert canceled.status == OrderStatus.CANCELED


def test_oms_state_machine_new_to_rejected() -> None:
    oms = OMS()
    order = oms.submit(client_order_id="o-rejected", symbol="BTCUSDT", qty=1)

    assert order.status == OrderStatus.NEW

    rejected = oms.reject("o-rejected", "post only")
    assert rejected.status == OrderStatus.REJECTED
    assert rejected.reject_reason == "post only"


def test_oms_client_order_id_is_idempotent() -> None:
    oms = OMS()

    first = oms.submit(client_order_id="dup-1", symbol="BTCUSDT", qty=1)
    second = oms.submit(client_order_id="dup-1", symbol="ETHUSDT", qty=999)

    assert second is first
    assert second.symbol == "BTCUSDT"
    assert second.qty == 1


def test_oms_rejects_transition_from_terminal_state() -> None:
    oms = OMS()
    oms.submit(client_order_id="o-terminal", symbol="BTCUSDT", qty=1)
    oms.fill("o-terminal")

    with pytest.raises(ValueError, match="invalid transition"):
        oms.cancel("o-terminal")
