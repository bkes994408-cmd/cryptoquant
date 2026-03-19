from __future__ import annotations

from dataclasses import dataclass

from .core import IndicatorContext


@dataclass(frozen=True)
class SMAIndicator:
    window: int = 14
    name: str = "sma"

    def compute(self, ctx: IndicatorContext) -> list[float | None]:
        if self.window <= 0:
            raise ValueError("window must be > 0")
        closes = [b.close for b in ctx.bars]
        out: list[float | None] = []
        acc = 0.0
        for i, value in enumerate(closes):
            acc += value
            if i >= self.window:
                acc -= closes[i - self.window]
            if i + 1 < self.window:
                out.append(None)
            else:
                out.append(acc / self.window)
        return out


@dataclass(frozen=True)
class EMAIndicator:
    window: int = 14
    name: str = "ema"

    def compute(self, ctx: IndicatorContext) -> list[float | None]:
        if self.window <= 0:
            raise ValueError("window must be > 0")
        closes = [b.close for b in ctx.bars]
        if not closes:
            return []

        alpha = 2 / (self.window + 1)
        out: list[float | None] = []
        ema: float | None = None
        for px in closes:
            if ema is None:
                ema = px
            else:
                ema = (px * alpha) + (ema * (1 - alpha))
            out.append(ema)
        return out
