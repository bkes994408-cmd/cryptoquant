from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import exp
from typing import Protocol, Sequence


@dataclass(frozen=True)
class SentimentItem:
    source: str
    text: str
    ts: datetime
    weight: float = 1.0


@dataclass(frozen=True)
class SentimentSnapshot:
    score: float
    confidence: float
    positive_hits: int
    negative_hits: int
    sample_size: int


class SentimentAdapter(Protocol):
    """Adapter interface for collecting unstructured sentiment inputs."""

    def fetch(self, *, since: datetime | None = None, limit: int = 200) -> list[SentimentItem]:
        ...


class InMemorySentimentAdapter:
    """Deterministic adapter used for tests and local prototyping."""

    def __init__(self, items: Sequence[SentimentItem]) -> None:
        self._items = list(items)

    def fetch(self, *, since: datetime | None = None, limit: int = 200) -> list[SentimentItem]:
        filtered = [
            item for item in self._items if since is None or item.ts >= since
        ]
        filtered.sort(key=lambda item: item.ts, reverse=True)
        return filtered[:limit]


class KeywordSentimentScorer:
    """Simple lexicon-based scoring for first MVP increment."""

    POSITIVE_KEYWORDS = {
        "bull",
        "bullish",
        "breakout",
        "surge",
        "adoption",
        "record high",
        "upgrade",
        "strong",
        "positive",
    }
    NEGATIVE_KEYWORDS = {
        "bear",
        "bearish",
        "dump",
        "hack",
        "ban",
        "lawsuit",
        "downgrade",
        "weak",
        "negative",
        "liquidation",
    }

    SOURCE_WEIGHTS = {
        "news": 1.25,
        "social": 1.0,
        "forum": 0.9,
    }

    def score(self, items: Sequence[SentimentItem]) -> SentimentSnapshot:
        if not items:
            return SentimentSnapshot(
                score=0.0,
                confidence=0.0,
                positive_hits=0,
                negative_hits=0,
                sample_size=0,
            )

        now = max(item.ts for item in items)
        weighted_sum = 0.0
        total_weight = 0.0
        pos = 0
        neg = 0

        for item in items:
            text = item.text.lower()
            p_hits = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text)
            n_hits = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text)

            if p_hits == 0 and n_hits == 0:
                continue

            raw = p_hits - n_hits
            if raw > 0:
                pos += raw
            elif raw < 0:
                neg += -raw

            src_w = self.SOURCE_WEIGHTS.get(item.source.lower(), 1.0)
            recency_w = _recency_weight(item.ts, now)
            w = max(0.0, item.weight) * src_w * recency_w
            weighted_sum += raw * w
            total_weight += abs(raw) * w

        if total_weight <= 1e-9:
            return SentimentSnapshot(
                score=0.0,
                confidence=0.0,
                positive_hits=0,
                negative_hits=0,
                sample_size=len(items),
            )

        score = max(-1.0, min(1.0, weighted_sum / total_weight))
        confidence = min(1.0, total_weight / max(5.0, len(items)))
        return SentimentSnapshot(
            score=score,
            confidence=confidence,
            positive_hits=pos,
            negative_hits=neg,
            sample_size=len(items),
        )


class SentimentPipeline:
    """Adapter + scorer pipeline."""

    def __init__(self, adapter: SentimentAdapter, scorer: KeywordSentimentScorer | None = None) -> None:
        self._adapter = adapter
        self._scorer = scorer or KeywordSentimentScorer()

    def snapshot(self, *, lookback: timedelta = timedelta(hours=24), limit: int = 200) -> SentimentSnapshot:
        since = datetime.now(timezone.utc) - lookback
        items = self._adapter.fetch(since=since, limit=limit)
        return self._scorer.score(items)


def _recency_weight(ts: datetime, now: datetime) -> float:
    delta_hours = max(0.0, (now - ts).total_seconds() / 3600.0)
    # Half-life ~= 12h
    return exp(-delta_hours / 17.31234049066756)
