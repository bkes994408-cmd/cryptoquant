from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from random import Random
from typing import Callable, Mapping, Sequence

from cryptoquant.events.market import MarketEvent
from cryptoquant.execution import Fill


@dataclass(frozen=True)
class ExecutionModelConfig:
    fee_bps: float = 4.0
    slippage_bps: float = 2.0
    latency_bars: int = 0
    latency_seconds: int = 0
    initial_equity: float = 10_000.0

    # MVP-11 realism upgrades
    maker_fee_bps: float | None = None
    taker_fee_bps: float | None = None
    maker_probability: float = 0.35
    base_fill_ratio: float = 0.75
    queue_ahead_notional: float = 0.0
    cancel_reject_probability: float = 0.0
    default_depth_notional: float = 100_000.0
    impact_bps: float = 8.0
    liquidity_shortage_bps: float = 20.0
    leverage: float = 3.0
    maintenance_margin_rate: float = 0.2
    funding_rate_per_bar: float = 0.0
    liquidation_penalty_bps: float = 10.0
    random_seed: int = 11


@dataclass(frozen=True)
class RealisticBacktestResult:
    fills: list[Fill]
    equity_curve: list[float]
    final_equity: float
    total_fee: float
    total_slippage_cost: float
    funding_cost: float = 0.0
    liquidation_count: int = 0
    regime_equity_delta: Mapping[str, float] = field(default_factory=dict)
    symbol_positions: Mapping[str, float] = field(default_factory=dict)


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


@dataclass
class _PendingOrder:
    execute_idx: int
    sequence: int
    symbol: str
    qty: float
    requested_price: float
    ts: object
    strategy: str


def _validate_config(config: ExecutionModelConfig) -> None:
    if config.initial_equity <= 0:
        raise ValueError("initial_equity must be > 0")
    if config.latency_bars < 0:
        raise ValueError("latency_bars must be >= 0")
    if config.latency_seconds < 0:
        raise ValueError("latency_seconds must be >= 0")
    if not 0 <= config.maker_probability <= 1:
        raise ValueError("maker_probability must be in [0, 1]")
    if not 0 < config.base_fill_ratio <= 1:
        raise ValueError("base_fill_ratio must be in (0, 1]")
    if not 0 <= config.cancel_reject_probability <= 1:
        raise ValueError("cancel_reject_probability must be in [0, 1]")
    if config.default_depth_notional <= 0:
        raise ValueError("default_depth_notional must be > 0")
    if config.leverage <= 0:
        raise ValueError("leverage must be > 0")


def _fee_rate(config: ExecutionModelConfig, *, is_maker: bool) -> float:
    maker_bps = config.fee_bps if config.maker_fee_bps is None else config.maker_fee_bps
    taker_bps = config.fee_bps if config.taker_fee_bps is None else config.taker_fee_bps
    return (maker_bps if is_maker else taker_bps) / 10_000


def _resolve_execute_idx(events: Sequence[MarketEvent], signal_idx: int, config: ExecutionModelConfig) -> int:
    by_bars = min(signal_idx + config.latency_bars, len(events) - 1)
    if config.latency_seconds == 0:
        return by_bars

    target_ts = events[signal_idx].ts + timedelta(seconds=config.latency_seconds)
    by_time = len(events) - 1
    for future_idx in range(signal_idx, len(events)):
        if events[future_idx].ts >= target_ts:
            by_time = future_idx
            break
    return max(by_bars, by_time)


def _equity(cash: float, positions: Mapping[str, float], prices: Mapping[str, float]) -> float:
    return cash + sum(positions.get(sym, 0.0) * prices[sym] for sym in prices)


def _gross_notional(positions: Mapping[str, float], prices: Mapping[str, float]) -> float:
    return sum(abs(positions.get(sym, 0.0) * prices[sym]) for sym in prices)


