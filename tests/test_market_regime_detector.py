from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cryptoquant.events.market import MarketEvent
from cryptoquant.strategy import (
    EventRegime,
    MarketRegimeConfig,
    MarketRegimeDetector,
    MarketRegimeProfile,
    MeanReversionRegime,
    TrendRegime,
    VolatilityRegime,
)


def _events(closes: list[float]) -> list[MarketEvent]:
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)
    return [
        MarketEvent(
            symbol="BTCUSDT",
            timeframe="1m",
            close=close,
            ts=base + timedelta(minutes=i),
            source="test",
        )
        for i, close in enumerate(closes)
    ]


def test_market_regime_detector_identifies_trend_profile() -> None:
    detector = MarketRegimeDetector(MarketRegimeConfig(lookback_events=30))
    closes = [100.0 + (0.8 * i) for i in range(30)]

    regime = detector.detect(_events(closes))

    assert regime.trend == TrendRegime.UP
    assert regime.event == EventRegime.CALM
    assert regime.profile == MarketRegimeProfile.TREND


def test_market_regime_detector_identifies_high_volatility_profile() -> None:
    detector = MarketRegimeDetector(
        MarketRegimeConfig(
            lookback_events=30,
            trend_threshold=0.5,
            volatility_high_threshold=0.01,
            event_jump_threshold=0.05,
        )
    )
    closes: list[float] = [100.0]
    for i in range(1, 30):
        closes.append(closes[-1] * (1.03 if i % 2 else 0.97))

    regime = detector.detect(_events(closes))

    assert regime.volatility == VolatilityRegime.HIGH
    assert regime.profile == MarketRegimeProfile.VOLATILITY


def test_market_regime_detector_identifies_event_profile_with_jump() -> None:
    detector = MarketRegimeDetector(MarketRegimeConfig(lookback_events=30, event_jump_threshold=0.015))
    closes = [100.0 + (0.1 * i) for i in range(29)] + [106.0]

    regime = detector.detect(_events(closes))

    assert regime.event == EventRegime.EVENT
    assert regime.profile == MarketRegimeProfile.EVENT
    assert regime.confidence == 1.0


def test_market_regime_detector_identifies_mean_reversion_profile_when_sideways_but_stretched() -> None:
    detector = MarketRegimeDetector(
        MarketRegimeConfig(
            lookback_events=30,
            trend_threshold=0.2,
            mean_reversion_zscore=0.9,
            volatility_high_threshold=0.03,
            event_jump_threshold=0.05,
        )
    )
    closes = [100.0] * 29 + [102.0]

    regime = detector.detect(_events(closes))

    assert regime.trend == TrendRegime.SIDEWAYS
    assert regime.mean_reversion == MeanReversionRegime.STRETCHED
    assert regime.profile == MarketRegimeProfile.MEAN_REVERSION


def test_market_regime_detector_requires_enough_history() -> None:
    detector = MarketRegimeDetector(MarketRegimeConfig(lookback_events=10))
    with pytest.raises(ValueError, match="insufficient history"):
        detector.detect(_events([100.0] * 9))
