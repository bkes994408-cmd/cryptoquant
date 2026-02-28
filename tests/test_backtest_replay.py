from __future__ import annotations

from datetime import datetime, timezone

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
