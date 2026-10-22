"""Human-readable and file outputs for backtest results."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from candlelab.engine import BacktestResult
from candlelab.metrics import Summary

_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _pct(value: float, signed: bool = True) -> str:
    if math.isnan(value):
        return "n/a"
    return f"{value * 100:+.2f}%" if signed else f"{value * 100:.1f}%"


def _num(value: float, digits: int = 2) -> str:
    if math.isnan(value):
        return "n/a"
    if math.isinf(value):
        return "inf"
    return f"{value:,.{digits}f}"


def format_summary(summary: Summary, title: str | None = None) -> str:
    """Render a :class:`Summary` as an aligned plain-text block."""
    period = f"{summary.start:%Y-%m-%d %H:%M} -> {summary.end:%Y-%m-%d %H:%M}"
    trades = f"{summary.trades}"
    if summary.trades:
        trades += (
            f"  (win rate {_pct(summary.win_rate, signed=False)},"
            f" profit factor {_num(summary.profit_factor)})"
        )
    rows = [
        ("Period", f"{period}  ({summary.bars} bars)"),
        (
            "Equity",
            f"{_num(summary.initial_equity)} -> {_num(summary.final_equity)}",
        ),
        ("Total return", _pct(summary.total_return)),
        ("Buy & hold", _pct(summary.buy_and_hold_return)),
        ("CAGR", _pct(summary.cagr)),
        ("Max drawdown", _pct(summary.max_drawdown)),
        ("Sharpe", _num(summary.sharpe)),
        ("Exposure", _pct(summary.exposure, signed=False)),
        ("Closed trades", trades),
        ("Avg trade", _pct(summary.avg_trade_return)),
        ("Fees paid", _num(summary.total_fees)),
        ("Open position", "yes (marked to market)" if summary.open_position else "no"),
    ]
    width = max(len(label) for label, _ in rows) + 2
    lines = [title, "-" * len(title)] if title else []
    lines += [f"{label:<{width}}{value}" for label, value in rows]
    return "\n".join(lines)


def write_trades_csv(result: BacktestResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = result.trades_frame()
    for column in ("entry_time", "exit_time"):
        frame[column] = pd.to_datetime(frame[column], utc=True).dt.strftime(_TIME_FORMAT)
    frame.to_csv(path, index=False)
    return path


def write_equity_csv(result: BacktestResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = result.equity.to_frame().join(result.position).join(result.target)
    frame.index = frame.index.strftime(_TIME_FORMAT)
    frame.index.name = "time"
    frame.to_csv(path)
    return path
