# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-22

### Added

- OHLCV normalization and validation (`normalize_ohlcv`, `load_csv`, `save_csv`).
- Binance public market-data fetcher with pagination and incomplete-candle dropping.
- SMA and EMA indicators.
- Strategy base class and registry; `ma_cross` moving-average crossover strategy.
- Long-only, all-in backtest engine with next-bar-open execution, fees and slippage.
- Summary metrics: total return, CAGR, max drawdown, Sharpe, exposure, win rate, profit
  factor, fees, buy-and-hold comparison.
- `candlelab` CLI with `fetch`, `backtest` and `strategies` commands.
- Synthetic sample dataset and generator script.
- CI on Python 3.10-3.13 with ruff and pytest.
