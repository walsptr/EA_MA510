# PRD.md — MA Cross Trend-Following EA (MT5 / Python)

## 1. Overview

An automated trading bot ("EA") for MetaTrader 5, written in Python using the official
`MetaTrader5` package. The bot trades a **Moving Average Cross strategy filtered by
multi-timeframe trend confirmation**. It must support two operating modes controlled by a
single environment variable (`MODE`):

- **BACKTEST** — replay historical price data over a configurable date range and produce
  performance metrics.
- **LIVE** — connect to a running MT5 terminal, monitor price in real time, and place real
  orders.

## 2. Background

This is a companion / alternative strategy track to the existing XAUUSD MT5 bot effort.
Prior iterations (EMA 9/21 crossover → filtered EMA → Triple Confirmation Scalping) hit
persistent stop-outs, traced to lagging-indicator strategies mismatched against a
ranging/choppy 2026 M5 regime, and to unrealistic return targets relative to capital.

This project intentionally goes back to a simpler, fully rule-based, fully configurable
MA Cross + multi-timeframe trend filter, so that:

- The strategy logic is transparent and auditable (no black-box scoring).
- Every parameter that previously required a code change is now an **ENV variable**, so the
  same codebase can be re-tuned and re-backtested quickly without touching code.
- Backtest and live share the exact same signal-generation code path, to eliminate
  "backtest vs live" logic drift as a source of bugs.

## 3. Goals

1. One codebase, one entrypoint, mode switch via `MODE=BACKTEST` or `MODE=LIVE`.
2. Fully parametrized strategy: MA periods, MA type, entry timeframe, and up to N trend
   confirmation timeframes — all via ENV.
3. Backtest date range configurable via ENV (`BACKTEST_START_DATE`, `BACKTEST_END_DATE`).
4. Deterministic, testable signal logic shared by both modes (`strategy.py` has no
   knowledge of whether it's running in backtest or live).
5. Backtest produces a metrics report + equity curve + trade log (see SCHEMA.md).
6. Live mode places real orders with risk management (position sizing, SL/TP) driven by
   the same ENV-configured risk parameters.
7. Safe-by-default: bot must not trade if config is invalid, MT5 connection is down, or
   required historical data is insufficient to compute indicators.

## 4. Non-Goals (v1)

- No machine learning / adaptive parameter optimization.
- No multi-symbol portfolio management (single `SYMBOL` per running instance).
- No GUI/dashboard — CLI + log files + optional CSV/DB export only.
- No walk-forward optimization engine (may be a future extension on top of the backtest
  engine, not part of v1).
- No news/fundamental filters.

## 5. Target User

Wal — building and personally operating automated trading systems. Runs the bot locally /
on a VPS against a real MT5 terminal instance. Comfortable with Python, expects
config-first, no-magic-numbers-in-code behavior.

## 6. Functional Requirements

| ID | Requirement |
|----|-------------|
| FR1 | System reads all configuration from environment variables (`.env` supported via `python-dotenv`) at startup and validates them before doing anything else. |
| FR2 | `MODE` env var selects `BACKTEST` or `LIVE`. Invalid/missing value → fail fast with a clear error. |
| FR3 | In `BACKTEST` mode, historical OHLCV is pulled from MT5 terminal history (`MetaTrader5.copy_rates_range`) for `SYMBOL` between `BACKTEST_START_DATE` and `BACKTEST_END_DATE`, for every timeframe required (`ENTRY_TIMEFRAME`, `TREND_TIMEFRAME_1`, `TREND_TIMEFRAME_2`, ...). |
| FR4 | In `LIVE` mode, the bot polls/streams live prices for the same set of timeframes and evaluates signals on each new closed candle of `ENTRY_TIMEFRAME`. |
| FR5 | MA periods (`MA_LOW`, `MA_HIGH`) and MA type (`MA_TYPE`: SMA or EMA) are configurable. `MA_LOW` must be less than `MA_HIGH`. |
| FR6 | Trend timeframes are configurable as a list (`TREND_TIMEFRAME_1`, `TREND_TIMEFRAME_2`, ... — extensible to N, see RULES.md). |
| FR7 | Entry rules exactly implement the Buy/Sell logic in RULES.md (trend alignment across all trend timeframes + fresh MA cross on entry timeframe in the same direction). |
| FR8 | Every trade has a stop-loss and take-profit (or trailing stop) computed from ENV-configured risk parameters — no unprotected positions. |
| FR9 | Position sizing is computed from account risk percentage or fixed lot size (configurable), never hardcoded. |
| FR10 | Backtest produces: trade log (CSV/DB), equity curve, and summary metrics (win rate, profit factor, max drawdown, total return, expectancy). |
| FR11 | Live mode logs every decision (signal detected, signal skipped + reason, order sent, order result) to a structured log file. |
| FR12 | Bot must gracefully handle MT5 connection loss/timeout in live mode (retry with backoff, never crash silently). |
| FR13 | One open position per symbol/direction at a time by default (configurable max concurrent positions). |

## 7. Non-Functional Requirements

- **Reliability**: live mode must run unattended for extended periods; must not place
  duplicate orders on the same signal (idempotency per closed candle).
- **Reproducibility**: given the same ENV config and the same historical data, backtest
  results must be identical across runs.
- **Observability**: structured logs (JSON or line-based) with timestamps, timeframe,
  signal type, and reasoning.
- **Portability**: must run on Windows (where MT5 terminal + Python API is officially
  supported) via a plain `python main.py`.
- **Config safety**: no secrets (MT5 login/password) committed to code; ENV/`.env` only,
  `.env` git-ignored.

## 8. Success Metrics

- Backtest and live signal generation produce identical signals given identical input
  candles (verified via a shared unit test fixture).
- A full backtest over a multi-month date range completes without manual intervention and
  produces a metrics report.
- Changing any of `MA_LOW`, `MA_HIGH`, `ENTRY_TIMEFRAME`, `TREND_TIMEFRAME_1/2` requires
  **zero code changes** — ENV only.
- No trade is ever opened without an attached SL.

## 9. Milestones (suggested build order)

1. Config loader + validation (`config.py`) — see SCHEMA.md.
2. MT5 data access layer (`mt5_client.py`, `data_feed.py`).
3. Indicator layer (`indicators.py`) — MA calculation, cross detection.
4. Strategy layer (`strategy.py`) — pure functions implementing RULES.md, mode-agnostic.
5. Backtest engine (`backtest_engine.py`) — bar-by-bar simulation using strategy.py.
6. Risk manager + order executor (`risk_manager.py`, `order_executor.py`).
7. Live engine (`live_engine.py`) — polling loop using strategy.py + order_executor.py.
8. Logging & reporting (`logger.py`, `reporting.py`).
9. `main.py` entrypoint wiring mode switch.

## 10. Open Questions / Assumptions

- Assumption: exactly 2 trend timeframes for v1 (`TREND_TIMEFRAME_1`, `TREND_TIMEFRAME_2`),
  but design should allow extending to N without a rewrite (see RULES.md §5).
- Assumption: single symbol per process (run multiple processes for multiple symbols).
- Assumption: SL/TP are required; trailing stop is optional and off by default.
