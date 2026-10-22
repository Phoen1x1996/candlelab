"""Generate the synthetic sample dataset in ``examples/``.

The data is a seeded, regime-switching random walk - it is NOT real market data. It exists
so the quick-start and tests work offline. Use ``candlelab fetch`` for real candles.

    python scripts/make_synthetic_data.py examples/synthetic_daily.csv
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from candlelab.data import normalize_ohlcv, save_csv


def synthetic_candles(
    bars: int = 1000,
    start: str = "2022-01-01",
    freq: str = "1D",
    price: float = 30_000.0,
    seed: int = 7,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    vol = 0.03
    # Alternate bullish / bearish regimes of random length so crossovers actually happen.
    drift = np.empty(bars)
    i = 0
    bull = True
    while i < bars:
        length = int(rng.integers(60, 180))
        drift[i : i + length] = 0.004 if bull else -0.003
        bull = not bull
        i += length

    log_returns = drift + rng.normal(0.0, vol, bars)
    closes = price * np.exp(np.cumsum(log_returns))
    opens = np.concatenate([[price], closes[:-1]]) * np.exp(rng.normal(0.0, vol / 10, bars))
    wick = np.abs(rng.normal(0.0, vol / 2, (2, bars)))
    highs = np.maximum(opens, closes) * np.exp(wick[0])
    lows = np.minimum(opens, closes) * np.exp(-wick[1])
    volume = rng.lognormal(mean=8.0, sigma=0.4, size=bars)

    frame = pd.DataFrame(
        {
            "time": pd.date_range(start, periods=bars, freq=freq, tz="UTC"),
            "open": opens.round(2),
            "high": highs.round(2),
            "low": lows.round(2),
            "close": closes.round(2),
            "volume": volume.round(4),
        }
    )
    # Rounding can push open/close a cent outside the wick; widen the wick to compensate.
    frame["high"] = frame[["high", "open", "close"]].max(axis=1)
    frame["low"] = frame[["low", "open", "close"]].min(axis=1)
    return normalize_ohlcv(frame)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output")
    parser.add_argument("--bars", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    path = save_csv(synthetic_candles(bars=args.bars, seed=args.seed), args.output)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
