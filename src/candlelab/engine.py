"""Backtest engine: turns a target-position series into trades and an equity curve.

Timing model (no look-ahead)
----------------------------
* ``target[t]`` is decided with information available at the **close** of bar ``t``.
* A change in target is executed at the **open** of bar ``t + 1``.
* Equity is marked to market at every bar's close.
* The target of the final bar is never executed (there is no next open).

Fill model
----------
* Long-only spot, all-in: an entry spends all available cash, an exit sells everything.
* Slippage moves the fill price against you: buys fill at ``open * (1 + slippage)``,
  sells at ``open * (1 - slippage)``.
* Fees are charged in the quote currency on the traded notional at ``fee_rate`` per side.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    """Account and cost assumptions for a backtest."""

    initial_cash: float = 10_000.0
    fee_rate: float = 0.001
    slippage: float = 0.0

    def __post_init__(self) -> None:
        if not self.initial_cash > 0:
            raise ValueError("initial_cash must be positive")
        if not 0 <= self.fee_rate < 1:
            raise ValueError("fee_rate must be in [0, 1)")
        if not 0 <= self.slippage < 1:
            raise ValueError("slippage must be in [0, 1)")


@dataclass(frozen=True)
class Trade:
    """One round trip. Open trades are marked to market at the last close."""

    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp | None
    exit_price: float
    quantity: float
    cost: float
    fees: float
    pnl: float
    return_pct: float
    bars_held: int
    is_open: bool = False


@dataclass
class BacktestResult:
    equity: pd.Series
    position: pd.Series
    trades: list[Trade]
    config: BacktestConfig
    target: pd.Series = field(repr=False)

    def trades_frame(self) -> pd.DataFrame:
        """Trades as a DataFrame (one row per trade)."""
        columns = [f.name for f in Trade.__dataclass_fields__.values()]
        return pd.DataFrame([t.__dict__ for t in self.trades], columns=columns)


@dataclass
class _OpenTrade:
    time: pd.Timestamp
    price: float
    quantity: float
    cost: float
    fee: float
    bar: int


def _prepare_target(candles: pd.DataFrame, target: pd.Series) -> np.ndarray:
    if not target.index.equals(candles.index):
        missing = candles.index.difference(target.index)
        if len(missing):
            raise ValueError(
                f"target is missing {len(missing)} bar(s), first at {missing[0].isoformat()}"
            )
        target = target.reindex(candles.index)
    values = pd.to_numeric(target, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    invalid = ~np.isin(values, (0.0, 1.0))
    if invalid.any():
        raise ValueError(
            f"only targets of 0 (flat) or 1 (fully long) are supported; got {values[invalid][0]!r}"
        )
    return values


def run_backtest(
    candles: pd.DataFrame,
    target: pd.Series,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Simulate a long-only, all-in spot strategy. See the module docstring for the model.

    ``NaN`` targets are treated as flat.
    """
    config = config or BacktestConfig()
    if len(candles) < 2:
        raise ValueError("need at least two candles to backtest")

    desired = _prepare_target(candles, target)
    index = candles.index
    opens = candles["open"].to_numpy(dtype=float)
    closes = candles["close"].to_numpy(dtype=float)
    fee, slip = config.fee_rate, config.slippage

    cash = config.initial_cash
    qty = 0.0
    open_trade: _OpenTrade | None = None
    trades: list[Trade] = []
    equity = np.empty(len(candles))
    held = np.empty(len(candles))

    for i in range(len(candles)):
        if i > 0:
            want_long = desired[i - 1] == 1.0
            if want_long and open_trade is None:
                price = opens[i] * (1 + slip)
                qty = cash / (price * (1 + fee))
                entry_fee = qty * price * fee
                open_trade = _OpenTrade(index[i], price, qty, cash, entry_fee, i)
                cash = 0.0
            elif not want_long and open_trade is not None:
                price = opens[i] * (1 - slip)
                gross = qty * price
                exit_fee = gross * fee
                cash = gross - exit_fee
                trades.append(_close(open_trade, index[i], price, cash, exit_fee, i))
                qty = 0.0
                open_trade = None
        equity[i] = cash + qty * closes[i]
        held[i] = qty

    if open_trade is not None:
        last = len(candles) - 1
        value = qty * closes[last]
        trades.append(_close(open_trade, None, closes[last], value, 0.0, last, is_open=True))

    return BacktestResult(
        equity=pd.Series(equity, index=index, name="equity"),
        position=pd.Series(held, index=index, name="position"),
        trades=trades,
        config=config,
        target=pd.Series(desired, index=index, name="target"),
    )


def _close(
    entry: _OpenTrade,
    exit_time: pd.Timestamp | None,
    exit_price: float,
    proceeds: float,
    exit_fee: float,
    bar: int,
    *,
    is_open: bool = False,
) -> Trade:
    pnl = float(proceeds - entry.cost)
    return Trade(
        entry_time=entry.time,
        entry_price=float(entry.price),
        exit_time=exit_time,
        exit_price=float(exit_price),
        quantity=float(entry.quantity),
        cost=float(entry.cost),
        fees=float(entry.fee + exit_fee),
        pnl=pnl,
        return_pct=pnl / entry.cost,
        bars_held=bar - entry.bar,
        is_open=is_open,
    )
