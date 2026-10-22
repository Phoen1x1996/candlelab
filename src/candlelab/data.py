"""Loading, validating and fetching OHLCV candle data.

Every function in candlelab works on a *normalized* candle frame:

* a tz-aware UTC ``DatetimeIndex`` named ``time`` holding each candle's **open** time,
* float columns ``open``, ``high``, ``low``, ``close``, ``volume``,
* strictly increasing, de-duplicated timestamps.

Use :func:`normalize_ohlcv` (or :func:`load_csv`) to get there from raw input.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from candlelab import __version__

OHLCV_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume")
TIME_COLUMN_ALIASES: tuple[str, ...] = ("time", "timestamp", "open_time", "datetime", "date")

#: Public market-data host operated by Binance. No account or API key is needed.
BINANCE_PUBLIC_URL = "https://data-api.binance.vision"

#: Supported kline intervals and their length in milliseconds.
#: ``1M`` (calendar month) is intentionally absent because its length varies.
BINANCE_INTERVALS: dict[str, int] = {
    "1m": 60_000,
    "3m": 3 * 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 3_600_000,
    "2h": 2 * 3_600_000,
    "4h": 4 * 3_600_000,
    "6h": 6 * 3_600_000,
    "8h": 8 * 3_600_000,
    "12h": 12 * 3_600_000,
    "1d": 86_400_000,
    "3d": 3 * 86_400_000,
    "1w": 7 * 86_400_000,
}

_PRICE_TOLERANCE = 1e-9

#: Callable that performs an HTTP GET and returns the raw response body.
Opener = Callable[[str], bytes]


class DataError(ValueError):
    """Raised when candle data is missing, malformed or internally inconsistent."""


# --------------------------------------------------------------------------- normalization


def normalize_ohlcv(raw: pd.DataFrame) -> pd.DataFrame:
    """Return a clean, validated copy of ``raw`` in candlelab's canonical layout.

    ``raw`` may either already have a ``DatetimeIndex`` or carry a time column under any
    of :data:`TIME_COLUMN_ALIASES` (matched case-insensitively). Time values may be ISO
    strings or epoch numbers in seconds, milliseconds, microseconds or nanoseconds.
    Duplicate timestamps keep the **last** row (later downloads win).
    """
    if raw.empty:
        raise DataError("candle data is empty")

    frame = raw.copy()
    frame.columns = [str(c).strip().lower() for c in frame.columns]

    if isinstance(frame.index, pd.DatetimeIndex):
        index = frame.index
        index = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    else:
        time_col = next((c for c in TIME_COLUMN_ALIASES if c in frame.columns), None)
        if time_col is None:
            raise DataError(
                f"no time column found; expected one of {', '.join(TIME_COLUMN_ALIASES)}"
            )
        index = pd.DatetimeIndex(_parse_times(frame.pop(time_col)))

    missing = [c for c in OHLCV_COLUMNS if c not in frame.columns]
    if missing:
        raise DataError(f"missing required column(s): {', '.join(missing)}")

    values = frame[list(OHLCV_COLUMNS)].apply(pd.to_numeric, errors="coerce").astype(float)
    values.index = index
    values.index.name = "time"

    bad = values.isna().any(axis=1)
    if bad.any():
        first = values.index[bad.argmax()]
        raise DataError(f"non-numeric or missing OHLCV value at {first.isoformat()}")

    values = values[~values.index.duplicated(keep="last")].sort_index()
    _validate_prices(values)
    return values


def _parse_times(column: pd.Series) -> pd.DatetimeIndex:
    try:
        if pd.api.types.is_numeric_dtype(column):
            magnitude = float(column.abs().max())
            if magnitude >= 1e17:
                unit = "ns"
            elif magnitude >= 1e14:
                unit = "us"
            elif magnitude >= 1e11:
                unit = "ms"
            else:
                unit = "s"
            return pd.DatetimeIndex(pd.to_datetime(column, unit=unit, utc=True))
        return pd.DatetimeIndex(pd.to_datetime(column, utc=True, format="ISO8601"))
    except (ValueError, TypeError, OverflowError) as exc:
        raise DataError(f"could not parse time column: {exc}") from exc


def _validate_prices(frame: pd.DataFrame) -> None:
    checks = {
        "non-positive price": (frame[["open", "high", "low", "close"]] <= 0).any(axis=1),
        "negative volume": frame["volume"] < 0,
        "high below open/close": frame["high"] * (1 + _PRICE_TOLERANCE)
        < frame[["open", "close"]].max(axis=1),
        "low above open/close": frame["low"] * (1 - _PRICE_TOLERANCE)
        > frame[["open", "close"]].min(axis=1),
    }
    for problem, mask in checks.items():
        if mask.any():
            first = frame.index[mask.argmax()]
            raise DataError(f"{problem} at {first.isoformat()} ({int(mask.sum())} row(s))")


# --------------------------------------------------------------------------- CSV I/O


def load_csv(path: str | Path) -> pd.DataFrame:
    """Read a CSV file of candles and return it normalized."""
    path = Path(path)
    if not path.exists():
        raise DataError(f"file not found: {path}")
    try:
        raw = pd.read_csv(path)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise DataError(f"could not read {path}: {exc}") from exc
    return normalize_ohlcv(raw)


def save_csv(candles: pd.DataFrame, path: str | Path) -> Path:
    """Write normalized candles to ``path`` (ISO-8601 UTC timestamps). Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = candles[list(OHLCV_COLUMNS)].copy()
    out.index = out.index.strftime("%Y-%m-%dT%H:%M:%SZ")
    out.index.name = "time"
    out.to_csv(path)
    return path


