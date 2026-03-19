from __future__ import annotations

from dataclasses import dataclass

from cryptoquant.aggregation import Bar
from cryptoquant.indicators import IndicatorContext, IndicatorPlugin
from cryptoquant.reporting import BacktestReport


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: list[float]
    report: BacktestReport


def run_sma_crossover_backtest(
    bars: list[Bar],
    indicator: IndicatorPlugin,
) -> BacktestResult:
    if not bars:
        report = BacktestReport(
            symbol="",
            timeframe="",
            bars=0,
            trades=0,
            total_return=0.0,
            max_drawdown=0.0,
        )
        return BacktestResult(equity_curve=[], report=report)

    values = indicator.compute(IndicatorContext(bars=bars))

    equity = 1.0
    peak = equity
    max_drawdown = 0.0
    pos = 0
    trades = 0
    curve: list[float] = [equity]

    for i in range(1, len(bars)):
        prev = bars[i - 1]
        cur = bars[i]
        signal = values[i - 1]

        next_pos = pos
        if signal is not None:
            next_pos = 1 if prev.close > signal else 0

        if next_pos != pos:
            trades += 1
            pos = next_pos

        ret = (cur.close / prev.close) - 1
        if pos == 1:
            equity *= 1 + ret
        curve.append(equity)

        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak else 0.0
        max_drawdown = max(max_drawdown, dd)

    report = BacktestReport(
        symbol=bars[0].symbol,
        timeframe=bars[0].timeframe,
        bars=len(bars),
        trades=trades,
        total_return=equity - 1,
        max_drawdown=max_drawdown,
    )
    return BacktestResult(equity_curve=curve, report=report)
