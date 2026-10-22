import math

import pandas as pd
import pytest

from candlelab.indicators import ema, sma


def test_sma_known_values():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(s, 3)
    assert out.isna().tolist() == [True, True, False, False, False]
    assert out.iloc[2:].tolist() == [2.0, 3.0, 4.0]


def test_ema_matches_recursive_definition():
    values = [10.0, 11.0, 9.0, 12.0, 13.0, 12.5]
    window = 3
    alpha = 2 / (window + 1)
    expected = [values[0]]
    for x in values[1:]:
        expected.append(alpha * x + (1 - alpha) * expected[-1])

    out = ema(pd.Series(values), window)

    assert out.iloc[: window - 1].isna().all()
    for got, want in zip(out.iloc[window - 1 :], expected[window - 1 :], strict=True):
        assert math.isclose(got, want, rel_tol=1e-12)


def test_window_one_is_identity():
    s = pd.Series([3.0, 1.0, 2.0])
    assert sma(s, 1).tolist() == s.tolist()
    assert ema(s, 1).tolist() == s.tolist()


@pytest.mark.parametrize("bad", [0, -1, 2.5, True, "3"])
@pytest.mark.parametrize("func", [sma, ema])
def test_invalid_window_rejected(func, bad):
    with pytest.raises(ValueError):
        func(pd.Series([1.0, 2.0]), bad)


def test_indicators_preserve_index():
    idx = pd.date_range("2024-01-01", periods=4, freq="1h", tz="UTC")
    s = pd.Series([1.0, 2.0, 3.0, 4.0], index=idx)
    assert sma(s, 2).index.equals(idx)
    assert ema(s, 2).index.equals(idx)