def run_multi_asset_multi_strategy_backtest(
    events: Sequence[MarketEvent],
    *,
    strategy_target_qty_fns: Mapping[str, Mapping[str, Callable[[MarketEvent], float]]],
    strategy_weights: Mapping[str, float] | None = None,
    symbol_weights: Mapping[str, float] | None = None,
    regime_fn: Callable[[MarketEvent], str] | None = None,
    config: ExecutionModelConfig = ExecutionModelConfig(),
) -> RealisticBacktestResult:
    _validate_config(config)
    if not events:
        raise ValueError("events is empty")
    if not strategy_target_qty_fns:
        raise ValueError("at least one symbol with strategy is required")

    rng = Random(config.random_seed)
    ordered = sorted(events, key=lambda event: event.ts)
    symbols = sorted(strategy_target_qty_fns.keys())
    if any(symbol not in {event.symbol for event in ordered} for symbol in symbols):
        raise ValueError("some configured symbols have no events")

    strategy_names = sorted({name for m in strategy_target_qty_fns.values() for name in m})
    if not strategy_names:
        raise ValueError("at least one strategy is required")

    if strategy_weights is None:
        norm_strategy_weights = {name: 1.0 / len(strategy_names) for name in strategy_names}
    else:
        if set(strategy_weights) != set(strategy_names):
            raise ValueError("strategy_weights keys must match strategy names")
        total = sum(float(strategy_weights[name]) for name in strategy_names)
        if total <= 0:
            raise ValueError("strategy_weights sum must be > 0")
        norm_strategy_weights = {name: float(strategy_weights[name]) / total for name in strategy_names}

    if symbol_weights is None:
        norm_symbol_weights = {symbol: 1.0 for symbol in symbols}
    else:
        if set(symbol_weights) != set(symbols):
            raise ValueError("symbol_weights keys must match configured symbols")
        norm_symbol_weights = {symbol: float(symbol_weights[symbol]) for symbol in symbols}

    symbol_events: dict[str, list[MarketEvent]] = {symbol: [] for symbol in symbols}
    for event in ordered:
        if event.symbol in symbol_events:
            symbol_events[event.symbol].append(event)

    cash = config.initial_equity
    fills: list[Fill] = []
    positions: dict[str, float] = {symbol: 0.0 for symbol in symbols}
    last_price: dict[str, float] = {symbol: symbol_events[symbol][0].close for symbol in symbols}
    equity_curve: list[float] = []
    pending: list[_PendingOrder] = []
    symbol_targets: dict[str, float] = {symbol: 0.0 for symbol in symbols}
    sequence = 0
    regime_equity_delta: dict[str, float] = {}
    funding_cost = 0.0
    liquidation_count = 0

    event_index: dict[tuple[str, object], int] = {}
    for symbol, seq in symbol_events.items():
        for idx, event in enumerate(seq):
            event_index[(symbol, event.ts)] = idx

    for event in ordered:
        last_price[event.symbol] = event.close

        # process matured orders (partial fill + queue + liquidity effects)
        symbol_seq = symbol_events[event.symbol]
        idx = event_index[(event.symbol, event.ts)]
        matured = [order for order in pending if order.symbol == event.symbol and order.execute_idx <= idx]
        if matured:
            kept: list[_PendingOrder] = []
            for order in pending:
                if order not in matured:
                    kept.append(order)
            pending = kept

            for order in matured:
                remaining = order.qty
                if remaining == 0:
                    continue

                is_maker = rng.random() < config.maker_probability
                fee_rate = _fee_rate(config, is_maker=is_maker)

                qty_abs = abs(remaining)
                depth_qty = max(config.default_depth_notional / max(event.close, 1e-9), 1e-9)
                queue_qty = max(config.queue_ahead_notional / max(event.close, 1e-9), 0.0)
                queue_factor = depth_qty / (depth_qty + queue_qty) if (depth_qty + queue_qty) > 0 else 1.0
                fill_ratio = min(1.0, config.base_fill_ratio * queue_factor * (depth_qty / max(qty_abs, depth_qty)))
                filled_qty = abs(remaining) * fill_ratio
                if filled_qty <= 0:
                    pending.append(order)
                    continue

                signed_fill_qty = filled_qty if remaining > 0 else -filled_qty
                impact = config.impact_bps * min(2.0, qty_abs / depth_qty)
                shortage = config.liquidity_shortage_bps if qty_abs > depth_qty else 0.0
                slippage_bps = config.slippage_bps + impact + shortage
                slippage_rate = slippage_bps / 10_000
                side = 1.0 if signed_fill_qty > 0 else -1.0
                fill_price = event.close * (1.0 + side * slippage_rate)
                notional = abs(signed_fill_qty) * fill_price
                fee = notional * fee_rate
                slippage_cost = abs(signed_fill_qty) * abs(fill_price - event.close)

                fills.append(
                    Fill(
                        client_order_id=f"mvp11-{order.sequence}",
                        symbol=order.symbol,
                        qty=signed_fill_qty,
                        requested_price=event.close,
                        fill_price=fill_price,
                        slippage_cost=slippage_cost,
                        fee=fee,
                        notional=notional,
                        ts=event.ts,
                    )
                )

                positions[order.symbol] = positions.get(order.symbol, 0.0) + signed_fill_qty
                cash -= signed_fill_qty * fill_price
                cash -= fee

                residual = remaining - signed_fill_qty
                if abs(residual) > 1e-12:
                    pending.append(
                        _PendingOrder(
                            execute_idx=min(idx + 1, len(symbol_seq) - 1),
                            sequence=order.sequence,
                            symbol=order.symbol,
                            qty=residual,
                            requested_price=event.close,
                            ts=event.ts,
                            strategy=order.strategy,
                        )
                    )

        # generate portfolio-level target for this event.symbol
        weighted_sum = 0.0
        for strategy_name, strategy_fn in strategy_target_qty_fns[event.symbol].items():
            weighted_sum += norm_strategy_weights[strategy_name] * strategy_fn(event)
        target_qty = weighted_sum * norm_symbol_weights[event.symbol]

        delta_qty = target_qty - symbol_targets[event.symbol]
        if abs(delta_qty) > 1e-12:
            # try cancel stale pending orders when target changes, allow cancel rejection simulation
            stale_orders = [o for o in pending if o.symbol == event.symbol and (o.qty * delta_qty) < 0]
            for stale in stale_orders:
                if rng.random() >= config.cancel_reject_probability:
                    pending.remove(stale)
                # else: cancel reject -> stale order keeps hanging

            execute_idx = _resolve_execute_idx(symbol_events[event.symbol], idx, config)
            pending.append(
                _PendingOrder(
                    execute_idx=execute_idx,
                    sequence=sequence,
                    symbol=event.symbol,
                    qty=delta_qty,
                    requested_price=event.close,
                    ts=event.ts,
                    strategy="portfolio",
                )
            )
            sequence += 1
            symbol_targets[event.symbol] += delta_qty

        # funding cost (portfolio level)
        bar_funding = sum(abs(positions[sym] * last_price[sym]) * config.funding_rate_per_bar for sym in symbols)
        cash -= bar_funding
        funding_cost += bar_funding

        current_equity = _equity(cash, positions, last_price)

        # liquidation check
        gross = _gross_notional(positions, last_price)
        max_notional = max(current_equity, 1e-9) * config.leverage
        maint_floor = gross * config.maintenance_margin_rate
        if gross > max_notional or current_equity <= maint_floor:
            liquidation_count += 1
            for symbol in symbols:
                qty = positions.get(symbol, 0.0)
                if abs(qty) <= 1e-12:
                    continue
                side = -1.0 if qty > 0 else 1.0
                penalty_rate = config.liquidation_penalty_bps / 10_000
                px = last_price[symbol] * (1.0 + side * penalty_rate)
                notional = abs(qty) * px
                fee = notional * _fee_rate(config, is_maker=False)
                fills.append(
                    Fill(
                        client_order_id=f"liq-{sequence}-{symbol}",
                        symbol=symbol,
                        qty=-qty,
                        requested_price=last_price[symbol],
                        fill_price=px,
                        slippage_cost=abs(qty) * abs(px - last_price[symbol]),
                        fee=fee,
                        notional=notional,
                        ts=event.ts,
                    )
                )
                cash -= (-qty) * px
                cash -= fee
                positions[symbol] = 0.0
                sequence += 1
            current_equity = _equity(cash, positions, last_price)

        equity_curve.append(current_equity)

        if regime_fn is not None:
            regime = regime_fn(event)
            regime_equity_delta[regime] = regime_equity_delta.get(regime, 0.0)
            if len(equity_curve) > 1:
                regime_equity_delta[regime] += equity_curve[-1] - equity_curve[-2]

    total_fee = sum(fill.fee for fill in fills)
    total_slippage_cost = sum(fill.slippage_cost for fill in fills)
    return RealisticBacktestResult(
        fills=fills,
        equity_curve=equity_curve,
        final_equity=equity_curve[-1],
        total_fee=total_fee,
        total_slippage_cost=total_slippage_cost,
        funding_cost=funding_cost,
        liquidation_count=liquidation_count,
        regime_equity_delta=regime_equity_delta,
        symbol_positions=dict(positions),
    )


