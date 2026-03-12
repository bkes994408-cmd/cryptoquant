from __future__ import annotations

from dataclasses import dataclass
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
        self._pull_count = 0
        self._reward_sum: dict[StrategyParameterSet, float] = {c: 0.0 for c in self._candidates}
        self._reward_count: dict[StrategyParameterSet, int] = {c: 0 for c in self._candidates}

    def select(self) -> StrategyParameterSet:
        self._pull_count += 1
        if self._epsilon > 0 and self._pull_count % max(1, int(1 / self._epsilon)) == 0:
            idx = (self._pull_count // max(1, int(1 / self._epsilon))) % len(self._candidates)
            return self._candidates[idx]

        best = self._candidates[0]
        best_mean = self.mean_reward(best)
        for candidate in self._candidates[1:]:
            candidate_mean = self.mean_reward(candidate)
            if candidate_mean > best_mean:
                best = candidate
                best_mean = candidate_mean
        return best

    def update(self, params: StrategyParameterSet, reward: float) -> None:
        if params not in self._reward_sum:
            raise ValueError("params not in candidate set")
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

    def step(self, history: Sequence[MarketEvent]) -> AdaptiveDecision:
        if len(history) < self._config.lookback_events:
            raise ValueError("insufficient history for adaptive tuning")

        self._events_seen += 1
        should_retune = self._events_seen == 1 or self._events_seen % self._config.retune_interval_events == 0

        window = history[-self._config.lookback_events :]
        optimization = self._optimizer.optimize(window, param_grid=self._candidates)

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
