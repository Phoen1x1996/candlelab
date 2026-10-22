# Contributing

Thanks for your interest in candlelab!

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Before opening a pull request

```bash
ruff format .
ruff check .
pytest
```

The test suite runs fully offline; network calls are injected (`opener=`) or monkeypatched.

## Guidelines

- **Correctness first.** Any change to execution timing, fills or fees needs a test with a
  hand-computed expected result (see `tests/test_engine.py`).
- **No look-ahead.** Strategies may only use data up to and including the current bar's
  close.
- **Keep the core small.** Optional features (charts, rich output, parquet) go behind
  optional dependencies.
- **No secrets.** candlelab only uses public market data. Never commit API keys, `.env`
  files or downloaded data (`data/` and `reports/` are git-ignored).
- Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages
  (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).

## Adding a strategy

1. Create `src/candlelab/strategies/<name>.py` with a `@register`ed `@dataclass` subclass of
   `Strategy`; its fields are the parameters (int, float, str or bool).
2. Validate parameters in `__post_init__`.
3. Implement `target_position(candles)` returning a 0/1 series on `candles.index`.
4. Import the module in `strategies/__init__.py` and add tests.
