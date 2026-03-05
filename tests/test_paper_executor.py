from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cryptoquant.execution import PaperExecutor
from cryptoquant.oms import OMS, OrderStatus
from cryptoquant.risk import KillSwitch


def test_paper_executor_market_fill_with_fee_and_slippage() -> None:
    oms = OMS()
    executor = PaperExecutor(oms, fee_bps=10, slippage_bps=20)  # 0.1%, 0.2%

    fill = executor.execute_market(
        client_order_id="o-1",
        symbol="BTCUSDT",
        qty=2,
        mark_price=100.0,
        ts=datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc),
    )

    assert fill.fill_price == 100.2
    assert round(fill.notional, 6) == 200.4
    assert round(fill.fee, 6) == 0.2004
    assert round(fill.slippage_cost, 6) == 0.4
    assert executor.position_qty("BTCUSDT") == 2
    assert oms.get("o-1") is not None
    assert oms.get("o-1").status == OrderStatus.FILLED


def test_paper_executor_idempotent_for_same_client_order_id() -> None:
    oms = OMS()
    executor = PaperExecutor(oms)

    first = executor.execute_market(
        client_order_id="o-1",
        symbol="BTCUSDT",
        qty=1,
        mark_price=100.0,
        ts=datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc),
    )
    second = executor.execute_market(
        client_order_id="o-1",
        symbol="BTCUSDT",
        qty=1,
        mark_price=999.0,
        ts=datetime(2026, 2, 28, 0, 1, tzinfo=timezone.utc),
    )

    assert second == first
    assert executor.position_qty("BTCUSDT") == 1


def test_execute_to_target_flip_splits_into_close_then_open() -> None:
    oms = OMS()
    executor = PaperExecutor(oms, fee_bps=0.0, slippage_bps=0.0)

    fills = executor.execute_to_target(
        client_order_id_prefix="flip-1",
        symbol="BTCUSDT",
        current_qty=2.0,
        target_qty=-1.0,
        mark_price=100.0,
        ts=datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc),
    )

    assert len(fills) == 2
    assert fills[0].client_order_id == "flip-1-close"
    assert fills[0].qty == -2.0
    assert fills[1].client_order_id == "flip-1-open"
    assert fills[1].qty == -1.0
    assert executor.position_qty("BTCUSDT") == -3.0

    close_order = oms.get("flip-1-close")
    open_order = oms.get("flip-1-open")
    assert close_order is not None and close_order.status == OrderStatus.FILLED
    assert open_order is not None and open_order.status == OrderStatus.FILLED


def test_execute_to_target_no_flip_uses_single_leg() -> None:
    oms = OMS()
    executor = PaperExecutor(oms, fee_bps=0.0, slippage_bps=0.0)

    fills = executor.execute_to_target(
        client_order_id_prefix="single-1",
        symbol="BTCUSDT",
        current_qty=1.0,
        target_qty=3.0,
        mark_price=100.0,
        ts=datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc),
    )

    assert len(fills) == 1
    assert fills[0].client_order_id == "single-1-single"
    assert fills[0].qty == 2.0
    assert executor.position_qty("BTCUSDT") == 2.0


def test_paper_executor_blocks_execution_when_kill_switch_active() -> None:
    oms = OMS()
    kill_switch = KillSwitch()
    kill_switch.engage("operator halt")
    executor = PaperExecutor(oms, kill_switch=kill_switch)

    with pytest.raises(RuntimeError, match="kill switch active"):
        executor.execute_market(
            client_order_id="o-kill-1",
            symbol="BTCUSDT",
            qty=1,
            mark_price=100.0,
            ts=datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc),
        )

    assert oms.get("o-kill-1") is None
