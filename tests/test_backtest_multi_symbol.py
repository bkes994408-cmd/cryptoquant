from __future__ import annotations

from datetime import datetime, timezone

from cryptoquant.backtest import EventReplayer
from cryptoquant.events.market import MarketEvent
from cryptoquant.execution import PaperExecutor
from cryptoquant.oms import OMS


def test_event_replayer_supports_multi_symbol_replay() -> None:
    oms = OMS()
    executor = PaperExecutor(oms, fee_bps=0.0, slippage_bps=0.0)
    replayer = EventReplayer(executor)  # symbol=None => all symbols

    events = [
        MarketEvent("BTCUSDT", "1m", 100.0, datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc), "test"),
        MarketEvent("ETHUSDT", "1m", 200.0, datetime(2026, 3, 1, 0, 1, tzinfo=timezone.utc), "test"),
        MarketEvent("BTCUSDT", "1m", 101.0, datetime(2026, 3, 1, 0, 2, tzinfo=timezone.utc), "test"),
    ]

    targets = {
        ("BTCUSDT", 100.0): 1.0,
        ("ETHUSDT", 200.0): -2.0,
        ("BTCUSDT", 101.0): 1.0,
    }

    def target_fn(event: MarketEvent) -> float:
        return targets[(event.symbol, event.close)]

    result = replayer.run(events, target_qty_fn=target_fn, order_id_prefix="ms")

    assert len(result.fills) == 2
    assert {f.symbol for f in result.fills} == {"BTCUSDT", "ETHUSDT"}
    assert executor.position_qty("BTCUSDT") == 1.0
    assert executor.position_qty("ETHUSDT") == -2.0
