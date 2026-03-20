from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .performance import PerformanceSnapshot


@dataclass(frozen=True)
class RiskEvent:
    ts: datetime
    level: str
    code: str
    message: str


@dataclass(frozen=True)
class StrategyHealthSample:
    ts: datetime
    strategy_id: str
    healthy: bool
    latency_ms: float
    error_rate: float


@dataclass(frozen=True)
class PnLView:
    ts: datetime
    realized_pnl: float
    unrealized_pnl: float
    net_pnl: float
    max_drawdown: float


@dataclass(frozen=True)
class StrategyHealthView:
    strategy_id: str
    latest_healthy: bool
    uptime_ratio: float
    avg_latency_ms: float
    avg_error_rate: float


@dataclass(frozen=True)
class PerformanceSummary:
    period: str
    from_ts: datetime
    to_ts: datetime
    samples: int
    net_pnl_open: float
    net_pnl_close: float
    net_pnl_change: float
    net_pnl_avg: float
    net_pnl_max: float
    net_pnl_min: float
    risk_event_count: int
    risk_event_by_level: dict[str, int]
    strategy_health: dict[str, StrategyHealthView]


@dataclass(frozen=True)
class OperationalDashboardView:
    pnl: PnLView
    risk_event_total: int
    risk_event_by_level: dict[str, int]
    strategy_health: dict[str, StrategyHealthView]


class OperationalDashboard:
    """MVP-21: real-time operation dashboard aggregator.

    Scope:
    - real-time PnL view (using PerformanceSnapshot)
    - risk event statistics
    - strategy health monitor
    - daily / weekly performance summary
    """

    def __init__(self, *, max_samples: int = 20_000) -> None:
        if max_samples < 10:
            raise ValueError("max_samples must be >= 10")
        self._max_samples = max_samples
        self._perf_samples: list[PerformanceSnapshot] = []
        self._risk_events: list[RiskEvent] = []
        self._health_samples: list[StrategyHealthSample] = []

    def record_performance(self, snapshot: PerformanceSnapshot) -> None:
        self._perf_samples.append(snapshot)
        self._trim_if_needed()

    def record_risk_event(
        self,
        *,
        level: str,
        code: str,
        message: str,
        ts: datetime | None = None,
    ) -> None:
        self._risk_events.append(
            RiskEvent(
                ts=ts or datetime.now(timezone.utc),
                level=level.upper(),
                code=code,
                message=message,
            )
        )
        self._trim_if_needed()

    def record_strategy_health(
        self,
        *,
        strategy_id: str,
        healthy: bool,
        latency_ms: float,
        error_rate: float,
        ts: datetime | None = None,
    ) -> None:
        if latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        if error_rate < 0 or error_rate > 1:
            raise ValueError("error_rate must be in [0, 1]")

        self._health_samples.append(
            StrategyHealthSample(
                ts=ts or datetime.now(timezone.utc),
                strategy_id=strategy_id,
                healthy=healthy,
                latency_ms=latency_ms,
                error_rate=error_rate,
            )
        )
        self._trim_if_needed()

    def live_view(self) -> OperationalDashboardView:
        if not self._perf_samples:
            raise ValueError("no performance sample available")

        latest = self._perf_samples[-1]
        pnl = PnLView(
            ts=latest.ts,
            realized_pnl=latest.realized_pnl,
            unrealized_pnl=latest.unrealized_pnl,
            net_pnl=latest.net_pnl,
            max_drawdown=latest.max_drawdown,
        )

        return OperationalDashboardView(
            pnl=pnl,
            risk_event_total=len(self._risk_events),
            risk_event_by_level=self._count_risk_levels(self._risk_events),
            strategy_health=self._aggregate_health(self._health_samples),
        )

    def summarize(self, *, period: str, as_of: datetime | None = None) -> PerformanceSummary:
        if period not in {"daily", "weekly"}:
            raise ValueError("period must be one of: daily, weekly")

        anchor = as_of or datetime.now(timezone.utc)
        if period == "daily":
            start = anchor - timedelta(days=1)
        else:
            start = anchor - timedelta(days=7)

        perf = [sample for sample in self._perf_samples if start <= sample.ts <= anchor]
        if not perf:
            raise ValueError("no performance sample in requested period")

        net_values = [sample.net_pnl for sample in perf]
        risk = [event for event in self._risk_events if start <= event.ts <= anchor]
        health = [sample for sample in self._health_samples if start <= sample.ts <= anchor]

        return PerformanceSummary(
            period=period,
            from_ts=start,
            to_ts=anchor,
            samples=len(perf),
            net_pnl_open=net_values[0],
            net_pnl_close=net_values[-1],
            net_pnl_change=net_values[-1] - net_values[0],
            net_pnl_avg=sum(net_values) / len(net_values),
            net_pnl_max=max(net_values),
            net_pnl_min=min(net_values),
            risk_event_count=len(risk),
            risk_event_by_level=self._count_risk_levels(risk),
            strategy_health=self._aggregate_health(health),
        )

    def _count_risk_levels(self, events: list[RiskEvent]) -> dict[str, int]:
        out: dict[str, int] = {}
        for event in events:
            out[event.level] = out.get(event.level, 0) + 1
        return out

    def _aggregate_health(self, samples: list[StrategyHealthSample]) -> dict[str, StrategyHealthView]:
        if not samples:
            return {}

        grouped: dict[str, list[StrategyHealthSample]] = {}
        for sample in samples:
            grouped.setdefault(sample.strategy_id, []).append(sample)

        result: dict[str, StrategyHealthView] = {}
        for strategy_id, strategy_samples in grouped.items():
            strategy_samples = sorted(strategy_samples, key=lambda s: s.ts)
            healthy_count = sum(1 for s in strategy_samples if s.healthy)
            avg_latency = sum(s.latency_ms for s in strategy_samples) / len(strategy_samples)
            avg_error = sum(s.error_rate for s in strategy_samples) / len(strategy_samples)
            result[strategy_id] = StrategyHealthView(
                strategy_id=strategy_id,
                latest_healthy=strategy_samples[-1].healthy,
                uptime_ratio=healthy_count / len(strategy_samples),
                avg_latency_ms=avg_latency,
                avg_error_rate=avg_error,
            )
        return result

    def _trim_if_needed(self) -> None:
        def trim[T](items: list[T]) -> list[T]:
            if len(items) <= self._max_samples:
                return items
            return items[-self._max_samples :]

        self._perf_samples = trim(self._perf_samples)
        self._risk_events = trim(self._risk_events)
        self._health_samples = trim(self._health_samples)
