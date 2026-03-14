from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from math import isfinite
from random import SystemRandom
from typing import Sequence

from cryptoquant.events.market import MarketEvent
from cryptoquant.sentiment import SentimentPipeline, SentimentSnapshot
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
    enable_ml_adaptation: bool = False
    ml_feature_window: int = 20
    ml_weight: float = 0.25
    epsilon_min: float = 0.02
    epsilon_max: float = 0.35
    enable_sentiment_overlay: bool = False
    sentiment_weight: float = 0.15
    sentiment_lookback_hours: int = 24


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

    def set_epsilon(self, epsilon: float) -> None:
        if not 0.0 <= epsilon <= 1.0:
            raise ValueError("epsilon must be within [0, 1]")
        self._epsilon = epsilon

    @property
    def epsilon(self) -> float:
        return self._epsilon

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
    predicted_return: float | None = None
    dynamic_epsilon: float | None = None
    sentiment_score: float | None = None
    sentiment_confidence: float | None = None


class _OnlineLinearReturnModel:
    """Tiny online linear model (SGD) for next-return prediction."""

    def __init__(self, *, learning_rate: float = 0.05, epochs: int = 5) -> None:
        self._lr = learning_rate
        self._epochs = epochs
        self._weights = [0.0, 0.0, 0.0, 0.0]  # bias + 3 features

    def fit(self, closes: Sequence[float], *, window: int) -> None:
        if len(closes) < max(6, window + 2):
            return
        returns = _returns(closes)
        xs: list[list[float]] = []
        ys: list[float] = []
        for i in range(window, len(returns) - 1):
            xs.append(_feature_vector(returns, i, window))
            ys.append(returns[i + 1])

        for _ in range(self._epochs):
            for x, y in zip(xs, ys):
                pred = _dot(self._weights, x)
                err = pred - y
                for j in range(len(self._weights)):
                    self._weights[j] -= self._lr * err * x[j]

    def predict_next_return(self, closes: Sequence[float], *, window: int) -> float:
        if len(closes) < max(6, window + 1):
            return 0.0
        returns = _returns(closes)
        x = _feature_vector(returns, len(returns) - 1, window)
        return _dot(self._weights, x)


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
        sentiment_pipeline: SentimentPipeline | None = None,
    ) -> None:
        cfg = config or AdaptiveStrategyConfig()
        if cfg.lookback_events < 20:
            raise ValueError("lookback_events must be >= 20")
        if cfg.retune_interval_events < 1:
            raise ValueError("retune_interval_events must be >= 1")
        if cfg.ml_feature_window < 5:
            raise ValueError("ml_feature_window must be >= 5")
        if cfg.ml_weight < 0:
            raise ValueError("ml_weight must be >= 0")
        if not 0 <= cfg.epsilon_min <= cfg.epsilon_max <= 1:
            raise ValueError("epsilon_min/epsilon_max must satisfy 0 <= min <= max <= 1")
        if cfg.sentiment_weight < 0:
            raise ValueError("sentiment_weight must be >= 0")
        if cfg.sentiment_lookback_hours < 1:
            raise ValueError("sentiment_lookback_hours must be >= 1")

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
        self._model = _OnlineLinearReturnModel() if cfg.enable_ml_adaptation else None
        self._sentiment_pipeline = sentiment_pipeline

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

        predicted_return: float | None = None
        dynamic_epsilon: float | None = None
        if self._model is not None:
            closes = [e.close for e in window]
            self._model.fit(closes, window=self._config.ml_feature_window)
            predicted_return = self._model.predict_next_return(closes, window=self._config.ml_feature_window)
            if should_retune:
                vol = _stdev(_returns(closes))
                confidence = 0.0 if vol <= 1e-9 else min(1.0, abs(predicted_return) / vol)
                dynamic_epsilon = self._config.epsilon_max - (
                    self._config.epsilon_max - self._config.epsilon_min
                ) * confidence
                self._bandit.set_epsilon(dynamic_epsilon)

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

        if predicted_return is not None:
            reward += self._ml_reward_adjustment(predicted_return, params)

        sentiment_snapshot = self._sentiment_snapshot()
        if sentiment_snapshot is not None:
            reward += self._sentiment_reward_adjustment(sentiment_snapshot, params)

        self._bandit.update(params, reward)
        self._last_selected = params
        return AdaptiveDecision(
            selected_params=params,
            optimization=optimization,
            mode=mode,
            predicted_return=predicted_return,
            dynamic_epsilon=dynamic_epsilon,
            sentiment_score=None if sentiment_snapshot is None else sentiment_snapshot.score,
            sentiment_confidence=None if sentiment_snapshot is None else sentiment_snapshot.confidence,
        )

    def _ml_reward_adjustment(self, predicted_return: float, params: StrategyParameterSet) -> float:
        # Map params to aggressiveness in [0, 1]: faster MA pair => more aggressive.
        aggressiveness = params.fast_window / params.slow_window
        target_aggressiveness = min(1.0, abs(predicted_return) * 150.0)
        mismatch_penalty = abs(aggressiveness - target_aggressiveness)
        return -self._config.ml_weight * mismatch_penalty

    def _sentiment_snapshot(self) -> SentimentSnapshot | None:
        if not self._config.enable_sentiment_overlay:
            return None
        if self._sentiment_pipeline is None:
            return None
        lookback = timedelta(hours=self._config.sentiment_lookback_hours)
        return self._sentiment_pipeline.snapshot(lookback=lookback)

    def _sentiment_reward_adjustment(
        self,
        snapshot: SentimentSnapshot,
        params: StrategyParameterSet,
    ) -> float:
        aggressiveness = params.fast_window / params.slow_window
        sentiment_target = (snapshot.score + 1.0) / 2.0
        mismatch_penalty = abs(aggressiveness - sentiment_target)
        confidence = snapshot.confidence
        return -self._config.sentiment_weight * confidence * mismatch_penalty


def _market_returns(events: Sequence[MarketEvent]) -> list[float]:
    return _returns([e.close for e in events])


def _returns(closes: Sequence[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev == 0:
            out.append(0.0)
        else:
            out.append((closes[i] - prev) / prev)
    return out


def _feature_vector(returns: Sequence[float], idx: int, window: int) -> list[float]:
    tail = returns[max(0, idx - window + 1) : idx + 1]
    r_now = returns[idx]
    momentum = sum(tail) / len(tail)
    volatility = _stdev(tail)
    return [1.0, r_now, momentum, volatility]


def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return var**0.5


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
