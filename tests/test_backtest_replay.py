from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cryptoquant.backtest import EventReplayer
from cryptoquant.events.market import MarketEvent
from cryptoquant.execution import PaperExecutor
from cryptoquant.oms import OMS


def test_event_replayer_reaches_target_position_and_generates_fills() -> None:
    oms = OMS()
    executor = PaperExecutor(oms, fee_bps=0.0, slippage_bps=0.0)
    replayer = EventReplayer(executor, symbol="BTCUSDT")

    events = [
        MarketEvent("BTCUSDT", "1m", 100.0, datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc), "test"),
        MarketEvent("BTCUSDT", "1m", 101.0, datetime(2026, 2, 28, 0, 1, tzinfo=timezone.utc), "test"),
        MarketEvent("BTCUSDT", "1m", 102.0, datetime(2026, 2, 28, 0, 2, tzinfo=timezone.utc), "test"),
    ]

    def target_fn(event: MarketEvent) -> float:
        if event.close >= 101:
            return 2.0
        return 0.0

    result = replayer.run(events, target_qty_fn=target_fn)

    assert len(result.fills) == 1
    assert result.fills[0].qty == 2.0
    assert result.fills[0].fill_price == 101.0
    assert executor.position_qty("BTCUSDT") == 2.0


@pytest.mark.xfail(reason="TODO(MVP-2): flip order should be split into reduceOnly close then open")
def test_event_replayer_flip_should_split_reduce_only_close_then_open() -> None:
    oms = OMS()
    executor = PaperExecutor(oms, fee_bps=0.0, slippage_bps=0.0)
    replayer = EventReplayer(executor, symbol="BTCUSDT")

    events = [
        MarketEvent("BTCUSDT", "1m", 100.0, datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc), "test"),
        MarketEvent("BTCUSDT", "1m", 101.0, datetime(2026, 2, 28, 0, 1, tzinfo=timezone.utc), "test"),
    ]

    def target_fn(event: MarketEvent) -> float:
        if event.close == 100.0:
            return 1.0  # 開多 1
        return -1.0  # 下一根翻空 1，預期拆成先平多再開空

    result = replayer.run(events, target_qty_fn=target_fn)

    # 期望行為（尚未實作）：
    # fill[0] +1 開多
    # fill[1] -1 reduceOnly 平多
    # fill[2] -1 開空
    assert len(result.fills) == 3
    assert [f.qty for f in result.fills] == [1.0, -1.0, -1.0]
    assert executor.position_qty("BTCUSDT") == -1.0
