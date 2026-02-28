from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptoquant.aggregation import Bar
from cryptoquant.strategy import MovingAverageCrossoverStrategy, StrategyEngine


def _bars(closes: list[float]) -> list[Bar]:
    base = datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc)
    out: list[Bar] = []
    for i, close in enumerate(closes):
        out.append(
            Bar(
                symbol="BTCUSDT",
                timeframe="15m",
                ts=base + timedelta(minutes=15 * i),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1.0,
            )
        )
    return out


def test_ma_crossover_outputs_long_short_flat() -> None:
    strategy = MovingAverageCrossoverStrategy(fast_window=2, slow_window=4, base_qty=1.5)
    engine = StrategyEngine(strategy)

    # fast MA > slow MA => long
    long_decision = engine.on_bars(_bars([100, 101, 102, 110]))
    assert long_decision.target_qty == 1.5

    # fast MA < slow MA => short
    short_decision = engine.on_bars(_bars([110, 109, 108, 100]))
    assert short_decision.target_qty == -1.5

    # insufficient bars => flat
    flat_decision = engine.on_bars(_bars([100, 101, 102]))
    assert flat_decision.target_qty == 0.0
