from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Mapping, Sequence

from .optimizer import StrategyParameterSet


@dataclass(frozen=True)
class AdaptationSignal:
    """Market context signal for parameter adaptation."""

    volatility: float
    trend_strength: float


@dataclass(frozen=True)
class BanditState:
    pulls: int = 0
    avg_reward: float = 0.0


class RegimeBanditParameterTuner:
    """Epsilon-greedy contextual bandit for online strategy parameter tuning.

    The tuner maps each signal to a coarse market regime and keeps an independent
    reward table per regime. Reward can be realized PnL, risk-adjusted return,
    or any scalar feedback from live/paper execution.
    """

    def __init__(
        self,
        candidates: Sequence[StrategyParameterSet],
        *,
        epsilon: float = 0.1,
        seed: int | None = None,
    ) -> None:
        if not candidates:
            raise ValueError("at least one candidate parameter set is required")
        if not (0.0 <= epsilon <= 1.0):
            raise ValueError("epsilon must be in [0, 1]")

        unique = {c for c in candidates}
        if len(unique) != len(candidates):
            raise ValueError("candidate parameter sets must be unique")

        self._candidates = list(candidates)
        self._epsilon = epsilon
        self._rng = Random(seed)
        self._states: dict[str, dict[StrategyParameterSet, BanditState]] = {}

    def select(self, signal: AdaptationSignal) -> StrategyParameterSet:
        regime = _regime_key(signal)
        table = self._states.setdefault(regime, _fresh_table(self._candidates))

        if self._rng.random() < self._epsilon:
            return self._rng.choice(self._candidates)

        best = sorted(
            self._candidates,
            key=lambda p: (table[p].avg_reward, -p.fast_window, p.slow_window),
            reverse=True,
        )
        return best[0]

    def update(self, signal: AdaptationSignal, params: StrategyParameterSet, reward: float) -> BanditState:
        regime = _regime_key(signal)
        table = self._states.setdefault(regime, _fresh_table(self._candidates))
        if params not in table:
            raise ValueError("params not found in candidate set")

        old = table[params]
        pulls = old.pulls + 1
        avg = old.avg_reward + (reward - old.avg_reward) / pulls
        new_state = BanditState(pulls=pulls, avg_reward=avg)
        table[params] = new_state
        return new_state

    def snapshot(self) -> Mapping[str, Mapping[StrategyParameterSet, BanditState]]:
        return {regime: dict(state) for regime, state in self._states.items()}


def _fresh_table(candidates: Sequence[StrategyParameterSet]) -> dict[StrategyParameterSet, BanditState]:
    return {p: BanditState() for p in candidates}


def _regime_key(signal: AdaptationSignal) -> str:
    if signal.volatility < 0:
        raise ValueError("volatility must be non-negative")

    vol_bucket = "highvol" if signal.volatility >= 0.03 else "lowvol"
    trend_bucket = "trend" if abs(signal.trend_strength) >= 0.5 else "range"
    return f"{vol_bucket}:{trend_bucket}"
