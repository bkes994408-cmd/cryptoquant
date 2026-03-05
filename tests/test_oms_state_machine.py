from __future__ import annotations

import pytest

from cryptoquant.oms import OMS, OrderStatus


@pytest.mark.parametrize(
    ("transition", "expected_status"),
    [
        ("fill", OrderStatus.FILLED),
        ("cancel", OrderStatus.CANCELED),
        ("reject", OrderStatus.REJECTED),
    ],
)
def test_oms_allows_transition_from_new_to_terminal_status(
    transition: str, expected_status: OrderStatus
) -> None:
    oms = OMS()
    order = oms.submit(client_order_id="o-1", symbol="BTCUSDT", qty=1.0)

    assert order.status == OrderStatus.NEW

    if transition == "reject":
        transitioned = oms.reject("o-1", reason="risk check failed")
        assert transitioned.reject_reason == "risk check failed"
    else:
        transitioned = getattr(oms, transition)("o-1")
        assert transitioned.reject_reason is None

    assert transitioned.status == expected_status
    assert oms.get("o-1") == transitioned


@pytest.mark.parametrize("transition", ["fill", "cancel", "reject"])
def test_oms_rejects_transition_from_terminal_state(transition: str) -> None:
    oms = OMS()
    oms.submit(client_order_id="o-1", symbol="BTCUSDT", qty=1.0)
    oms.fill("o-1")

    with pytest.raises(ValueError, match=r"invalid transition"):
        if transition == "reject":
            oms.reject("o-1", reason="late reject")
        else:
            getattr(oms, transition)("o-1")


def test_oms_submit_is_idempotent_for_duplicate_client_order_id() -> None:
    oms = OMS()

    first = oms.submit(client_order_id="o-1", symbol="BTCUSDT", qty=1.0)
    second = oms.submit(client_order_id="o-1", symbol="ETHUSDT", qty=99.0)

    assert second is first
    assert second.symbol == "BTCUSDT"
    assert second.qty == 1.0
    assert second.status == OrderStatus.NEW
