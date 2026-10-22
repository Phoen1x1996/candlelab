"""Technical indicators.

All indicators take a ``pd.Series`` and return a ``pd.Series`` on the same index.
Values that cannot be computed yet (the warm-up period) are ``NaN`` - never a
partially-filled guess.
"""

from __future__ import annotations

import pandas as pd


def _check_window(window: int) -> None:
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        raise ValueError(f"window must be a positive integer, got {window!r}")


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average over the last ``window`` values."""
    _check_window(window)
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    """Exponential moving average with ``alpha = 2 / (window + 1)``.

    Uses the recursive form ``ema[t] = alpha * x[t] + (1 - alpha) * ema[t-1]`` seeded with
    the first value, and masks the first ``window - 1`` results as ``NaN``.
    """
    _check_window(window)
    return series.ewm(span=window, adjust=False, min_periods=window).mean()


MOVING_AVERAGES = {"sma": sma, "ema": ema}
