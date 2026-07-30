# AGENTS.md — Instructions for the AI Coding Agent

This file is the entrypoint for any AI coding assistant (Claude, Trae, etc.) working in
this repository. Read this first, then read the other context files in the order below
before writing or editing any code.

## 1. Reading Order

1. **PRD.md** — why this bot exists, scope, what's in/out for v1. Read this to understand
   intent before touching requirements.
2. **RULES.md** — the exact trading logic (entry/exit/sizing rules). This is the source of
   truth for *behavior*. If code and RULES.md disagree, RULES.md wins — flag the
   discrepancy instead of silently picking one.
3. **ARCHITECTURE.md** — module boundaries and data flow. Defines *where* each piece of
   logic belongs.
4. **DESIGN.md** — concrete function/class signatures, algorithms, pseudo-code. Implement
   against this directly; it's intentionally close to real code.
5. **SCHEMA.md** — every ENV variable (name, type, required/default, validation rules) and
   every data structure (candle DataFrame, trade log, report JSON, log line format).

Do not start writing code from memory of "a typical MA cross bot." Use these files as the
spec. If something needed to implement a task isn't covered by these files, stop and ask
rather than inventing new behavior — especially for anything touching order sizing, SL/TP,
or live order placement.

## 2. Ground Rules

- **RULES.md is the contract for trading logic.** Never change entry/exit conditions,
  add filters, or "improve" the strategy without it being reflected in RULES.md first.
- **SCHEMA.md is the contract for configuration.** Every tunable value must be an ENV
  variable per SCHEMA.md — no hardcoded periods, timeframes, lot sizes, SL/TP distances,
  or magic numbers in code. If a new parameter is genuinely needed, add it to SCHEMA.md
  (with type/default/validation) before wiring it into code, and update PRD.md/RULES.md
  if it changes behavior.
- **`strategy.py` stays pure.** No MT5 calls, no file I/O, no `datetime.now()` inside it.
  It must be fully testable with hand-built pandas DataFrames. Backtest and live must call
  the exact same `evaluate_signal()` function — never fork the logic.
- **No look-ahead in backtests.** Any trend-timeframe candle used to evaluate a signal at
  time T must have a `close_time <= T` on the entry timeframe. See RULES.md §7 and
  DESIGN.md §6 (`slice_up_to_time`). This is the single most important correctness
  property of the backtest engine — double-check it whenever touching
  `backtest_engine.py`.
- **Every position has a stop loss.** No code path may open a position without a
  computed, valid SL. If SL calculation fails, skip the trade (log + continue), never
  open unprotected.
- **Fail fast on config errors.** Invalid/missing/inconsistent ENV values must raise a
  clear error at startup, before connecting to MT5 or starting any loop — not fail
  halfway through a run.
- **Never commit secrets.** `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` come from `.env`
  only. `.env` must be in `.gitignore`. Provide a `.env.example` with all SCHEMA.md
  variables and placeholder/empty values.
- **Prefer explicit over clever.** This is a personal trading bot handling real orders
  eventually — favor readable, explicit code over dense one-liners, especially in
  `risk_manager.py` and `order_executor.py`.

## 3. Build Order (mirrors PRD.md §9)

Implement and get each layer working (with basic tests/manual checks) before moving to
the next — don't jump straight to the live engine:

1. `config.py` — loader + validation.
2. `mt5_client.py`, `data_feed.py` — connection + candle fetching, verify against a real
   MT5 terminal with a manual script before building anything on top.
3. `indicators.py` — MA + cross detection, unit tests with synthetic series.
4. `strategy.py` — signal evaluation, unit tests with fixture DataFrames covering: clean
   BUY signal, clean SELL signal, cross without trend agreement (no signal), trend
   agreement without cross (no signal), insufficient history (no signal).
5. `risk_manager.py` — sizing/SL/TP math, unit tests for both sizing modes and the
   "reject below min lot" path.
6. `order_executor.py` — `BacktestOrderExecutor` first (no live risk), then
   `LiveOrderExecutor`.
7. `backtest_engine.py` — wire it up, run against a real historical range, sanity-check
   the trade log and equity curve by hand for a small date range before trusting larger
   runs.
8. `reporting.py` — metrics + report files.
9. `live_engine.py` — only after backtest engine is verified correct. Start with a demo
   MT5 account, never a live/funded account, until behavior is confirmed over multiple
   sessions.
10. `main.py` — wire the `MODE` dispatch last, once both engines work standalone.

## 4. What NOT to Do

- Don't add strategy features not in RULES.md (extra filters, session windows, news
  avoidance, multi-symbol logic) unless explicitly asked — flag them as suggestions
  instead of silently adding them.
- Don't hardcode MT5 timeframe constants, symbol names, or point-value math outside
  `data_feed.py` / `risk_manager.py` as specified in ARCHITECTURE.md.
- Don't let `backtest_engine.py` and `live_engine.py` diverge in how they call
  `strategy.evaluate_signal` — if you find yourself writing signal logic twice, stop and
  refactor back into `strategy.py`.
- Don't skip the "no unprotected position" and "no look-ahead" invariants for the sake of
  a quick prototype — these are correctness requirements, not polish.

## 5. When Requirements Are Ambiguous

If PRD.md / RULES.md / ARCHITECTURE.md / DESIGN.md / SCHEMA.md don't cover something
needed to proceed (e.g. exact behavior when a trend timeframe has a data gap, or how to
handle a broker that rejects a lot size mid-request), make the most conservative choice
(skip the trade / log and continue, never guess into a live order), note the assumption
in code comments, and surface it back to Wal rather than treating it as settled.
