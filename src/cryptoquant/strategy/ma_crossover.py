from __future__ import annotations

from collections import deque
from typing import Sequence

from cryptoquant.aggregation import Bar


class MovingAverageCrossoverStrategy:
    """Simple MA crossover: fast>slow => long, fast<slow => short, else flat."""

    def __init__(self, *, fast_window: int = 3, slow_window: int = 5, base_qty: float = 1.0) -> None:
        if fast_window <= 0 or slow_window <= 0:
            raise ValueError("moving average window must be positive")
        if fast_window >= slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        if base_qty <= 0:
            raise ValueError("base_qty must be positive")

        self._fast = fast_window
        self._slow = slow_window
        self._base_qty = base_qty

    @property
    def name(self) -> str:
        return "ma_crossover"

    def target_qty(self, bars: Sequence[Bar]) -> float:
        if len(bars) < self._slow:
            return 0.0

        closes = deque((bar.close for bar in bars), maxlen=self._slow)
        close_values = list(closes)
        slow_ma = sum(close_values) / self._slow
        fast_ma = sum(close_values[-self._fast :]) / self._fast

        if fast_ma > slow_ma:
            return self._base_qty
        if fast_ma < slow_ma:
            return -self._base_qty
        return 0.0
