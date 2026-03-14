from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptoquant.sentiment import InMemorySentimentAdapter, SentimentItem, SentimentPipeline


def test_sentiment_pipeline_produces_positive_score_with_recent_positive_news() -> None:
    now = datetime.now(timezone.utc)
    adapter = InMemorySentimentAdapter(
        [
            SentimentItem(
                source="news",
                text="ETF adoption drives bullish breakout and strong demand",
                ts=now - timedelta(hours=2),
            ),
            SentimentItem(
                source="social",
                text="bearish liquidation fear after hack rumor",
                ts=now - timedelta(hours=20),
            ),
        ]
    )
    pipeline = SentimentPipeline(adapter)

    snapshot = pipeline.snapshot(lookback=timedelta(hours=24))

    assert snapshot.score > 0
    assert 0 <= snapshot.confidence <= 1
    assert snapshot.sample_size == 2


def test_sentiment_pipeline_returns_neutral_when_no_keywords_match() -> None:
    now = datetime.now(timezone.utc)
    adapter = InMemorySentimentAdapter(
        [
            SentimentItem(source="news", text="market update without clear direction", ts=now),
            SentimentItem(source="social", text="just observing volatility", ts=now),
        ]
    )
    pipeline = SentimentPipeline(adapter)

    snapshot = pipeline.snapshot(lookback=timedelta(hours=24))

    assert snapshot.score == 0.0
    assert snapshot.confidence == 0.0
    assert snapshot.sample_size == 2
