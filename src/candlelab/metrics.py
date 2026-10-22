"""Performance statistics for a :class:`~candlelab.engine.BacktestResult`."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import pandas as pd

from candlelab.engine import BacktestResult

SECONDS_PER_YEAR = 365.25 * 24 * 3600  # crypto trades every day of the year


@dataclass(frozen=True)
class Summary:
    start: pd.Timestamp
    end: pd.Timestamp
    bars: int
    initial_equity: float
    final_equity: float
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe: float
    exposure: float
    trades: int
    win_rate: float
    profit_factor: float
    avg_trade_return: float
    total_fees: float
    buy_and_hold_return: float
    open_position: bool

    def as_dict(self) -> dict[str, object]:
        out = asdict(self)
        out["start"] = self.start.isoformat()
        out["end"] = self.end.isoformat()
        return out


def periods_per_year(index: pd.DatetimeIndex) -> float:
    """Bars per year, inferred from the median spacing of ``index``."""
    if len(index) < 2:
        raise ValueError("need at least two timestamps")
    spacing = pd.Series(index).diff().dropna().median().total_seconds()
    if spacing <= 0:
        raise ValueError("timestamps must be increasing")
    return SECONDS_PER_YEAR / spacing


def max_drawdown(equity: pd.Series) -> float:
    """Largest peak-to-trough decline as a negative fraction (``-0.25`` = -25%)."""
    if equity.empty:
        return math.nan
    return float((equity / equity.cummax() - 1.0).min())


def sharpe_ratio(equity: pd.Series, bars_per_year: float) -> float:
    """Annualized Sharpe ratio of per-bar returns with a zero risk-free rate."""
    returns = equity.pct_change().dropna()
    if len(returns) < 2:
        return math.nan
    std = returns.std(ddof=1)
    if std == 0 or math.isnan(std):
        return math.nan
    return float(returns.mean() / std * math.sqrt(bars_per_year))


def _profit_factor(wins: list[float], losses: list[float]) -> float:
    """Gross profit / gross loss; ``inf`` with wins but no losses, ``nan`` with no trades."""
    if losses:
        return sum(wins) / -sum(losses)
    return math.inf if wins else math.nan


def summarize(result: BacktestResult, candles: pd.DataFrame) -> Summary:
    """Compute headline statistics. ``candles`` must cover the backtested bars."""
    equity = result.equity
    initial = result.config.initial_cash
    final = float(equity.iloc[-1])
    years = (equity.index[-1] - equity.index[0]).total_seconds() / SECONDS_PER_YEAR

    cagr = (final / initial) ** (1 / years) - 1 if years > 0 and final > 0 else math.nan

    closed = [t for t in result.trades if not t.is_open]
    wins = [t.pnl for t in closed if t.pnl > 0]
    losses = [t.pnl for t in closed if t.pnl < 0]
    profit_factor = _profit_factor(wins, losses)

    closes = candles["close"].loc[equity.index]
    return Summary(
        start=equity.index[0],
        end=equity.index[-1],
        bars=len(equity),
        initial_equity=initial,
        final_equity=final,
        total_return=final / initial - 1,
        cagr=cagr,
        max_drawdown=max_drawdown(equity),
        sharpe=sharpe_ratio(equity, periods_per_year(equity.index)),
        exposure=float((result.position > 0).mean()),
        trades=len(closed),
        win_rate=len(wins) / len(closed) if closed else math.nan,
        profit_factor=profit_factor,
        avg_trade_return=(sum(t.return_pct for t in closed) / len(closed)) if closed else math.nan,
        total_fees=sum(t.fees for t in result.trades),
        buy_and_hold_return=float(closes.iloc[-1] / closes.iloc[0] - 1),
        open_position=any(t.is_open for t in result.trades),
    )
