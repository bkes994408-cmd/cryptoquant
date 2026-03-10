from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cryptoquant.aggregation import Bar
from cryptoquant.backtest import atr, bollinger_bands, ema, rsi, sma


def _bars(closes: list[float]) -> list[Bar]:
    base = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    out: list[Bar] = []
    for i, close in enumerate(closes):
        out.append(
            Bar(
                symbol="BTCUSDT",
                timeframe="1m",
                ts=base + timedelta(minutes=i),
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=10.0,
            )
        )
    return out


def test_sma_and_ema_produce_expected_shape() -> None:
    bars = _bars([1, 2, 3, 4, 5])

    sma_values = sma(bars, 3)
    ema_values = ema(bars, 3)

    assert sma_values == [None, None, 2.0, 3.0, 4.0]
    assert ema_values[:2] == [None, None]
    assert ema_values[2] == pytest.approx(2.0)
    assert ema_values[4] == pytest.approx(4.0)


def test_rsi_range_and_initial_none_window() -> None:
    bars = _bars([100, 101, 102, 101, 103, 104, 103, 102, 103, 104, 105, 106, 107, 108, 109, 110])
    values = rsi(bars, window=14)

    assert all(v is None for v in values[:14])
    assert values[14] is not None
    assert 0.0 <= (values[14] or 0.0) <= 100.0


def test_bollinger_and_atr_outputs() -> None:
    bars = _bars([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120])

    upper, mid, lower = bollinger_bands(bars, window=20, num_stddev=2.0)
    atr_values = atr(bars, window=14)

    assert upper[18] is None and mid[18] is None and lower[18] is None
    assert upper[19] is not None and mid[19] is not None and lower[19] is not None
    assert (upper[20] or 0.0) > (mid[20] or 0.0) > (lower[20] or 0.0)

    assert all(v is None for v in atr_values[:14])
    assert atr_values[14] is not None


def test_indicator_window_validation() -> None:
    bars = _bars([1, 2, 3])
    with pytest.raises(ValueError):
        sma(bars, 0)
    with pytest.raises(ValueError):
        ema(bars, -1)
    with pytest.raises(ValueError):
        rsi(bars, 0)
    with pytest.raises(ValueError):
        bollinger_bands(bars, window=0)
    with pytest.raises(ValueError):
        atr(bars, window=0)
