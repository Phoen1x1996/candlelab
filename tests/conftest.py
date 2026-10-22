from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import pytest

from candlelab.data import normalize_ohlcv

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def make_candles(
    closes: Sequence[float],
    opens: Sequence[float] | None = None,
    start: str = "2024-01-01",
    freq: str = "1D",
) -> pd.DataFrame:
    """Build a valid candle frame from closes (and optionally opens)."""
    closes = list(map(float, closes))
    if opens is None:
        opens = [closes[0], *closes[:-1]]
    opens = list(map(float, opens))
    frame = pd.DataFrame(
        {
            "time": pd.date_range(start, periods=len(closes), freq=freq, tz="UTC"),
            "open": opens,
            "high": [max(o, c) * 1.01 for o, c in zip(opens, closes, strict=True)],
            "low": [min(o, c) * 0.99 for o, c in zip(opens, closes, strict=True)],
            "close": closes,
            "volume": [1.0] * len(closes),
        }
    )
    return normalize_ohlcv(frame)


@pytest.fixture
def candles_from():
    """Factory fixture: ``candles_from(closes, opens=None, start=..., freq=...)``."""
    return make_candles


@pytest.fixture
def sample_csv() -> Path:
    path = EXAMPLES / "synthetic_daily.csv"
    assert path.exists(), "run scripts/make_synthetic_data.py examples/synthetic_daily.csv"
    return path
