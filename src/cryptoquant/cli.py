from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from cryptoquant.backtest.simple import run_sma_crossover_backtest
from cryptoquant.data import BAR_V1_DICTIONARY, CsvBarDataSource
from cryptoquant.indicators import EMAIndicator, IndicatorRegistry, SMAIndicator
from cryptoquant.reporting import save_report_csv, save_report_json, save_report_markdown

try:
    from cryptoquant.reporting import save_equity_curve_csv
except ImportError:  # backward compatibility for minimal reporting module
    def save_equity_curve_csv(equity_curve: list[float], path: Path) -> None:
        import csv

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["index", "equity"])
            writer.writeheader()
            for idx, equity in enumerate(equity_curve):
                writer.writerow({"index": idx, "equity": equity})


def build_registry() -> IndicatorRegistry:
    registry = IndicatorRegistry()
    registry.register(SMAIndicator())
    registry.register(EMAIndicator())
    return registry


def parse_indicator(raw: str):
    # 格式: sma:window=20
    name, _, params_raw = raw.partition(":")
    params: dict[str, str] = {}
    if params_raw:
        for kv in params_raw.split(","):
            if not kv:
                continue
            k, _, v = kv.partition("=")
            params[k.strip()] = v.strip()
    return name, params


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cryptoquant")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ind = sub.add_parser("indicators", help="List available indicators")
    p_ind.set_defaults(func=cmd_indicators)

    p_ds = sub.add_parser("datasources", help="List available historical data sources")
    p_ds.set_defaults(func=cmd_datasources)

    p_run = sub.add_parser("backtest", help="Run historical backtest")
    p_run.add_argument("--csv", required=True)
    p_run.add_argument("--symbol", required=True)
    p_run.add_argument("--timeframe", default="1m")
    p_run.add_argument("--start")
    p_run.add_argument("--end")
    p_run.add_argument("--indicator", default="sma:window=14")
    p_run.add_argument("--out-dir", default="out")
    p_run.add_argument(
        "--report-formats",
        default="json,csv,md",
        help="comma separated: json,csv,md",
    )
    p_run.add_argument(
        "--export-equity-csv",
        action="store_true",
        help="export equity curve to equity_curve.csv",
    )
    p_run.set_defaults(func=cmd_backtest)

    args = parser.parse_args(argv)
    return args.func(args)


def cmd_indicators(_: argparse.Namespace) -> int:
    for name in build_registry().list_names():
        print(name)
    return 0


def cmd_datasources(_: argparse.Namespace) -> int:
    print("csv")
    print(f"  schema={BAR_V1_DICTIONARY.schema_name}")
    print(f"  version={BAR_V1_DICTIONARY.schema_version}")
    print("  quality_check=enabled(default)")
    print("  versioning=file-manifest(optional)")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    registry = build_registry()
    name, params = parse_indicator(args.indicator)
    plugin = registry.create(name, **params)

    start = datetime.fromisoformat(args.start) if args.start else None
    end = datetime.fromisoformat(args.end) if args.end else None

    source = CsvBarDataSource(path=Path(args.csv))
    bars = source.fetch_bars(symbol=args.symbol, timeframe=args.timeframe, start=start, end=end)
    result = run_sma_crossover_backtest(bars, plugin)

    out_dir = Path(args.out_dir)
    formats = {f.strip().lower() for f in args.report_formats.split(",") if f.strip()}
    if "json" in formats:
        save_report_json(result.report, out_dir / "report.json")
    if "csv" in formats:
        save_report_csv(result.report, out_dir / "report.csv")
    if "md" in formats:
        save_report_markdown(result.report, out_dir / "report.md")

    if args.export_equity_csv:
        save_equity_curve_csv(result.equity_curve, out_dir / "equity_curve.csv")

    sharpe = getattr(result.report, "sharpe_ratio", 0.0)
    print(
        "backtest done: "
        f"return={result.report.total_return:.4f}, "
        f"sharpe={sharpe:.4f}, "
        f"trades={result.report.trades}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