# --------------------------------------------------------------------------- Binance fetcher


def _default_opener(url: str, timeout: float = 30.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": f"candlelab/{__version__}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def to_epoch_ms(value: Any) -> int:
    """Convert a date string, ``datetime`` or ``Timestamp`` to epoch milliseconds (UTC).

    Naive values are interpreted as UTC.
    """
    try:
        ts = pd.Timestamp(value)
    except (ValueError, TypeError) as exc:
        raise DataError(f"invalid date/time: {value!r}") from exc
    if pd.isna(ts):
        raise DataError(f"invalid date/time: {value!r}")
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return int(ts.value // 1_000_000)


def klines_to_frame(rows: Iterable[Sequence[Any]]) -> pd.DataFrame:
    """Convert raw Binance kline arrays into a normalized candle frame.

    Each row is ``[open_time, open, high, low, close, volume, close_time, ...]``;
    only the first six fields are used.
    """
    rows = list(rows)
    if not rows:
        raise DataError("no candles returned")
    raw = pd.DataFrame(
        [row[:6] for row in rows],
        columns=["open_time", "open", "high", "low", "close", "volume"],
    )
    raw["open_time"] = pd.to_numeric(raw["open_time"])
    return normalize_ohlcv(raw)


def fetch_binance_klines(
    symbol: str,
    interval: str,
    start: Any,
    end: Any | None = None,
    *,
    base_url: str = BINANCE_PUBLIC_URL,
    limit: int = 1000,
    pause: float = 0.0,
    drop_incomplete: bool = True,
    opener: Opener | None = None,
    now_ms: int | None = None,
) -> pd.DataFrame:
    """Download spot candles from Binance's public market-data API.

    Returns candles whose **open** time lies in ``[start, end)``. When ``end`` is omitted
    it defaults to now. Requests are paginated ``limit`` candles at a time.

    Parameters
    ----------
    drop_incomplete:
        Drop the candle that is still forming (its close time is in the future). Backtesting
        on a half-built candle silently uses information that will change.
    opener:
        Injected HTTP GET function; mainly for tests. Defaults to :mod:`urllib`.
    now_ms:
        Override "now" in epoch ms; mainly for tests.
    """
    if interval not in BINANCE_INTERVALS:
        raise DataError(
            f"unsupported interval {interval!r}; choose from {', '.join(BINANCE_INTERVALS)}"
        )
    if not 1 <= limit <= 1000:
        raise DataError("limit must be between 1 and 1000")

    get = opener or _default_opener
    step = BINANCE_INTERVALS[interval]
    now = int(time.time() * 1000) if now_ms is None else now_ms
    start_ms = to_epoch_ms(start)
    end_ms = now if end is None else to_epoch_ms(end)
    if start_ms >= end_ms:
        raise DataError("start must be earlier than end")

    rows: list[list[Any]] = []
    cursor = start_ms
    while cursor < end_ms:
        query = urllib.parse.urlencode(
            {
                "symbol": symbol.upper(),
                "interval": interval,
                "startTime": cursor,
                "endTime": end_ms - 1,
                "limit": limit,
            }
        )
        try:
            payload = json.loads(get(f"{base_url.rstrip('/')}/api/v3/klines?{query}"))
        except json.JSONDecodeError as exc:
            raise DataError(f"invalid JSON from {base_url}: {exc}") from exc
        if not isinstance(payload, list):
            raise DataError(f"unexpected response from {base_url}: {str(payload)[:200]}")
        if not payload:
            break
        rows.extend(payload)
        next_cursor = int(payload[-1][0]) + step
        if next_cursor <= cursor or len(payload) < limit:
            break
        cursor = next_cursor
        if pause:
            time.sleep(pause)

    if drop_incomplete:
        rows = [row for row in rows if int(row[6]) < now]
    return klines_to_frame(rows)
