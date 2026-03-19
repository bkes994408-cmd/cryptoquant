from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

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
    active_returns: list[float] = []

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
            active_returns.append(ret)
        curve.append(equity)

        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak else 0.0
        max_drawdown = max(max_drawdown, dd)

    annualized_return = _annualized_return(total_return=equity - 1, bars=len(bars), timeframe=bars[0].timeframe)
    sharpe_ratio = _sharpe_ratio(active_returns, bars[0].timeframe)
    win_rate = _win_rate(active_returns)

    report = BacktestReport(
        symbol=bars[0].symbol,
        timeframe=bars[0].timeframe,
        bars=len(bars),
        trades=trades,
        total_return=equity - 1,
        annualized_return=annualized_return,
        sharpe_ratio=sharpe_ratio,
        win_rate=win_rate,
        final_equity=equity,
        max_drawdown=max_drawdown,
    )
    return BacktestResult(equity_curve=curve, report=report)


def _annualized_return(*, total_return: float, bars: int, timeframe: str) -> float:
    if bars <= 1:
        return 0.0
    minutes = _timeframe_to_minutes(timeframe)
    periods_per_year = int((365 * 24 * 60) / minutes)
    years = bars / periods_per_year
    if years <= 0 or years < (1 / 12):
        return 0.0
    return (1 + total_return) ** (1 / years) - 1


def _sharpe_ratio(returns: list[float], timeframe: str) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = sqrt(var)
    if std == 0:
        return 0.0

    minutes = _timeframe_to_minutes(timeframe)
    periods_per_year = int((365 * 24 * 60) / minutes)
    return (mean / std) * sqrt(periods_per_year)


def _win_rate(returns: list[float]) -> float:
    if not returns:
        return 0.0
    wins = sum(1 for r in returns if r > 0)
    return wins / len(returns)


def _timeframe_to_minutes(timeframe: str) -> int:
    unit = timeframe[-1].lower()
    value = int(timeframe[:-1] or "1")
    if unit == "m":
        return value
    if unit == "h":
        return value * 60
    if unit == "d":
        return value * 24 * 60
    raise ValueError(f"unsupported timeframe: {timeframe}")
