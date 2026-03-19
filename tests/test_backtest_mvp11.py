from datetime import datetime, timedelta

from cryptoquant.backtest import (
    ExecutionModelConfig,
    RegimeScenario,
    run_multi_strategy_portfolio_backtest,
    run_regime_scenarios,
    simulate_realistic_execution,
)
from cryptoquant.events.market import MarketEvent


def _events() -> list[MarketEvent]:
    start = datetime(2024, 1, 1)
    closes = [100.0, 101.0, 102.0, 104.0, 103.0, 105.0]
    return [
        MarketEvent(symbol="BTCUSDT", timeframe="1m", close=close, ts=start + timedelta(minutes=idx))
        for idx, close in enumerate(closes)
    ]


def test_simulate_realistic_execution_supports_latency_slippage_fee() -> None:
    result = simulate_realistic_execution(
        _events(),
        symbol="BTCUSDT",
        target_qty_fn=lambda event: 1.0 if event.close >= 102.0 else 0.0,
        config=ExecutionModelConfig(initial_equity=10_000.0, fee_bps=10.0, slippage_bps=20.0, latency_bars=1),
    )

    assert len(result.fills) == 1
    fill = result.fills[0]
    # latency=1 => 訊號在 close=102 生成，下一根 close=104 成交
    assert round(fill.requested_price, 6) == 104.0
    assert round(fill.fill_price, 6) == 104.208
    assert result.total_fee > 0
    assert result.total_slippage_cost > 0
    assert len(result.equity_curve) == len(_events())


def test_run_regime_scenarios_applies_cost_multipliers() -> None:
    base = ExecutionModelConfig(initial_equity=10_000.0, fee_bps=5.0, slippage_bps=5.0, latency_bars=0)
    scenarios = [
        RegimeScenario(name="normal", slippage_multiplier=1.0, fee_multiplier=1.0),
        RegimeScenario(name="stress", slippage_multiplier=4.0, fee_multiplier=2.0, latency_bars=1),
    ]

    results = run_regime_scenarios(
        _events(),
        symbol="BTCUSDT",
        target_qty_fn=lambda event: 1.0 if event.close >= 102.0 else 0.0,
        scenarios=scenarios,
        base_config=base,
    )

    assert len(results) == 2
    normal = next(item for item in results if item.scenario.name == "normal")
    stress = next(item for item in results if item.scenario.name == "stress")
    assert stress.result.total_fee >= normal.result.total_fee
    assert stress.result.total_slippage_cost >= normal.result.total_slippage_cost


def test_multi_strategy_portfolio_backtest_uses_weighted_targets() -> None:
    events = _events()
    result = run_multi_strategy_portfolio_backtest(
        events,
        symbol="BTCUSDT",
        strategy_target_qty_fns={
            "trend": lambda event: 1.0 if event.close >= 102.0 else 0.0,
            "mean_revert": lambda event: -0.5 if event.close >= 104.0 else 0.0,
        },
        weights={"trend": 0.75, "mean_revert": 0.25},
        config=ExecutionModelConfig(initial_equity=10_000.0, fee_bps=0.0, slippage_bps=0.0),
    )

    assert len(result.fills) >= 1
    # 在 close=104 起，組合目標 = 0.75*1 + 0.25*(-0.5) = 0.625
    final_position = sum(fill.qty for fill in result.fills)
    assert round(final_position, 6) == 0.625
