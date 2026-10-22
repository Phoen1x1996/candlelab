import math

import pandas as pd
import pytest

from candlelab.engine import BacktestConfig, run_backtest


def _target(candles, values):
    return pd.Series(values, index=candles.index, dtype=float)


def test_round_trip_with_fees_and_slippage_matches_hand_calculation(candles_from):
    candles = candles_from(closes=[100, 105, 115, 95, 100], opens=[100, 100, 110, 120, 90])
    config = BacktestConfig(initial_cash=1000.0, fee_rate=0.001, slippage=0.01)

    result = run_backtest(candles, _target(candles, [1, 1, 0, 0, 0]), config)

    buy_price = 100 * 1.01  # signal at close of bar 0 -> filled at open of bar 1
    qty = 1000.0 / (buy_price * 1.001)
    sell_price = 120 * 0.99  # signal at close of bar 2 -> filled at open of bar 3
    proceeds = qty * sell_price * (1 - 0.001)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_time == candles.index[1]
    assert trade.exit_time == candles.index[3]
    assert trade.entry_price == pytest.approx(buy_price)
    assert trade.exit_price == pytest.approx(sell_price)
    assert trade.quantity == pytest.approx(qty)
    assert trade.bars_held == 2
    assert not trade.is_open
    assert trade.pnl == pytest.approx(proceeds - 1000.0)
    assert trade.pnl == pytest.approx(173.8875, abs=1e-3)
    assert type(trade.pnl) is float  # plain floats, not numpy scalars
    assert trade.return_pct == pytest.approx(trade.pnl / 1000.0)
    assert trade.fees == pytest.approx(qty * buy_price * 0.001 + qty * sell_price * 0.001)

    expected_equity = [1000.0, qty * 105, qty * 115, proceeds, proceeds]
    assert result.equity.tolist() == pytest.approx(expected_equity)
    assert result.position.tolist() == pytest.approx([0, qty, qty, 0, 0])


def test_signal_on_last_bar_is_never_executed(candles_from):
    candles = candles_from([100, 101, 102, 103])
    result = run_backtest(candles, _target(candles, [0, 0, 0, 1]))
    assert result.trades == []
    assert result.equity.tolist() == [10_000.0] * 4


def test_first_bar_signal_executes_on_second_bar_open(candles_from):
    candles = candles_from(closes=[100, 110, 120], opens=[95, 105, 115])
    cfg = BacktestConfig(fee_rate=0.0)
    result = run_backtest(candles, _target(candles, [1, 0, 0]), cfg)
    (trade,) = result.trades
    assert trade.entry_price == 105  # not the open (95) or close (100) of bar 0
    assert trade.exit_price == 115


def test_open_position_is_marked_to_market(candles_from):
    candles = candles_from(closes=[100, 100, 150], opens=[100, 100, 120])
    result = run_backtest(candles, _target(candles, [1, 1, 1]), BacktestConfig(fee_rate=0.0))

    (trade,) = result.trades
    assert trade.is_open
    assert trade.exit_time is None
    assert trade.exit_price == 150
    assert trade.pnl == pytest.approx(5_000.0)
    assert result.equity.iloc[-1] == pytest.approx(15_000.0)


def test_always_flat_keeps_cash(candles_from):
    candles = candles_from([100, 50, 200, 10])
    result = run_backtest(candles, _target(candles, [0, 0, 0, 0]))
    assert result.trades == []
    assert (result.equity == 10_000.0).all()
    assert (result.position == 0.0).all()


def test_nan_target_means_flat(candles_from):
    candles = candles_from([100, 101, 102])
    result = run_backtest(candles, _target(candles, [math.nan, math.nan, 1]))
    assert result.trades == []


def test_fractional_target_rejected(candles_from):
    candles = candles_from([100, 101, 102])
    with pytest.raises(ValueError, match="only targets of 0"):
        run_backtest(candles, _target(candles, [0, 0.5, 1]))


def test_target_missing_bars_rejected(candles_from):
    candles = candles_from([100, 101, 102])
    short = pd.Series([1.0, 1.0], index=candles.index[:2])
    with pytest.raises(ValueError, match="missing 1 bar"):
        run_backtest(candles, short)


def test_target_with_extra_bars_is_aligned(candles_from):
    candles = candles_from([100, 101, 102, 103])
    longer = pd.Series([1.0, 1.0, 1.0, 1.0, 0.0], index=candles_from([1] * 5).index)
    result = run_backtest(candles, longer)
    assert result.target.index.equals(candles.index)


def test_needs_two_candles(candles_from):
    candles = candles_from([100])
    with pytest.raises(ValueError, match="at least two"):
        run_backtest(candles, _target(candles, [1]))


@pytest.mark.parametrize(
    "kwargs",
    [{"initial_cash": 0}, {"fee_rate": -0.1}, {"fee_rate": 1}, {"slippage": 1.5}],
)
def test_config_validation(kwargs):
    with pytest.raises(ValueError):
        BacktestConfig(**kwargs)


def test_trades_frame_columns(candles_from):
    candles = candles_from([100, 101, 102, 103])
    result = run_backtest(candles, _target(candles, [1, 0, 1, 1]))
    frame = result.trades_frame()
    assert len(frame) == 2
    assert frame["is_open"].tolist() == [False, True]
    assert {"entry_time", "exit_time", "pnl", "fees", "return_pct"} <= set(frame.columns)
