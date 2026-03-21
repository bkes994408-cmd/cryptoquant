from datetime import datetime, timedelta

import pytest

from cryptoquant.backtest import (
    ExecutionModelConfig,
    RegimeScenario,
    run_multi_asset_multi_strategy_backtest,
    run_multi_strategy_portfolio_backtest,
    run_regime_scenarios,
    simulate_realistic_execution,
)
from cryptoquant.events.market import MarketEvent


def _events(symbol: str = "BTCUSDT") -> list[MarketEvent]:
    start = datetime(2024, 1, 1)
    closes = [100.0, 101.0, 102.0, 104.0, 103.0, 105.0]
    return [
        MarketEvent(symbol=symbol, timeframe="1m", close=close, ts=start + timedelta(minutes=idx))
        for idx, close in enumerate(closes)
    ]


def _multi_symbol_events() -> list[MarketEvent]:
    start = datetime(2024, 1, 1)
    btc = [100.0, 101.0, 102.0, 104.0, 103.0, 105.0]
    eth = [50.0, 49.0, 48.5, 49.5, 50.5, 51.0]
    events: list[MarketEvent] = []
    for idx in range(len(btc)):
        ts = start + timedelta(minutes=idx)
        events.append(MarketEvent(symbol="BTCUSDT", timeframe="1m", close=btc[idx], ts=ts))
        events.append(MarketEvent(symbol="ETHUSDT", timeframe="1m", close=eth[idx], ts=ts))
    return events


def test_simulate_realistic_execution_supports_latency_slippage_fee() -> None:
    result = simulate_realistic_execution(
        _events(),
        symbol="BTCUSDT",
        target_qty_fn=lambda event: 1.0 if event.close >= 102.0 else 0.0,
        config=ExecutionModelConfig(initial_equity=10_000.0, fee_bps=10.0, slippage_bps=20.0, latency_bars=1),
    )

    assert len(result.fills) >= 1
    fill = result.fills[0]
    # latency=1 => 訊號在 close=102 生成，下一根 bar 才會開始嘗試成交
    assert round(fill.requested_price, 6) in (104.0, 103.0, 105.0)
    assert result.total_fee > 0
    assert result.total_slippage_cost > 0
    assert len(result.equity_curve) == len(_events())


def test_run_regime_scenarios_applies_cost_multipliers() -> None:
    base = ExecutionModelConfig(
        initial_equity=10_000.0,
        fee_bps=5.0,
        slippage_bps=5.0,
        latency_bars=0,
        latency_seconds=30,
    )
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
    final_position = result.symbol_positions["BTCUSDT"]
    assert 0.3 <= final_position <= 0.7


def test_simulate_realistic_execution_supports_time_based_latency() -> None:
    result = simulate_realistic_execution(
        _events(),
        symbol="BTCUSDT",
        target_qty_fn=lambda event: 1.0 if event.close >= 102.0 else 0.0,
        config=ExecutionModelConfig(
            initial_equity=10_000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
            latency_bars=0,
            latency_seconds=120,
        ),
    )

    assert len(result.fills) >= 1
    fill = result.fills[0]
    # 訊號在 close=102 生成，延遲 120s 後應在後續 bar 成交
    assert fill.requested_price in {103.0, 104.0, 105.0}


def test_run_regime_scenarios_rejects_invalid_scenario_multipliers() -> None:
    with pytest.raises(ValueError, match="scenario multiplier"):
        run_regime_scenarios(
            _events(),
            symbol="BTCUSDT",
            target_qty_fn=lambda event: 0.0,
            scenarios=[RegimeScenario(name="bad", slippage_multiplier=-1.0)],
        )


def test_multi_asset_multi_strategy_portfolio_level_backtest() -> None:
    events = _multi_symbol_events()
    result = run_multi_asset_multi_strategy_backtest(
        events,
        strategy_target_qty_fns={
            "BTCUSDT": {
                "trend": lambda event: 1.0 if event.close >= 102 else 0.0,
                "mr": lambda event: -0.4 if event.close >= 104 else 0.0,
            },
            "ETHUSDT": {
                "trend": lambda event: 1.2 if event.close <= 49 else 0.0,
                "mr": lambda event: -0.5 if event.close >= 50.5 else 0.0,
            },
        },
        strategy_weights={"trend": 0.6, "mr": 0.4},
        symbol_weights={"BTCUSDT": 1.0, "ETHUSDT": 0.8},
        config=ExecutionModelConfig(fee_bps=3.0, slippage_bps=2.0, initial_equity=20_000.0),
    )
    assert len(result.equity_curve) == len(events)
    assert set(result.symbol_positions) == {"BTCUSDT", "ETHUSDT"}


