from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from typing import Callable, Sequence

from cryptoquant.events.market import MarketEvent
from cryptoquant.execution import Fill, PaperExecutor
from cryptoquant.oms import OMS


@dataclass(frozen=True)
class StrategyMetrics:
    trades: int
    turnover: float
    pnl: float
    return_pct: float
    win_rate: float


@dataclass(frozen=True)
class WalkForwardConfig:
    train_size: int
    test_size: int
    step_size: int | None = None
    initial_equity: float = 10_000.0
    fee_bps: float = 4.0
    slippage_bps: float = 2.0


@dataclass(frozen=True)
class WalkForwardSliceResult:
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_metrics: StrategyMetrics
    test_metrics: StrategyMetrics


@dataclass(frozen=True)
class WalkForwardReport:
    slices: list[WalkForwardSliceResult]
    avg_test_return_pct: float
    positive_test_ratio: float


@dataclass(frozen=True)
class RegimeSplitConfig:
    return_threshold: float = 0.002
    initial_equity: float = 10_000.0
    fee_bps: float = 4.0
    slippage_bps: float = 2.0


@dataclass(frozen=True)
class RegimeSplitReport:
    bull: StrategyMetrics | None
    sideways: StrategyMetrics | None
    bear: StrategyMetrics | None


def _ensure_sorted(events: Sequence[MarketEvent], *, symbol: str) -> list[MarketEvent]:
    filtered = [event for event in events if event.symbol == symbol]
    if not filtered:
        raise ValueError(f"no events for symbol={symbol}")
    return sorted(filtered, key=lambda e: e.ts)


def evaluate_strategy_metrics(
    events: Sequence[MarketEvent],
    *,
    symbol: str,
    target_qty_fn: Callable[[MarketEvent], float],
    initial_equity: float = 10_000.0,
    fee_bps: float = 4.0,
    slippage_bps: float = 2.0,
) -> StrategyMetrics:
    if initial_equity <= 0:
        raise ValueError("initial_equity must be > 0")

    sorted_events = _ensure_sorted(events, symbol=symbol)

    oms = OMS()
    executor = PaperExecutor(oms, fee_bps=fee_bps, slippage_bps=slippage_bps)

    fills: list[Fill] = []
    for idx, event in enumerate(sorted_events, start=1):
        target_qty = target_qty_fn(event)
        current_qty = executor.position_qty(symbol)
        fills.extend(
            executor.execute_to_target(
                client_order_id_prefix=f"robust-{idx}",
                symbol=symbol,
                current_qty=current_qty,
                target_qty=target_qty,
                mark_price=event.close,
                ts=event.ts,
            )
        )

    final_price = sorted_events[-1].close
    position = 0.0
    cash = 0.0
    realized_wins = 0

    for fill in fills:
        position += fill.qty
        cash -= fill.qty * fill.fill_price
        cash -= fill.fee
        if (fill.qty > 0 and fill.fill_price <= fill.requested_price) or (
            fill.qty < 0 and fill.fill_price >= fill.requested_price
        ):
            realized_wins += 1

    equity = cash + position * final_price
    pnl = equity
    turnover = sum(abs(fill.notional) for fill in fills)
    return_pct = (pnl / initial_equity) * 100.0
    win_rate = (realized_wins / len(fills)) if fills else 0.0

    return StrategyMetrics(
        trades=len(fills),
        turnover=turnover,
        pnl=pnl,
        return_pct=return_pct,
        win_rate=win_rate,
    )


def run_walk_forward_validation(
    events: Sequence[MarketEvent],
    *,
    symbol: str,
    target_qty_fn: Callable[[MarketEvent], float],
    config: WalkForwardConfig,
) -> WalkForwardReport:
    if config.train_size <= 0 or config.test_size <= 0:
        raise ValueError("train_size/test_size must be > 0")

    sorted_events = _ensure_sorted(events, symbol=symbol)
    if len(sorted_events) < config.train_size + config.test_size:
        raise ValueError("insufficient events for requested walk-forward windows")

    step = config.step_size or config.test_size
    if step <= 0:
        raise ValueError("step_size must be > 0")

    slices: list[WalkForwardSliceResult] = []
    start = 0
    while start + config.train_size + config.test_size <= len(sorted_events):
        train = sorted_events[start : start + config.train_size]
        test = sorted_events[start + config.train_size : start + config.train_size + config.test_size]

        train_metrics = evaluate_strategy_metrics(
            train,
            symbol=symbol,
            target_qty_fn=target_qty_fn,
            initial_equity=config.initial_equity,
            fee_bps=config.fee_bps,
            slippage_bps=config.slippage_bps,
        )
        test_metrics = evaluate_strategy_metrics(
            test,
            symbol=symbol,
            target_qty_fn=target_qty_fn,
            initial_equity=config.initial_equity,
            fee_bps=config.fee_bps,
            slippage_bps=config.slippage_bps,
        )

        slices.append(
            WalkForwardSliceResult(
                train_start=train[0].ts,
                train_end=train[-1].ts,
                test_start=test[0].ts,
                test_end=test[-1].ts,
                train_metrics=train_metrics,
                test_metrics=test_metrics,
            )
        )
        start += step

    avg_test_return_pct = mean(slice_result.test_metrics.return_pct for slice_result in slices)
    positive_test_ratio = mean(1.0 if slice_result.test_metrics.pnl > 0 else 0.0 for slice_result in slices)

    return WalkForwardReport(
        slices=slices,
        avg_test_return_pct=avg_test_return_pct,
        positive_test_ratio=positive_test_ratio,
    )


def run_regime_split_validation(
    events: Sequence[MarketEvent],
    *,
    symbol: str,
    target_qty_fn: Callable[[MarketEvent], float],
    config: RegimeSplitConfig,
) -> RegimeSplitReport:
    sorted_events = _ensure_sorted(events, symbol=symbol)

    bull: list[MarketEvent] = []
    sideways: list[MarketEvent] = []
    bear: list[MarketEvent] = []

    for idx in range(1, len(sorted_events)):
        prev_event = sorted_events[idx - 1]
        event = sorted_events[idx]
        ret = (event.close / prev_event.close) - 1.0
        if ret >= config.return_threshold:
            bull.append(event)
        elif ret <= -config.return_threshold:
            bear.append(event)
        else:
            sideways.append(event)

    def _metrics_or_none(regime_events: list[MarketEvent]) -> StrategyMetrics | None:
        if not regime_events:
            return None
        return evaluate_strategy_metrics(
            regime_events,
            symbol=symbol,
            target_qty_fn=target_qty_fn,
            initial_equity=config.initial_equity,
            fee_bps=config.fee_bps,
            slippage_bps=config.slippage_bps,
        )

    return RegimeSplitReport(
        bull=_metrics_or_none(bull),
        sideways=_metrics_or_none(sideways),
        bear=_metrics_or_none(bear),
    )
