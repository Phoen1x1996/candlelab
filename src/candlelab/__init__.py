"""candlelab - a small, transparent backtesting lab for OHLCV candles."""

__version__ = "0.1.0"

from candlelab.data import DataError, fetch_binance_klines, load_csv, normalize_ohlcv, save_csv
from candlelab.engine import BacktestConfig, BacktestResult, Trade, run_backtest
from candlelab.metrics import Summary, summarize
from candlelab.strategies import Strategy, get_strategy, list_strategies

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "DataError",
    "Strategy",
    "Summary",
    "Trade",
    "__version__",
    "fetch_binance_klines",
    "get_strategy",
    "list_strategies",
    "load_csv",
    "normalize_ohlcv",
    "run_backtest",
    "save_csv",
    "summarize",
]
