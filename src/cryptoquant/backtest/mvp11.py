from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from cryptoquant.events.market import MarketEvent
from cryptoquant.execution import Fill, PaperExecutor
from cryptoquant.oms import OMS


@dataclass(frozen=True)
class ExecutionModelConfig:
    fee_bps: float = 4.0
    slippage_bps: float = 2.0
    latency_bars: int = 0
    initial_equity: float = 10_000.0


@dataclass(frozen=True)
class RealisticBacktestResult:
    fills: list[Fill]
    equity_curve: list[float]
    final_equity: float
    total_fee: float
    total_slippage_cost: float


@dataclass(frozen=True)
class RegimeScenario:
    name: str
    slippage_multiplier: float = 1.0
    fee_multiplier: float = 1.0
    latency_bars: int | None = None


@dataclass(frozen=True)
class RegimeScenarioResult:
    scenario: RegimeScenario
    result: RealisticBacktestResult


def simulate_realistic_execution(
    events: Sequence[MarketEvent],
    *,
    symbol: str,
    target_qty_fn: Callable[[MarketEvent], float],
    config: ExecutionModelConfig = ExecutionModelConfig(),
    order_id_prefix: str = "mvp11",
) -> RealisticBacktestResult:
    if config.initial_equity <= 0:
        raise ValueError("initial_equity must be > 0")
    if config.latency_bars < 0:
        raise ValueError("latency_bars must be >= 0")

    ordered = sorted((event for event in events if event.symbol == symbol), key=lambda event: event.ts)
    if not ordered:
        raise ValueError(f"no events for symbol={symbol}")

    oms = OMS()
    executor = PaperExecutor(oms, fee_bps=config.fee_bps, slippage_bps=config.slippage_bps)

    pending: list[tuple[int, int, float]] = []
    fills: list[Fill] = []
    expected_qty = 0.0
    cash = config.initial_equity
    equity_curve: list[float] = []
    sequence = 0

    for idx, event in enumerate(ordered):
        matured = [item for item in pending if item[0] == idx]
        if matured:
            pending = [item for item in pending if item[0] != idx]
            for _, scheduled_seq, delta_qty in matured:
                fill = executor.execute_market(
                    client_order_id=f"{order_id_prefix}-{scheduled_seq}",
                    symbol=symbol,
                    qty=delta_qty,
                    mark_price=event.close,
                    ts=event.ts,
                )
                fills.append(fill)
                cash -= fill.qty * fill.fill_price
                cash -= fill.fee

        target_qty = target_qty_fn(event)
        delta_qty = target_qty - expected_qty
        if delta_qty != 0:
            execute_idx = min(idx + config.latency_bars, len(ordered) - 1)
            pending.append((execute_idx, sequence, delta_qty))
            expected_qty += delta_qty
            sequence += 1

        position = executor.position_qty(symbol)
        equity_curve.append(cash + position * event.close)

    if pending:
        last_event = ordered[-1]
        for _, scheduled_seq, delta_qty in pending:
            fill = executor.execute_market(
                client_order_id=f"{order_id_prefix}-{scheduled_seq}",
                symbol=symbol,
                qty=delta_qty,
                mark_price=last_event.close,
                ts=last_event.ts,
            )
            fills.append(fill)
            cash -= fill.qty * fill.fill_price
            cash -= fill.fee
        equity_curve[-1] = cash + executor.position_qty(symbol) * last_event.close

    total_fee = sum(fill.fee for fill in fills)
    total_slippage_cost = sum(fill.slippage_cost for fill in fills)

    return RealisticBacktestResult(
        fills=fills,
        equity_curve=equity_curve,
        final_equity=equity_curve[-1],
        total_fee=total_fee,
        total_slippage_cost=total_slippage_cost,
    )


def run_regime_scenarios(
    events: Sequence[MarketEvent],
    *,
    symbol: str,
    target_qty_fn: Callable[[MarketEvent], float],
    scenarios: Sequence[RegimeScenario],
    base_config: ExecutionModelConfig = ExecutionModelConfig(),
) -> list[RegimeScenarioResult]:
    results: list[RegimeScenarioResult] = []
    for scenario in scenarios:
        scenario_config = ExecutionModelConfig(
            fee_bps=base_config.fee_bps * scenario.fee_multiplier,
            slippage_bps=base_config.slippage_bps * scenario.slippage_multiplier,
            latency_bars=base_config.latency_bars if scenario.latency_bars is None else scenario.latency_bars,
            initial_equity=base_config.initial_equity,
        )
        result = simulate_realistic_execution(
            events,
            symbol=symbol,
            target_qty_fn=target_qty_fn,
            config=scenario_config,
            order_id_prefix=f"regime-{scenario.name}",
        )
        results.append(RegimeScenarioResult(scenario=scenario, result=result))
    return results


def run_multi_strategy_portfolio_backtest(
    events: Sequence[MarketEvent],
    *,
    symbol: str,
    strategy_target_qty_fns: Mapping[str, Callable[[MarketEvent], float]],
    weights: Mapping[str, float] | None = None,
    config: ExecutionModelConfig = ExecutionModelConfig(),
) -> RealisticBacktestResult:
    if not strategy_target_qty_fns:
        raise ValueError("at least one strategy is required")

    names = sorted(strategy_target_qty_fns.keys())
    if weights is None:
        normalized_weights = {name: 1.0 / len(names) for name in names}
    else:
        if set(weights.keys()) != set(names):
            raise ValueError("weights keys must match strategy names")
        total_weight = sum(float(weights[name]) for name in names)
        if total_weight <= 0:
            raise ValueError("weights sum must be > 0")
        normalized_weights = {name: float(weights[name]) / total_weight for name in names}

    def portfolio_target(event: MarketEvent) -> float:
        return sum(
            normalized_weights[name] * strategy_target_qty_fns[name](event)
            for name in names
        )

    return simulate_realistic_execution(
        events,
        symbol=symbol,
        target_qty_fn=portfolio_target,
        config=config,
        order_id_prefix="portfolio",
    )