def simulate_realistic_execution(
    events: Sequence[MarketEvent],
    *,
    symbol: str,
    target_qty_fn: Callable[[MarketEvent], float],
    config: ExecutionModelConfig = ExecutionModelConfig(),
    order_id_prefix: str = "mvp11",
) -> RealisticBacktestResult:
    del order_id_prefix
    return run_multi_asset_multi_strategy_backtest(
        events,
        strategy_target_qty_fns={symbol: {"default": target_qty_fn}},
        config=config,
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
        if scenario.fee_multiplier < 0 or scenario.slippage_multiplier < 0:
            raise ValueError("scenario multiplier must be >= 0")
        if scenario.latency_bars is not None and scenario.latency_bars < 0:
            raise ValueError("scenario latency_bars must be >= 0")

        scenario_config = ExecutionModelConfig(
            fee_bps=base_config.fee_bps * scenario.fee_multiplier,
            slippage_bps=base_config.slippage_bps * scenario.slippage_multiplier,
            latency_bars=base_config.latency_bars if scenario.latency_bars is None else scenario.latency_bars,
            latency_seconds=base_config.latency_seconds,
            initial_equity=base_config.initial_equity,
            maker_fee_bps=base_config.maker_fee_bps,
            taker_fee_bps=base_config.taker_fee_bps,
            maker_probability=base_config.maker_probability,
            base_fill_ratio=base_config.base_fill_ratio,
            queue_ahead_notional=base_config.queue_ahead_notional,
            cancel_reject_probability=base_config.cancel_reject_probability,
            default_depth_notional=base_config.default_depth_notional,
            impact_bps=base_config.impact_bps,
            liquidity_shortage_bps=base_config.liquidity_shortage_bps,
            leverage=base_config.leverage,
            maintenance_margin_rate=base_config.maintenance_margin_rate,
            funding_rate_per_bar=base_config.funding_rate_per_bar,
            liquidation_penalty_bps=base_config.liquidation_penalty_bps,
            random_seed=base_config.random_seed,
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

    return run_multi_asset_multi_strategy_backtest(
        events,
        strategy_target_qty_fns={symbol: strategy_target_qty_fns},
        strategy_weights=normalized_weights,
        config=config,
    )
