from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptoquant.cli import main


def test_cli_backtest_generates_reports(tmp_path) -> None:
    csv_file = tmp_path / "bars.csv"
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)
    rows = ["symbol,timeframe,ts,open,high,low,close,volume"]
    for i in range(20):
        ts = (base + timedelta(minutes=i)).isoformat()
        px = 100 + i
        rows.append(f"BTCUSDT,1m,{ts},{px},{px+1},{px-1},{px},1")
    csv_file.write_text("\n".join(rows), encoding="utf-8")

    code = main(
        [
            "backtest",
            "--csv",
            str(csv_file),
            "--symbol",
            "BTCUSDT",
            "--timeframe",
            "1m",
            "--indicator",
            "sma:window=5",
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )

    assert code == 0
    assert (tmp_path / "out" / "report.json").exists()
    assert (tmp_path / "out" / "report.csv").exists()
    assert (tmp_path / "out" / "report.md").exists()
