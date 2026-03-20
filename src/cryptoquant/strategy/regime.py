from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, sqrt
from statistics import mean, pstdev
from typing import Sequence

from cryptoquant.events.market import MarketEvent


class TrendRegime(str, Enum):
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"


class MeanReversionRegime(str, Enum):
    STRETCHED = "stretched"
    NEUTRAL = "neutral"


class VolatilityRegime(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class EventRegime(str, Enum):
    CALM = "calm"
    EVENT = "event"


class MarketRegimeProfile(str, Enum):
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    EVENT = "event"


@dataclass(frozen=True)
class MarketRegime:
    trend: TrendRegime
    mean_reversion: MeanReversionRegime
    volatility: VolatilityRegime
    event: EventRegime
    profile: MarketRegimeProfile
    confidence: float
    trend_score: float
    z_score: float
    volatility_value: float


@dataclass(frozen=True)
class MarketRegimeConfig:
    lookback_events: int = 30
    trend_threshold: float = 0.01
    mean_reversion_zscore: float = 1.2
    volatility_low_threshold: float = 0.004
    volatility_high_threshold: float = 0.012
    event_jump_threshold: float = 0.02


class MarketRegimeDetector:
    def __init__(self, config: MarketRegimeConfig | None = None) -> None:
        self._config = config or MarketRegimeConfig()
        if self._config.lookback_events < 5:
            raise ValueError("lookback_events must be >= 5")

    def detect(self, events: Sequence[MarketEvent], *, event_intensity: float = 0.0) -> MarketRegime:
        if len(events) < self._config.lookback_events:
            raise ValueError("insufficient history for regime detection")

        closes = [float(e.close) for e in events[-self._config.lookback_events :]]
        if any((not isfinite(v) or v <= 0.0) for v in closes):
            raise ValueError("close values must be finite and > 0")

        returns = [(closes[i] / closes[i - 1]) - 1.0 for i in range(1, len(closes))]
        trend_score = (closes[-1] / closes[0]) - 1.0
        vol = _stddev(returns)

        avg = mean(closes)
        sigma = pstdev(closes)
        z_score = 0.0 if sigma == 0.0 else (closes[-1] - avg) / sigma

        if trend_score >= self._config.trend_threshold:
            trend = TrendRegime.UP
        elif trend_score <= -self._config.trend_threshold:
            trend = TrendRegime.DOWN
        else:
            trend = TrendRegime.SIDEWAYS

        mean_reversion = (
            MeanReversionRegime.STRETCHED
            if abs(z_score) >= self._config.mean_reversion_zscore
            else MeanReversionRegime.NEUTRAL
        )

        if vol >= self._config.volatility_high_threshold:
            volatility = VolatilityRegime.HIGH
        elif vol <= self._config.volatility_low_threshold:
            volatility = VolatilityRegime.LOW
        else:
            volatility = VolatilityRegime.NORMAL

        recent_jump = abs(returns[-1]) if returns else 0.0
        event = (
            EventRegime.EVENT
            if max(abs(event_intensity), recent_jump) >= self._config.event_jump_threshold
            else EventRegime.CALM
        )

        profile = _select_profile(trend=trend, mean_reversion=mean_reversion, volatility=volatility, event=event)
        confidence = _confidence(
            trend_score=trend_score,
            z_score=z_score,
            volatility=vol,
            config=self._config,
            event=event,
        )
        return MarketRegime(
            trend=trend,
            mean_reversion=mean_reversion,
            volatility=volatility,
            event=event,
            profile=profile,
            confidence=confidence,
            trend_score=trend_score,
            z_score=z_score,
            volatility_value=vol,
        )


def _stddev(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mu = mean(values)
    var = sum((v - mu) ** 2 for v in values) / len(values)
    return sqrt(var)


def _select_profile(
    *,
    trend: TrendRegime,
    mean_reversion: MeanReversionRegime,
    volatility: VolatilityRegime,
    event: EventRegime,
) -> MarketRegimeProfile:
    if event == EventRegime.EVENT:
        return MarketRegimeProfile.EVENT
    if volatility == VolatilityRegime.HIGH:
        return MarketRegimeProfile.VOLATILITY
    if trend in {TrendRegime.UP, TrendRegime.DOWN}:
        return MarketRegimeProfile.TREND
    if mean_reversion == MeanReversionRegime.STRETCHED:
        return MarketRegimeProfile.MEAN_REVERSION
    return MarketRegimeProfile.TREND


def _confidence(
    *,
    trend_score: float,
    z_score: float,
    volatility: float,
    config: MarketRegimeConfig,
    event: EventRegime,
) -> float:
    if event == EventRegime.EVENT:
        return 1.0

    trend_component = min(abs(trend_score) / max(config.trend_threshold, 1e-9), 1.0)
    mean_component = min(abs(z_score) / max(config.mean_reversion_zscore, 1e-9), 1.0)
    vol_component = min(volatility / max(config.volatility_high_threshold, 1e-9), 1.0)
    return max(0.0, min(1.0, 0.4 * trend_component + 0.4 * mean_component + 0.2 * vol_component))
