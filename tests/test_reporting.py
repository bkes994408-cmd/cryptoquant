from __future__ import annotations

import json

from cryptoquant.reporting import (
    BacktestReport,
    save_drawdown_curve_csv,
    save_equity_curve_csv,
    save_report_csv,
    save_report_json,
    save_report_markdown,
)


def test_report_exporters(tmp_path) -> None:
    report = BacktestReport(
        symbol="BTCUSDT",
        timeframe="1m",
        bars=100,
        trades=5,
        total_return=0.12,
        max_drawdown=0.05,
        annualized_return=0.13,
        sharpe_ratio=1.2,
        win_rate=0.56,
        final_equity=1.12,
    )

    save_report_json(report, tmp_path / "report.json")
    save_report_csv(report, tmp_path / "report.csv")
    save_report_markdown(report, tmp_path / "report.md")
    save_equity_curve_csv([1.0, 1.02, 1.01], tmp_path / "equity_curve.csv")
    save_drawdown_curve_csv([0.0, 0.0, 0.01], tmp_path / "drawdown_curve.csv")

    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["symbol"] == "BTCUSDT"
    assert payload["sharpe_ratio"] == 1.2
    assert (tmp_path / "report.csv").exists()
    assert "Backtest Report" in (tmp_path / "report.md").read_text(encoding="utf-8")
    assert (tmp_path / "equity_curve.csv").exists()
    assert (tmp_path / "drawdown_curve.csv").exists()
