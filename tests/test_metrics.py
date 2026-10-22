import math

import pandas as pd
import pytest

from candlelab.engine import BacktestConfig, run_backtest
from candlelab.metrics import max_drawdown, periods_per_year, sharpe_ratio, summarize


def test_max_drawdown():
    equity = pd.Series([100.0, 120.0, 90.0, 130.0, 65.0, 80.0])
    assert max_drawdown(equity) == pytest.approx(-0.5)  # 130 -> 65
    assert max_drawdown(pd.Series([1.0, 2.0, 3.0])) == 0.0


@pytest.mark.parametrize(("freq", "expected"), [("1D", 365.25), ("1h", 365.25 * 24)])
def test_periods_per_year(freq, expected):
    index = pd.date_range("2024-01-01", periods=10, freq=freq, tz="UTC")
    assert periods_per_year(index) == pytest.approx(expected)


def test_periods_per_year_ignores_a_single_gap():
    index = pd.DatetimeIndex(
        ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-10", "2024-01-11"], tz="UTC"
    )
    assert periods_per_year(index) == pytest.approx(365.25)


def test_sharpe_is_nan_for_flat_equity():
    assert math.isnan(sharpe_ratio(pd.Series([1.0, 1.0, 1.0]), 365.25))


def test_sharpe_sign_follows_returns():
    rising = pd.Series([100.0, 101.0, 103.0, 104.0, 107.0])
    assert sharpe_ratio(rising, 365.25) > 0
    assert sharpe_ratio(rising[::-1].reset_index(drop=True), 365.25) < 0


def test_summary_for_hand_built_backtest(candles_from):
    #             0    1    2    3    4    5
    closes = [100, 100, 120, 120, 90, 90]
    opens = [100, 100, 100, 120, 120, 90]
    candles = candles_from(closes=closes, opens=opens)
    target = pd.Series([1, 1, 0, 1, 0, 0], index=candles.index, dtype=float)

    result = run_backtest(candles, target, BacktestConfig(initial_cash=1000, fee_rate=0.0))
    s = summarize(result, candles)

    # Trade 1: buy open[1]=100, sell open[3]=120 -> +20%. Trade 2: buy open[4]=120,
    # sell open[5]=90 -> -25%.
    assert s.trades == 2
    assert s.win_rate == pytest.approx(0.5)
    assert s.avg_trade_return == pytest.approx((0.20 - 0.25) / 2)
    assert s.final_equity == pytest.approx(1000 * 1.2 * 0.75)
    assert s.total_return == pytest.approx(-0.1)
    assert s.profit_factor == pytest.approx(200 / 300)
    assert s.buy_and_hold_return == pytest.approx(-0.1)
    assert s.exposure == pytest.approx(3 / 6)
    assert s.total_fees == 0
    assert not s.open_position
    assert s.bars == 6


def test_summary_without_trades(candles_from):
    candles = candles_from([100, 110, 120])
    result = run_backtest(candles, pd.Series(0.0, index=candles.index))
    s = summarize(result, candles)
    assert s.trades == 0
    assert math.isnan(s.win_rate)
    assert math.isnan(s.profit_factor)
    assert s.total_return == 0
    assert s.as_dict()["start"].startswith("2024-01-01")


def test_profit_factor_infinite_when_no_losses(candles_from):
    candles = candles_from(closes=[100, 100, 120, 120], opens=[100, 100, 110, 130])
    target = pd.Series([1, 0, 0, 0], index=candles.index, dtype=float)
    s = summarize(run_backtest(candles, target, BacktestConfig(fee_rate=0)), candles)
    assert math.isinf(s.profit_factor)