def test_maker_taker_fee_difference_applies() -> None:
    events = _events()
    maker_only = simulate_realistic_execution(
        events,
        symbol="BTCUSDT",
        target_qty_fn=lambda event: 1.0 if event.close >= 102 else 0.0,
        config=ExecutionModelConfig(
            maker_fee_bps=1.0,
            taker_fee_bps=10.0,
            maker_probability=1.0,
            initial_equity=10_000.0,
        ),
    )
    taker_only = simulate_realistic_execution(
        events,
        symbol="BTCUSDT",
        target_qty_fn=lambda event: 1.0 if event.close >= 102 else 0.0,
        config=ExecutionModelConfig(
            maker_fee_bps=1.0,
            taker_fee_bps=10.0,
            maker_probability=0.0,
            initial_equity=10_000.0,
        ),
    )
    assert taker_only.total_fee > maker_only.total_fee


def test_partial_fill_and_queue_delay_exposes_remaining_orders() -> None:
    result = simulate_realistic_execution(
        _events(),
        symbol="BTCUSDT",
        target_qty_fn=lambda event: 3.0 if event.close >= 102 else 0.0,
        config=ExecutionModelConfig(
            initial_equity=30_000.0,
            base_fill_ratio=0.3,
            queue_ahead_notional=200_000.0,
            default_depth_notional=50_000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
        ),
    )
    # 分批成交 => fills 會超過 1 筆，且最終部位尚未必達滿倉
    assert len(result.fills) >= 2
    assert 0 < result.symbol_positions["BTCUSDT"] < 3.0


def test_cancel_reject_probability_keeps_stale_order() -> None:
    events = _events()
    result = simulate_realistic_execution(
        events,
        symbol="BTCUSDT",
        target_qty_fn=lambda event: 1.0 if event.close in (102.0, 103.0) else 0.0,
        config=ExecutionModelConfig(
            initial_equity=10_000.0,
            latency_bars=2,
            cancel_reject_probability=1.0,
            fee_bps=0.0,
            slippage_bps=0.0,
        ),
    )
    # 必然存在撤單失敗導致殘留單成交
    assert len(result.fills) >= 1


def test_funding_and_liquidation_logic() -> None:
    start = datetime(2024, 1, 1)
    events = [
        MarketEvent(symbol="BTCUSDT", timeframe="1m", close=100.0, ts=start),
        MarketEvent(symbol="BTCUSDT", timeframe="1m", close=80.0, ts=start + timedelta(minutes=1)),
        MarketEvent(symbol="BTCUSDT", timeframe="1m", close=60.0, ts=start + timedelta(minutes=2)),
    ]
    result = simulate_realistic_execution(
        events,
        symbol="BTCUSDT",
        target_qty_fn=lambda _: 20.0,
        config=ExecutionModelConfig(
            initial_equity=1_000.0,
            leverage=1.1,
            maintenance_margin_rate=0.4,
            funding_rate_per_bar=0.001,
            base_fill_ratio=1.0,
            default_depth_notional=1_000_000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
        ),
    )

    assert result.funding_cost > 0
    assert result.liquidation_count >= 1


def test_regime_split_tracks_regime_pnl() -> None:
    events = _events()
    result = run_multi_asset_multi_strategy_backtest(
        events,
        strategy_target_qty_fns={"BTCUSDT": {"trend": lambda event: 1.0 if event.close >= 102 else 0.0}},
        regime_fn=lambda event: "risk_on" if event.close >= 103 else "risk_off",
        config=ExecutionModelConfig(initial_equity=10_000.0, fee_bps=0.0, slippage_bps=0.0),
    )
    assert "risk_on" in result.regime_equity_delta
    assert "risk_off" in result.regime_equity_delta
