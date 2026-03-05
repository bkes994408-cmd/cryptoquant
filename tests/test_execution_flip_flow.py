from __future__ import annotations

from datetime import datetime, timezone

from cryptoquant.execution import PaperExecutor
from cryptoquant.oms import OMS


def test_execute_to_target_splits_flip_into_close_then_open() -> None:
    oms = OMS()
    executor = PaperExecutor(oms, fee_bps=0, slippage_bps=0)

    # Start with a long position of +2
    executor.execute_market(
        client_order_id="seed-long",
        symbol="BTCUSDT",
        qty=2,
        mark_price=100.0,
        ts=datetime(2026, 3, 5, 0, 0, tzinfo=timezone.utc),
    )
    assert executor.position_qty("BTCUSDT") == 2

    fills = executor.execute_to_target(
        client_order_id_prefix="flip-1",
        symbol="BTCUSDT",
        current_qty=2,
        target_qty=-1,
        mark_price=100.0,
        ts=datetime(2026, 3, 5, 0, 1, tzinfo=timezone.utc),
    )

    assert [f.client_order_id for f in fills] == ["flip-1-close", "flip-1-open"]
    assert [f.qty for f in fills] == [-2, -1]
    assert executor.position_qty("BTCUSDT") == -1


def test_execute_to_target_non_flip_uses_single_leg() -> None:
    oms = OMS()
    executor = PaperExecutor(oms, fee_bps=0, slippage_bps=0)

    fills = executor.execute_to_target(
        client_order_id_prefix="grow-long",
        symbol="BTCUSDT",
        current_qty=1,
        target_qty=3,
        mark_price=100.0,
        ts=datetime(2026, 3, 5, 0, 2, tzinfo=timezone.utc),
    )

    assert len(fills) == 1
    assert fills[0].client_order_id == "grow-long-single"
    assert fills[0].qty == 2


def test_execute_to_target_idempotent_with_same_prefix() -> None:
    oms = OMS()
    executor = PaperExecutor(oms, fee_bps=0, slippage_bps=0)

    executor.execute_market(
        client_order_id="seed-short",
        symbol="BTCUSDT",
        qty=-2,
        mark_price=100.0,
        ts=datetime(2026, 3, 5, 0, 3, tzinfo=timezone.utc),
    )

    first = executor.execute_to_target(
        client_order_id_prefix="flip-2",
        symbol="BTCUSDT",
        current_qty=-2,
        target_qty=1,
        mark_price=100.0,
        ts=datetime(2026, 3, 5, 0, 4, tzinfo=timezone.utc),
    )
    second = executor.execute_to_target(
        client_order_id_prefix="flip-2",
        symbol="BTCUSDT",
        current_qty=-2,
        target_qty=1,
        mark_price=100.0,
        ts=datetime(2026, 3, 5, 0, 5, tzinfo=timezone.utc),
    )

    assert [f.client_order_id for f in second] == [f.client_order_id for f in first]
    assert executor.position_qty("BTCUSDT") == 1
