"""Command-line interface: ``candlelab fetch | backtest | strategies``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from urllib.error import URLError

from candlelab import __version__
from candlelab.data import BINANCE_INTERVALS, DataError, fetch_binance_klines, load_csv, save_csv
from candlelab.engine import BacktestConfig, run_backtest
from candlelab.metrics import summarize
from candlelab.report import format_summary, write_equity_csv, write_trades_csv
from candlelab.strategies import (
    coerce_param,
    get_strategy,
    list_strategies,
    parameter_types,
    strategy_class,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="candlelab",
        description="A small, transparent backtesting lab for OHLCV candles.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="download spot candles from Binance public data")
    fetch.add_argument("symbol", help="trading pair, e.g. BTCUSDT")
    fetch.add_argument("--interval", default="1d", choices=list(BINANCE_INTERVALS))
    fetch.add_argument("--start", required=True, help="first candle open time, e.g. 2021-01-01")
    fetch.add_argument("--end", help="exclusive end time (default: now)")
    fetch.add_argument("-o", "--output", required=True, help="CSV file to write")
    fetch.add_argument("--pause", type=float, default=0.2, help="seconds between requests")

    bt = sub.add_parser("backtest", help="run a strategy over a CSV of candles")
    bt.add_argument("csv", help="candle CSV (time, open, high, low, close, volume)")
    bt.add_argument("-s", "--strategy", default="ma_cross", help="strategy name")
    bt.add_argument(
        "-p",
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="strategy parameter, repeatable (e.g. -p fast=20 -p slow=50)",
    )
    bt.add_argument("--cash", type=float, default=10_000.0, help="initial cash (quote currency)")
    bt.add_argument("--fee", type=float, default=0.001, help="fee rate per side (0.001 = 0.1%%)")
    bt.add_argument("--slippage", type=float, default=0.0, help="slippage fraction per fill")
    bt.add_argument("--start", help="only trade from this time (indicators still warm up)")
    bt.add_argument("--end", help="only trade until this time (inclusive)")
    bt.add_argument("--trades-out", help="write trades to this CSV")
    bt.add_argument("--equity-out", help="write the equity curve to this CSV")

    sub.add_parser("strategies", help="list available strategies and their parameters")
    return parser


def _parse_params(strategy: str, pairs: Sequence[str]) -> dict[str, object]:
    cls = strategy_class(strategy)
    params: dict[str, object] = {}
    for pair in pairs:
        key, sep, raw = pair.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"expected KEY=VALUE, got {pair!r}")
        params[key.strip()] = coerce_param(cls, key.strip(), raw.strip())
    return params


def _cmd_fetch(args: argparse.Namespace) -> int:
    candles = fetch_binance_klines(
        args.symbol, args.interval, args.start, args.end, pause=args.pause
    )
    path = save_csv(candles, args.output)
    span = f"{candles.index[0]:%Y-%m-%d %H:%M} -> {candles.index[-1]:%Y-%m-%d %H:%M}"
    print(f"wrote {len(candles)} candles ({span}) to {path}")
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    strategy = get_strategy(args.strategy, **_parse_params(args.strategy, args.param))
    config = BacktestConfig(initial_cash=args.cash, fee_rate=args.fee, slippage=args.slippage)
    candles = load_csv(args.csv)

    # Compute signals on the full history so indicators are warm when the window starts.
    target = strategy.target_position(candles)
    window = candles.loc[args.start : args.end]
    if len(window) < 2:
        raise ValueError("the selected --start/--end window has fewer than two candles")

    result = run_backtest(window, target.loc[window.index], config)
    summary = summarize(result, window)

    params = ", ".join(f"{k}={v}" for k, v in strategy.params().items())
    print(format_summary(summary, title=f"{strategy.name}({params})"))

    if args.trades_out:
        print(f"\ntrades -> {write_trades_csv(result, args.trades_out)}")
    if args.equity_out:
        print(f"equity -> {write_equity_csv(result, args.equity_out)}")
    return 0


def _cmd_strategies(_: argparse.Namespace) -> int:
    for cls in list_strategies():
        print(f"{cls.name}: {cls.description}")
        defaults = cls()
        for key, typ in parameter_types(cls).items():
            print(f"    {key} ({typ.__name__}, default {getattr(defaults, key)!r})")
    return 0


_COMMANDS = {"fetch": _cmd_fetch, "backtest": _cmd_backtest, "strategies": _cmd_strategies}


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return _COMMANDS[args.command](args)
    except (DataError, ValueError, URLError, OSError) as exc:
        print(f"candlelab: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
