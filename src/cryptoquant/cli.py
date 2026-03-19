from __future__ import annotations

import argparse
from pathlib import Path

from cryptoquant.backtest import run_sma_crossover_backtest
from cryptoquant.data import CsvBarDataSource
from cryptoquant.indicators import EMAIndicator, IndicatorRegistry, SMAIndicator
from cryptoquant.reporting import save_report_csv, save_report_json, save_report_markdown


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

    p_run = sub.add_parser("backtest", help="Run historical backtest")
    p_run.add_argument("--csv", required=True)
    p_run.add_argument("--symbol", required=True)
    p_run.add_argument("--timeframe", default="1m")
    p_run.add_argument("--indicator", default="sma:window=14")
    p_run.add_argument("--out-dir", default="out")
    p_run.set_defaults(func=cmd_backtest)

    args = parser.parse_args(argv)
    return args.func(args)


def cmd_indicators(_: argparse.Namespace) -> int:
    for name in build_registry().list_names():
        print(name)
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    registry = build_registry()
    name, params = parse_indicator(args.indicator)

    plugin = registry.get(name)
    if "window" in params:
        window = int(params["window"])
        plugin = type(plugin)(window=window)

    source = CsvBarDataSource(path=Path(args.csv))
    bars = source.fetch_bars(symbol=args.symbol, timeframe=args.timeframe)
    result = run_sma_crossover_backtest(bars, plugin)

    out_dir = Path(args.out_dir)
    save_report_json(result.report, out_dir / "report.json")
    save_report_csv(result.report, out_dir / "report.csv")
    save_report_markdown(result.report, out_dir / "report.md")

    print(f"backtest done: return={result.report.total_return:.4f}, trades={result.report.trades}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
