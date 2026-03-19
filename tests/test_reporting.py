from __future__ import annotations

import json

from cryptoquant.reporting import BacktestReport, save_report_csv, save_report_json, save_report_markdown


def test_report_exporters(tmp_path) -> None:
    report = BacktestReport(
        symbol="BTCUSDT",
        timeframe="1m",
        bars=100,
        trades=5,
        total_return=0.12,
        max_drawdown=0.05,
    )

    save_report_json(report, tmp_path / "report.json")
    save_report_csv(report, tmp_path / "report.csv")
    save_report_markdown(report, tmp_path / "report.md")

    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["symbol"] == "BTCUSDT"
    assert (tmp_path / "report.csv").exists()
    assert "Backtest Report" in (tmp_path / "report.md").read_text(encoding="utf-8")
