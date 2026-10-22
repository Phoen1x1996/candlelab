"""Moving-average crossover (a.k.a. dual moving average, 双均线)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pandas as pd

from candlelab.data import OHLCV_COLUMNS
from candlelab.indicators import MOVING_AVERAGES
from candlelab.strategies.base import Strategy, register


@register
@dataclass
class MACross(Strategy):
    """Long while the fast moving average is above the slow one, flat otherwise.

    This is the *regime* form of the rule: if the fast average is already above the slow
    one when the data starts (after warm-up), the strategy is long immediately rather than
    waiting for a fresh crossover.
    """

    name: ClassVar[str] = "ma_cross"
    description: ClassVar[str] = "Long when fast MA > slow MA, flat otherwise."

    fast: int = 20
    slow: int = 50
    kind: str = "sma"
    source: str = "close"

    def __post_init__(self) -> None:
        for label, value in (("fast", self.fast), ("slow", self.slow)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{label} must be a positive integer, got {value!r}")
        if self.fast >= self.slow:
            raise ValueError(f"fast ({self.fast}) must be smaller than slow ({self.slow})")
        if self.kind not in MOVING_AVERAGES:
            raise ValueError(f"kind must be one of {', '.join(MOVING_AVERAGES)}, got {self.kind!r}")
        if self.source not in OHLCV_COLUMNS:
            raise ValueError(
                f"source must be one of {', '.join(OHLCV_COLUMNS)}, got {self.source!r}"
            )

    def target_position(self, candles: pd.DataFrame) -> pd.Series:
        average = MOVING_AVERAGES[self.kind]
        price = candles[self.source]
        fast = average(price, self.fast)
        slow = average(price, self.slow)
        # NaN comparisons are False, so the warm-up period is flat.
        return (fast > slow).astype(float).rename("target")
