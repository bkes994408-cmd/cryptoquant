from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

from cryptoquant.aggregation import Bar
from cryptoquant.events.market import MarketEvent
from cryptoquant.execution import PaperExecutor
from cryptoquant.oms import OMS
from cryptoquant.strategy.ma_crossover import MovingAverageCrossoverStrategy

OptimizationObjective = Literal["net_pnl", "win_rate"]


@dataclass(frozen=True)
class StrategyParameterSet:
    fast_window: int
    slow_window: int


@dataclass(frozen=True)
class OptimizationMetrics:
    net_pnl: float
    win_rate: float
    close_trades: int


@dataclass(frozen=True)
class StrategyEvaluation:
    params: StrategyParameterSet
    score: float
    metrics: OptimizationMetrics
    fills: int


@dataclass(frozen=True)
class StrategyOptimizationResult:
    best: StrategyEvaluation
    leaderboard: list[StrategyEvaluation]


@dataclass
class _PositionState:
    qty: float = 0.0
    avg_entry_price: float = 0.0


class AutomatedStrategyOptimizer:
    """Run parameter search over strategy configs using paper execution replay."""

    def __init__(
        self,
        *,
        symbol: str,
        base_qty: float = 1.0,
        objective: OptimizationObjective = "net_pnl",
        fee_bps: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> None:
        if base_qty <= 0:
            raise ValueError("base_qty must be positive")
        self._symbol = symbol
        self._base_qty = base_qty
        self._objective = objective
        self._fee_bps = fee_bps
        self._slippage_bps = slippage_bps

    def optimize(
        self,
        events: Iterable[MarketEvent],
        *,
        param_grid: Sequence[StrategyParameterSet],
    ) -> StrategyOptimizationResult:
        candidate_events = sorted((e for e in events if e.symbol == self._symbol), key=lambda e: e.ts)
        if not candidate_events:
            raise ValueError("no events for optimization symbol")

        evaluations: list[StrategyEvaluation] = []
        for params in param_grid:
            if params.fast_window >= params.slow_window:
                continue
            evaluations.append(self._evaluate(candidate_events, params))

        if not evaluations:
            raise ValueError("no valid parameter set to optimize")

        leaderboard = sorted(evaluations, key=lambda x: x.score, reverse=True)
        return StrategyOptimizationResult(best=leaderboard[0], leaderboard=leaderboard)

    def _evaluate(self, events: Sequence[MarketEvent], params: StrategyParameterSet) -> StrategyEvaluation:
        strategy = MovingAverageCrossoverStrategy(
            fast_window=params.fast_window,
            slow_window=params.slow_window,
            base_qty=self._base_qty,
        )
        oms = OMS()
        executor = PaperExecutor(oms, fee_bps=self._fee_bps, slippage_bps=self._slippage_bps)

        bars: list[Bar] = []
        fills = 0
        fees_and_slippage = 0.0
        realized_pnl = 0.0
        close_trades = 0
        winning_closes = 0
        position = _PositionState()

        for idx, event in enumerate(events, start=1):
            bars.append(_market_event_to_bar(event))
            target_qty = strategy.target_qty(bars)
            current_qty = executor.position_qty(self._symbol)
            legs = executor.execute_to_target(
                client_order_id_prefix=f"opt-{params.fast_window}-{params.slow_window}-{idx}",
                symbol=self._symbol,
                current_qty=current_qty,
                target_qty=target_qty,
                mark_price=event.close,
                ts=event.ts,
            )
            for fill in legs:
                fills += 1
                fees_and_slippage += fill.fee + fill.slippage_cost
                close_pnl, closed = _apply_fill(position, fill.qty, fill.fill_price)
                if closed:
                    close_trades += 1
                    realized_pnl += close_pnl
                    if close_pnl > 0:
                        winning_closes += 1

        last_px = events[-1].close
        unrealized = 0.0 if position.qty == 0 else position.qty * (last_px - position.avg_entry_price)
        net_pnl = realized_pnl + unrealized - fees_and_slippage
        win_rate = 0.0 if close_trades == 0 else winning_closes / close_trades

        metrics = OptimizationMetrics(net_pnl=net_pnl, win_rate=win_rate, close_trades=close_trades)
        score = net_pnl if self._objective == "net_pnl" else win_rate
        return StrategyEvaluation(params=params, score=score, metrics=metrics, fills=fills)


def _market_event_to_bar(event: MarketEvent) -> Bar:
    return Bar(
        symbol=event.symbol,
        timeframe=event.timeframe,
        ts=event.ts,
        open=event.close,
        high=event.close,
        low=event.close,
        close=event.close,
        volume=0.0,
    )


def _apply_fill(position: _PositionState, qty: float, fill_price: float) -> tuple[float, bool]:
    old_qty = position.qty
    old_avg = position.avg_entry_price
    close_pnl = 0.0
    closed_trade = False

    if old_qty == 0 or old_qty * qty > 0:
        new_qty = old_qty + qty
        total_cost = abs(old_qty) * old_avg + abs(qty) * fill_price
        position.avg_entry_price = total_cost / abs(new_qty)
        position.qty = new_qty
        return close_pnl, closed_trade

    close_qty = min(abs(old_qty), abs(qty))
    side = 1.0 if old_qty > 0 else -1.0
    close_pnl = close_qty * (fill_price - old_avg) * side
    closed_trade = True

    new_qty = old_qty + qty
    if new_qty == 0:
        position.qty = 0.0
        position.avg_entry_price = 0.0
    elif old_qty * new_qty > 0:
        position.qty = new_qty
    else:
        position.qty = new_qty
        position.avg_entry_price = fill_price

    return close_pnl, closed_trade
