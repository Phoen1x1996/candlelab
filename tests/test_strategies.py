import pytest

from candlelab.strategies import (
    coerce_param,
    get_strategy,
    list_strategies,
    parameter_types,
    strategy_class,
)
from candlelab.strategies.ma_cross import MACross


def test_ma_cross_is_registered():
    assert MACross in list_strategies()
    assert strategy_class("ma_cross") is MACross


def test_ma_cross_flat_during_warmup_and_long_in_uptrend(candles_from):
    candles = candles_from([float(x) for x in range(1, 31)])  # steady uptrend
    target = MACross(fast=3, slow=5).target_position(candles)

    assert target.index.equals(candles.index)
    assert (target.iloc[:4] == 0.0).all()  # slow SMA needs 5 bars
    assert (target.iloc[4:] == 1.0).all()


def test_ma_cross_goes_flat_in_downtrend(candles_from):
    up = [float(x) for x in range(1, 21)]
    down = [float(x) for x in range(20, 0, -1)]
    target = MACross(fast=2, slow=4).target_position(candles_from(up + down))
    assert target.iloc[19] == 1.0
    assert target.iloc[-1] == 0.0
    assert set(target.unique()) <= {0.0, 1.0}


def test_ma_cross_ema_kind(candles_from):
    candles = candles_from([float(x) for x in range(1, 31)])
    target = MACross(fast=3, slow=5, kind="ema").target_position(candles)
    assert target.iloc[-1] == 1.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fast": 5, "slow": 5},
        {"fast": 10, "slow": 5},
        {"fast": 0, "slow": 5},
        {"fast": 2.5, "slow": 5},
        {"kind": "wma"},
        {"source": "vwap"},
    ],
)
def test_ma_cross_rejects_bad_params(kwargs):
    with pytest.raises(ValueError):
        MACross(**kwargs)


def test_get_strategy_rejects_unknown_names_and_params():
    with pytest.raises(ValueError, match="unknown strategy"):
        get_strategy("nope")
    with pytest.raises(ValueError, match="no parameter"):
        get_strategy("ma_cross", length=3)


def test_parameter_types_and_coercion():
    assert parameter_types(MACross) == {"fast": int, "slow": int, "kind": str, "source": str}
    assert coerce_param(MACross, "fast", "12") == 12
    assert coerce_param(MACross, "kind", "ema") == "ema"
    with pytest.raises(ValueError, match="expects int"):
        coerce_param(MACross, "fast", "twelve")
    with pytest.raises(ValueError, match="no parameter"):
        coerce_param(MACross, "length", "3")


def test_params_round_trip():
    strategy = get_strategy("ma_cross", fast=7, slow=21, kind="ema")
    assert strategy.params() == {"fast": 7, "slow": 21, "kind": "ema", "source": "close"}
