from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import csv
import json


@dataclass(frozen=True)
class BacktestReport:
    symbol: str
    timeframe: str
    bars: int
    trades: int
    total_return: float
    max_drawdown: float

    def to_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


def save_report_json(report: BacktestReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def save_report_csv(report: BacktestReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(report.to_dict().keys()))
        writer.writeheader()
        writer.writerow(report.to_dict())


def save_report_markdown(report: BacktestReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Backtest Report",
        "",
        f"- Symbol: `{report.symbol}`",
        f"- Timeframe: `{report.timeframe}`",
        f"- Bars: `{report.bars}`",
        f"- Trades: `{report.trades}`",
        f"- Total Return: `{report.total_return:.4f}`",
        f"- Max Drawdown: `{report.max_drawdown:.4f}`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
