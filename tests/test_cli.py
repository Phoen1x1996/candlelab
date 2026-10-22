import pandas as pd
import pytest

from candlelab import cli, data
from candlelab.cli import main


def test_strategies_lists_ma_cross(capsys):
    assert main(["strategies"]) == 0
    out = capsys.readouterr().out
    assert "ma_cross" in out
    assert "fast (int, default 20)" in out


def test_backtest_prints_summary_and_writes_files(sample_csv, tmp_path, capsys):
    trades = tmp_path / "out" / "trades.csv"
    equity = tmp_path / "out" / "equity.csv"
    code = main(
        [
            "backtest",
            str(sample_csv),
            "-p",
            "fast=10",
            "-p",
            "slow=30",
            "-p",
            "kind=ema",
            "--trades-out",
            str(trades),
            "--equity-out",
            str(equity),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "ma_cross(fast=10, slow=30, kind=ema, source=close)" in out
    assert "Max drawdown" in out
    trade_rows = pd.read_csv(trades)
    assert len(trade_rows) > 0
    assert trade_rows["entry_time"].str.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ").all()
    curve = pd.read_csv(equity)
    assert list(curve.columns) == ["time", "equity", "position", "target"]


def test_backtest_window_uses_warm_indicators(sample_csv, tmp_path):
    equity = tmp_path / "equity.csv"
    code = main(
        [
            "backtest",
            str(sample_csv),
            "--start",
            "2023-01-01",
            "--end",
            "2023-06-30",
            "--equity-out",
            str(equity),
        ]
    )
    assert code == 0
    curve = pd.read_csv(equity)
    assert curve["time"].iloc[0] == "2023-01-01T00:00:00Z"
    assert curve["time"].iloc[-1] == "2023-06-30T00:00:00Z"


@pytest.mark.parametrize(
    "args",
    [
        ["-p", "fast=abc"],
        ["-p", "nonsense"],
        ["-p", "length=3"],
        ["-p", "fast=60", "-p", "slow=50"],
        ["-s", "does_not_exist"],
        ["--fee", "2"],
        ["--start", "2030-01-01"],
    ],
)
def test_backtest_errors_exit_with_code_2(sample_csv, capsys, args):
    assert main(["backtest", str(sample_csv), *args]) == 2
    assert "candlelab: error:" in capsys.readouterr().err


def test_backtest_missing_file(tmp_path, capsys):
    assert main(["backtest", str(tmp_path / "missing.csv")]) == 2
    assert "not found" in capsys.readouterr().err


def test_fetch_writes_csv(monkeypatch, tmp_path, capsys):
    rows = [
        [
            1704067200000 + i * 86_400_000,
            "1",
            "2",
            "0.5",
            "1.5",
            "3",
            1704153599999 + i * 86_400_000,
            "0",
            0,
            "0",
            "0",
            "0",
        ]
        for i in range(3)
    ]

    def fake_fetch(symbol, interval, start, end, pause):
        assert (symbol, interval, start, end) == ("ETHUSDT", "1d", "2024-01-01", "2024-01-04")
        return data.klines_to_frame(rows)

    monkeypatch.setattr(cli, "fetch_binance_klines", fake_fetch)
    out_path = tmp_path / "eth.csv"
    code = main(
        ["fetch", "ETHUSDT", "--start", "2024-01-01", "--end", "2024-01-04", "-o", str(out_path)]
    )
    assert code == 0
    assert "wrote 3 candles" in capsys.readouterr().out
    assert len(data.load_csv(out_path)) == 3
