from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from cryptoquant.aggregation import Bar


@dataclass(frozen=True)
class StrategyDecision:
    target_qty: float
    signal: str


class Strategy(Protocol):
    def target_qty(self, bars: Sequence[Bar]) -> float: ...

    @property
    def name(self) -> str: ...


class StrategyEngine:
    """Compute target position quantity from aggregated bars."""

    def __init__(self, strategy: Strategy) -> None:
        self._strategy = strategy

    def on_bars(self, bars: Sequence[Bar]) -> StrategyDecision:
        qty = self._strategy.target_qty(bars)
        return StrategyDecision(target_qty=qty, signal=self._strategy.name)
