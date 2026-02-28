from __future__ import annotations

from datetime import datetime, timezone

from cryptoquant.execution import PaperExecutor
from cryptoquant.oms import OMS, OrderStatus


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
