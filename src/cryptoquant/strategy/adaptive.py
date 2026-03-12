from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from random import SystemRandom
from typing import Sequence

from cryptoquant.events.market import MarketEvent
from cryptoquant.strategy.optimizer import (
    AutomatedStrategyOptimizer,
    StrategyOptimizationResult,
    StrategyParameterSet,
)


@dataclass(frozen=True)
class AdaptiveStrategyConfig:
    """Configuration for dynamic strategy parameter tuning."""

    lookback_events: int = 120
    retune_interval_events: int = 30
    epsilon: float = 0.1


class EpsilonGreedyParameterBandit:
    """Simple RL-style bandit for online parameter exploration/exploitation."""

    def __init__(self, candidates: Sequence[StrategyParameterSet], *, epsilon: float = 0.1) -> None:
        if not candidates:
            raise ValueError("candidates cannot be empty")
        if not 0.0 <= epsilon <= 1.0:
            raise ValueError("epsilon must be within [0, 1]")

        self._candidates = list(candidates)
        self._epsilon = epsilon
        self._reward_sum: dict[StrategyParameterSet, float] = {c: 0.0 for c in self._candidates}
        self._reward_count: dict[StrategyParameterSet, int] = {c: 0 for c in self._candidates}
        self._rng = SystemRandom()

    def select(self) -> StrategyParameterSet:
        # Explore stochastically with probability epsilon.
        if self._rng.random() < self._epsilon:
            return self._rng.choice(self._candidates)

        # Exploit the highest mean reward; random tie-break among equals.
        means = {candidate: self.mean_reward(candidate) for candidate in self._candidates}
        best_mean = max(means.values())
        top_candidates = [candidate for candidate, mean in means.items() if mean == best_mean]
        return self._rng.choice(top_candidates)

    def update(self, params: StrategyParameterSet, reward: float) -> None:
        if params not in self._reward_sum:
            raise ValueError("params not in candidate set")
        if not isfinite(reward):
            raise ValueError("reward must be a finite number")
        self._reward_sum[params] += reward
        self._reward_count[params] += 1

    def mean_reward(self, params: StrategyParameterSet) -> float:
        count = self._reward_count[params]
        return 0.0 if count == 0 else self._reward_sum[params] / count


@dataclass(frozen=True)
class AdaptiveDecision:
    selected_params: StrategyParameterSet
    optimization: StrategyOptimizationResult
    mode: str  # "retune" or "hold"


class AdaptiveParameterController:
    """Dynamic controller: periodic retune + epsilon-greedy online adaptation."""

    def __init__(
        self,
        *,
        symbol: str,
        candidates: Sequence[StrategyParameterSet],
        config: AdaptiveStrategyConfig | None = None,
        objective: str = "net_pnl",
        base_qty: float = 1.0,
    ) -> None:
        cfg = config or AdaptiveStrategyConfig()
        if cfg.lookback_events < 20:
            raise ValueError("lookback_events must be >= 20")
        if cfg.retune_interval_events < 1:
            raise ValueError("retune_interval_events must be >= 1")

        self._symbol = symbol
        self._candidates = list(candidates)
        if not self._candidates:
            raise ValueError("candidates cannot be empty")

        self._config = cfg
        self._optimizer = AutomatedStrategyOptimizer(
            symbol=symbol,
            objective=objective,
            base_qty=base_qty,
        )
        self._bandit = EpsilonGreedyParameterBandit(self._candidates, epsilon=cfg.epsilon)
        self._events_seen = 0
        self._last_selected = self._candidates[0]
        self._last_optimization: StrategyOptimizationResult | None = None

    def step(self, history: Sequence[MarketEvent]) -> AdaptiveDecision:
        if len(history) < self._config.lookback_events:
            raise ValueError("insufficient history for adaptive tuning")

        self._events_seen += 1
        should_retune = self._events_seen == 1 or self._events_seen % self._config.retune_interval_events == 0

        window = history[-self._config.lookback_events :]

        if should_retune or self._last_optimization is None:
            optimization = self._optimizer.optimize(window, param_grid=self._candidates)
            self._last_optimization = optimization
        else:
            # Hold mode: reuse cached optimization to avoid re-running full optimization each event.
            optimization = self._last_optimization

        if should_retune:
            params = self._bandit.select()
            mode = "retune"
        else:
            params = self._last_selected
            mode = "hold"

        if params == optimization.best.params:
            reward = optimization.best.score
        else:
            matched = next((x for x in optimization.leaderboard if x.params == params), None)
            reward = 0.0 if matched is None else matched.score

        self._bandit.update(params, reward)
        self._last_selected = params
        return AdaptiveDecision(selected_params=params, optimization=optimization, mode=mode)
