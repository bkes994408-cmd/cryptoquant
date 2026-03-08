from __future__ import annotations

from math import sqrt

from cryptoquant.aggregation import Bar


def sma(bars: list[Bar], window: int) -> list[float | None]:
    _validate_window(window)
    values = [b.close for b in bars]
    out: list[float | None] = [None] * len(values)
    rolling_sum = 0.0
    for i, v in enumerate(values):
        rolling_sum += v
        if i >= window:
            rolling_sum -= values[i - window]
        if i >= window - 1:
            out[i] = rolling_sum / window
    return out


def ema(bars: list[Bar], window: int) -> list[float | None]:
    _validate_window(window)
    values = [b.close for b in bars]
    out: list[float | None] = [None] * len(values)
    if len(values) < window:
        return out

    seed = sum(values[:window]) / window
    out[window - 1] = seed
    k = 2 / (window + 1)
    prev = seed
    for i in range(window, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(bars: list[Bar], window: int = 14) -> list[float | None]:
    _validate_window(window)
    values = [b.close for b in bars]
    out: list[float | None] = [None] * len(values)
    if len(values) <= window:
        return out

    gains = 0.0
    losses = 0.0
    for i in range(1, window + 1):
        delta = values[i] - values[i - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)

    avg_gain = gains / window
    avg_loss = losses / window
    out[window] = _rsi_from_avg(avg_gain, avg_loss)

    for i in range(window + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = ((avg_gain * (window - 1)) + gain) / window
        avg_loss = ((avg_loss * (window - 1)) + loss) / window
        out[i] = _rsi_from_avg(avg_gain, avg_loss)

    return out


def bollinger_bands(
    bars: list[Bar],
    *,
    window: int = 20,
    num_stddev: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    _validate_window(window)
    values = [b.close for b in bars]
    mid = sma(bars, window)
    upper: list[float | None] = [None] * len(values)
    lower: list[float | None] = [None] * len(values)

    for i in range(window - 1, len(values)):
        segment = values[i - window + 1 : i + 1]
        mean = mid[i] or 0.0
        variance = sum((x - mean) ** 2 for x in segment) / window
        std = sqrt(variance)
        upper[i] = mean + num_stddev * std
        lower[i] = mean - num_stddev * std

    return upper, mid, lower


def atr(bars: list[Bar], window: int = 14) -> list[float | None]:
    _validate_window(window)
    out: list[float | None] = [None] * len(bars)
    if len(bars) <= window:
        return out

    true_ranges: list[float] = []
    for i, bar in enumerate(bars):
        if i == 0:
            tr = bar.high - bar.low
        else:
            prev_close = bars[i - 1].close
            tr = max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))
        true_ranges.append(tr)

    first_atr = sum(true_ranges[1 : window + 1]) / window
    out[window] = first_atr
    prev = first_atr
    for i in range(window + 1, len(bars)):
        prev = ((prev * (window - 1)) + true_ranges[i]) / window
        out[i] = prev

    return out


def _rsi_from_avg(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _validate_window(window: int) -> None:
    if window <= 0:
        raise ValueError("window must be positive")
