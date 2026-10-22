import json
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from candlelab.data import (
    DataError,
    fetch_binance_klines,
    klines_to_frame,
    load_csv,
    normalize_ohlcv,
    save_csv,
    to_epoch_ms,
)

DAY_MS = 86_400_000
T0 = to_epoch_ms("2024-01-01")


def _raw(**overrides):
    data = {
        "Timestamp": ["2024-01-02", "2024-01-01", "2024-01-03"],
        "Open": [11, 10, 12],
        "High": [12, 11, 13],
        "Low": [10, 9, 11],
        "Close": [12, 11, 13],
        "Volume": [5, 4, 6],
    }
    data.update(overrides)
    return pd.DataFrame(data)


def test_normalize_sorts_lowercases_and_sets_utc_index():
    frame = normalize_ohlcv(_raw())
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
    assert frame.index.name == "time"
    assert str(frame.index.tz) == "UTC"
    assert frame.index.is_monotonic_increasing
    assert frame["open"].tolist() == [10.0, 11.0, 12.0]
    assert all(pd.api.types.is_float_dtype(dtype) for dtype in frame.dtypes)


@pytest.mark.parametrize(
    ("values", "unit"),
    [
        ([T0 // 1000, T0 // 1000 + 86_400], "s"),
        ([T0, T0 + DAY_MS], "ms"),
        ([T0 * 1000, (T0 + DAY_MS) * 1000], "us"),
    ],
)
def test_epoch_units_are_detected(values, unit):
    raw = pd.DataFrame(
        {
            "open_time": values,
            "open": [1, 1],
            "high": [1, 1],
            "low": [1, 1],
            "close": [1, 1],
            "volume": [0, 0],
        }
    )
    frame = normalize_ohlcv(raw)
    assert frame.index[0] == pd.Timestamp("2024-01-01", tz="UTC"), unit
    assert frame.index[1] == pd.Timestamp("2024-01-02", tz="UTC"), unit


def test_datetime_index_input_is_accepted_and_localized():
    raw = _raw().set_index(pd.DatetimeIndex(["2024-01-02", "2024-01-01", "2024-01-03"]))
    raw = raw.drop(columns="Timestamp")
    frame = normalize_ohlcv(raw)
    assert str(frame.index.tz) == "UTC"
    assert frame.index[0] == pd.Timestamp("2024-01-01", tz="UTC")


def test_duplicates_keep_last():
    raw = _raw(Timestamp=["2024-01-01", "2024-01-01", "2024-01-02"], Close=[11, 10.5, 13])
    frame = normalize_ohlcv(raw)
    assert len(frame) == 2
    assert frame["close"].iloc[0] == 10.5


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"Close": [12, "x", 13]}, "non-numeric"),
        ({"High": [12, 10.5, 13]}, "high below"),
        ({"Low": [11.5, 9, 11]}, "low above"),
        ({"Volume": [5, -1, 6]}, "negative volume"),
        ({"Open": [11, 0, 12], "Low": [10, 0, 11]}, "non-positive"),
    ],
)
def test_invalid_rows_are_rejected(overrides, message):
    with pytest.raises(DataError, match=message):
        normalize_ohlcv(_raw(**overrides))


def test_missing_columns_and_time():
    with pytest.raises(DataError, match="missing required"):
        normalize_ohlcv(_raw().drop(columns="Volume"))
    with pytest.raises(DataError, match="no time column"):
        normalize_ohlcv(_raw().drop(columns="Timestamp"))
    with pytest.raises(DataError, match="empty"):
        normalize_ohlcv(pd.DataFrame())


def test_csv_round_trip(tmp_path):
    frame = normalize_ohlcv(_raw())
    path = save_csv(frame, tmp_path / "nested" / "candles.csv")
    assert path.read_text().splitlines()[1].startswith("2024-01-01T00:00:00Z,")
    pd.testing.assert_frame_equal(load_csv(path), frame)


def test_load_csv_missing_file(tmp_path):
    with pytest.raises(DataError, match="not found"):
        load_csv(tmp_path / "nope.csv")


def _kline(open_ms, price=100.0, interval_ms=DAY_MS):
    p = str(price)
    return [
        open_ms,
        p,
        str(price + 1),
        str(price - 1),
        p,
        "1.5",
        open_ms + interval_ms - 1,
        "150.0",
        10,
        "0.7",
        "70.0",
        "0",
    ]


def test_klines_to_frame():
    frame = klines_to_frame([_kline(T0, 100), _kline(T0 + DAY_MS, 105)])
    assert frame.index[0] == pd.Timestamp("2024-01-01", tz="UTC")
    assert frame["close"].tolist() == [100.0, 105.0]
    assert frame["volume"].tolist() == [1.5, 1.5]
    with pytest.raises(DataError, match="no candles"):
        klines_to_frame([])


class FakeBinance:
    """Serves daily klines for [T0, T0 + n days) and records requests."""

    def __init__(self, days):
        self.klines = [_kline(T0 + i * DAY_MS, 100 + i) for i in range(days)]
        self.requests = []

    def __call__(self, url):
        query = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        self.requests.append(query)
        start, end, limit = int(query["startTime"]), int(query["endTime"]), int(query["limit"])
        hits = [k for k in self.klines if start <= k[0] <= end][:limit]
        return json.dumps(hits).encode()


def test_fetch_paginates_and_respects_end():
    fake = FakeBinance(days=10)
    frame = fetch_binance_klines(
        "btcusdt", "1d", "2024-01-01", "2024-01-08", limit=3, opener=fake, now_ms=T0 + 100 * DAY_MS
    )
    assert len(frame) == 7  # Jan 1..7; end is exclusive
    assert frame.index[-1] == pd.Timestamp("2024-01-07", tz="UTC")
    assert [r["startTime"] for r in fake.requests] == [str(T0 + i * DAY_MS) for i in (0, 3, 6)]
    assert all(r["symbol"] == "BTCUSDT" and r["interval"] == "1d" for r in fake.requests)


def test_fetch_drops_incomplete_candle():
    fake = FakeBinance(days=5)
    now = T0 + 4 * DAY_MS + 3_600_000  # one hour into the 5th day
    frame = fetch_binance_klines("BTCUSDT", "1d", "2024-01-01", opener=fake, now_ms=now)
    assert len(frame) == 4
    kept = fetch_binance_klines(
        "BTCUSDT", "1d", "2024-01-01", opener=fake, now_ms=now, drop_incomplete=False
    )
    assert len(kept) == 5


def test_fetch_validates_inputs_and_responses():
    fake = FakeBinance(days=1)
    with pytest.raises(DataError, match="unsupported interval"):
        fetch_binance_klines("BTCUSDT", "7m", "2024-01-01", opener=fake)
    with pytest.raises(DataError, match="earlier than end"):
        fetch_binance_klines("BTCUSDT", "1d", "2024-02-01", "2024-01-01", opener=fake)
    with pytest.raises(DataError, match="unexpected response"):
        fetch_binance_klines(
            "BTCUSDT",
            "1d",
            "2024-01-01",
            "2024-01-02",
            opener=lambda url: b'{"code": -1121, "msg": "Invalid symbol."}',
        )
    with pytest.raises(DataError, match="invalid date"):
        to_epoch_ms("not a date")
