# ARCHITECTURE.md — System Architecture

## 1. Design Principle

**One strategy core, two runners.** `strategy.py` decides *what to do* given candle data.
It has zero knowledge of MT5 connections, order placement, or whether it's being called
from a backtest loop or a live polling loop. `backtest_engine.py` and `live_engine.py` are
both thin runners that feed candle data into the same strategy function and act on its
output differently (simulate a fill vs. send a real order).

```
                     ┌─────────────────┐
                     │     main.py      │  reads MODE, dispatches
                     └────────┬─────────┘
                              │
                 ┌────────────┴────────────┐
                 │                         │
         MODE=BACKTEST                MODE=LIVE
                 │                         │
      ┌──────────▼─────────┐   ┌───────────▼───────────┐
      │  backtest_engine.py │   │      live_engine.py    │
      │  (bar-by-bar loop)  │   │   (polling loop, waits  │
      │                     │   │    for new closed bar)  │
      └──────────┬──────────┘   └───────────┬────────────┘
                 │                          │
                 └────────────┬─────────────┘
                               │
                     ┌─────────▼─────────┐
                     │    strategy.py     │  pure functions:
                     │  evaluate_signal() │  candles in -> Signal out
                     └─────────┬─────────┘
                               │
                     ┌─────────▼─────────┐
                     │   indicators.py    │  MA calc, cross detection
                     └────────────────────┘

      Both engines also use:
      ┌────────────────┐   ┌──────────────────┐   ┌─────────────────┐
      │  data_feed.py    │   │  risk_manager.py  │   │ order_executor.py│
      │ (candle fetch,   │   │ (lot sizing,       │   │ (send/simulate    │
      │  per timeframe)  │   │  SL/TP calc)       │   │  order, track pos) │
      └────────────────┘   └──────────────────┘   └─────────────────┘

      Cross-cutting: config.py (env loading/validation), logger.py, reporting.py
```

## 2. Module Map

| Module | Responsibility |
|---|---|
| `main.py` | Entry point. Loads config, sets up logging, dispatches to backtest or live engine based on `MODE`. |
| `config.py` | Loads ENV (via `python-dotenv` + `os.environ`), validates types/ranges/consistency (see SCHEMA.md), exposes a single immutable `Config` object used everywhere else. Fails fast with descriptive errors. |
| `mt5_client.py` | Thin wrapper around the `MetaTrader5` package: `initialize()`, `shutdown()`, `login`, connection health check, retry/reconnect logic. Both live and backtest use this for terminal/history access. |
| `data_feed.py` | Fetches OHLCV candles for a given symbol+timeframe: `copy_rates_from`/`copy_rates_range` for backtest history, and latest-N-candles for live polling. Normalizes MT5 timeframe constants from the string values in ENV (`M5`, `M15`, `H1`, ...). Returns pandas DataFrames with a consistent schema (see SCHEMA.md §4). |
| `indicators.py` | Pure functions: `moving_average(series, period, ma_type)`, `detect_cross(ma_low_series, ma_high_series)` → returns `NONE / CROSS_UP / CROSS_DOWN` for the latest bar. No I/O. |
| `strategy.py` | `evaluate_signal(candles_by_timeframe: dict[str, DataFrame], cfg: Config) -> Signal`. Implements RULES.md exactly. Mode-agnostic, unit-testable with static fixtures. |
| `risk_manager.py` | Given account equity, symbol info, and `cfg`, computes lot size and SL/TP price levels for a given signal. Pure calculation, no order sending. |
| `order_executor.py` | Two implementations behind a common interface: `LiveOrderExecutor` (calls `MetaTrader5.order_send`) and `BacktestOrderExecutor` (simulates fills against the historical bar, tracks a virtual position book and equity curve). Both implement `open_position()`, `close_position()`, `get_open_positions()`. |
| `backtest_engine.py` | Loads historical data for all required timeframes over `[BACKTEST_START_DATE, BACKTEST_END_DATE]`, iterates entry-timeframe bars chronologically, calls `strategy.evaluate_signal` with the correctly time-aligned slice of each timeframe's history (no look-ahead), calls `BacktestOrderExecutor`, accumulates trade log + equity curve, and at the end calls `reporting.py` to produce the summary. |
| `live_engine.py` | Connects via `mt5_client`, enters a polling loop (`LIVE_POLL_INTERVAL_SECONDS`), detects newly closed `ENTRY_TIMEFRAME` candles, fetches current data for all required timeframes, calls `strategy.evaluate_signal`, and on a signal calls `risk_manager` + `LiveOrderExecutor`. Includes reconnect/backoff handling. |
| `logger.py` | Structured logging setup (console + rotating file). Used by every module. |
| `reporting.py` | Computes backtest metrics (win rate, profit factor, max drawdown, expectancy, total return) from the trade log + equity curve, writes report files (see SCHEMA.md §6). |

## 3. Data Flow (Backtest)

1. `main.py` → `config.py` loads & validates ENV.
2. `backtest_engine.py` asks `data_feed.py` for full history of every required timeframe
   across the backtest date range.
3. For each closed bar on `ENTRY_TIMEFRAME` (walking forward in time):
   a. Slice each trend timeframe's history up to the latest candle that had actually
      closed by that point in time (no look-ahead — RULES.md §7).
   b. Call `strategy.evaluate_signal(...)`.
   c. If a signal fires and no conflicting open position exists, call `risk_manager` for
      lot size/SL/TP, then `BacktestOrderExecutor.open_position(...)`.
   d. On every bar, `BacktestOrderExecutor` checks open positions against the bar's
      high/low to simulate SL/TP hits and updates the equity curve.
4. After the loop, `reporting.py` writes the trade log, equity curve, and metrics summary.

## 4. Data Flow (Live)

1. `main.py` → `config.py` loads & validates ENV.
2. `live_engine.py` connects to the running MT5 terminal via `mt5_client.py`.
3. Loop every `LIVE_POLL_INTERVAL_SECONDS`:
   a. `data_feed.py` fetches the latest N candles for `ENTRY_TIMEFRAME` and each trend
      timeframe.
   b. If the latest `ENTRY_TIMEFRAME` candle's open time is new (not yet processed):
      - Call `strategy.evaluate_signal(...)`.
      - On a signal, call `risk_manager` then `LiveOrderExecutor.open_position(...)`
        (real `order_send`).
      - Mark this candle's open time as processed (idempotency — never double-fire on the
        same closed candle).
   c. Independently of new-candle detection, check open positions for trailing-stop
      updates and the daily-loss circuit breaker if enabled.
4. All decisions (signal fired / signal skipped + reason / order result) are logged via
   `logger.py`.

## 5. External Dependencies

- `MetaTrader5` (official Python package) — terminal connection, history, order sending.
- `pandas`, `numpy` — candle data handling, MA/indicator math.
- `python-dotenv` — `.env` loading.
- Optional: `pydantic` for config validation (recommended — see SCHEMA.md), or plain
  `dataclasses` if the coding agent prefers zero extra dependencies.

## 6. Deployment Notes

- MT5 Python API requires the MT5 terminal to be installed and logged in on the same
  Windows machine/VPS the script runs on (official package limitation).
- `.env` is git-ignored; a `.env.example` documents every variable (see SCHEMA.md) without
  real credentials.
- Logs and reports write to a local `logs/` and `reports/` directory (git-ignored),
  timestamped per run.
