# Roadmap

candlelab grows in small, testable steps. Each item below is sized to be one focused piece
of work (a feature, a fix, a refactor or docs) with clear acceptance criteria. Items
marked **good first issue** are self-contained.

Labels: `feature` · `fix` · `refactor` · `test` · `docs` · `perf`

## v0.2 - TradingView parity and parameter search

The goal of this milestone is to reproduce what a TradingView strategy would have done,
and to pick parameters with evidence instead of guesswork.

- [ ] `feature` **Crossover-only entries for `ma_cross`** - add `entry=regime|cross`. In
  `cross` mode the strategy only enters on a fresh fast-over-slow cross (like Pine's
  `ta.crossover`) instead of being long whenever fast > slow at the start of the data.
- [ ] `feature` **Parameter sweep command** - `candlelab sweep data.csv -g fast=5:50:5
  -g slow=20:200:10` runs a grid, skips invalid combinations (fast ≥ slow), and writes a
  ranked CSV of summary metrics.
- [ ] `feature` **Heatmap of sweep results** - fast × slow grid of a chosen metric, saved as
  PNG/HTML.
- [ ] `feature` **Walk-forward validation** - rolling in-sample optimization and
  out-of-sample evaluation windows, reporting stitched out-of-sample equity.
- [ ] `test` **EMA parity fixture** - a small CSV of values exported from TradingView's
  `ta.ema`/`ta.sma` with a test that candlelab matches them (documenting any seeding
  differences).
- [ ] `feature` **JSON output** - `backtest --json` prints the summary as JSON for scripting.
  **good first issue**

## v0.3 - Risk management

- [ ] `feature` **Stop-loss and take-profit** - percentage-based, evaluated intrabar using
  high/low with a documented, conservative rule when both are hit in the same bar.
- [ ] `feature` **Trailing stop (ATR-based)** - add an `atr` indicator and an ATR trailing
  exit.
- [ ] `feature` **Position sizing** - support fractional targets (0 < target ≤ 1) and a
  fixed-fraction sizing mode; rebalance only when the change exceeds a threshold.
- [ ] `feature` **Maker/taker fees and BNB discount** - separate fee rates per side and a
  fee-asset option.
- [ ] `feature` **Minimum order size and lot-step rounding** - mimic exchange filters
  (`minNotional`, `stepSize`) so tiny accounts behave realistically.

## v0.4 - Reports

- [ ] `feature` **HTML report** - single self-contained file with equity curve, drawdown
  chart, price with trade markers, and the summary table.
- [ ] `feature` **Monthly returns table** - calendar heatmap of strategy returns.
- [ ] `feature` **More metrics** - Sortino, Calmar, longest drawdown duration, average
  bars held, unrealized P&L of the open position.
- [ ] `feature` **Benchmark with costs** - buy-and-hold including entry/exit fees and
  slippage for a fair comparison.
- [ ] `feature` **Rich terminal output** - colored summary table (optional dependency).
  **good first issue**

## v0.5 - Data

- [ ] `feature` **Local cache** - store fetched candles per symbol/interval and only
  download missing ranges on the next fetch.
- [ ] `fix` **Gap detection** - warn (or fail with `--strict`) when candles are missing,
  e.g. exchange outages, instead of silently treating the gap as one bar.
- [ ] `feature` **Resampling** - build 4h/1d candles from 1h data (`candlelab resample`).
- [ ] `feature` **Parquet support** - read/write `.parquet` when `pyarrow` is installed.
- [ ] `feature` **Multiple data sources** - pluggable source interface; add a second public
  source (e.g. bulk monthly archives from `data.binance.vision`).
- [ ] `fix` **Retry with backoff** - handle HTTP 429/5xx in the fetcher and honor
  `Retry-After`.

## v0.6 - Strategies

- [ ] `feature` **RSI mean-reversion** strategy.
- [ ] `feature` **Bollinger Band breakout** strategy.
- [ ] `feature` **Donchian channel / turtle breakout** strategy.
- [ ] `feature` **Strategy plugins via entry points** - third-party packages can register
  strategies without modifying candlelab.
- [ ] `feature` **DCA ladder simulation** - model a safety-order DCA bot (base order,
  safety orders, step scale, take profit) as used by common bot platforms.

## Ongoing quality

- [ ] `refactor` **Config files** - load backtest settings from a TOML file
  (`candlelab backtest --config run.toml`) so runs are reproducible.
- [ ] `refactor` **Strict typing** - add `mypy --strict` to CI and fix findings.
- [ ] `test` **Property-based tests** - Hypothesis tests for engine invariants (cash never
  negative, equity = cash + qty × close, fees ≥ 0, no trade before the first signal).
- [ ] `perf` **Engine speed** - benchmark on 1m candles over several years; vectorize or
  JIT the loop if needed while keeping the reference implementation for tests.
- [ ] `docs` **Documentation site** - MkDocs with a tutorial, the timing model with
  diagrams, and API reference.
- [ ] `docs` **Japanese and Chinese README** (`README.ja.md`, `README.zh.md`).
  **good first issue**
- [ ] `docs` **Worked example notebook** - from fetch to sweep to walk-forward on BTCUSDT.

## Out of scope

- Placing real orders or handling exchange API keys. candlelab is for research only; live
  trading belongs in a separate, purpose-built tool.
