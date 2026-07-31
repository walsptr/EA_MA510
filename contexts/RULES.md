# RULES.md — Strategy Rules (MA Cross + Multi-Timeframe Trend Filter)

This document is the single source of truth for **trading logic**. Any ambiguity in
ARCHITECTURE.md or DESIGN.md defers to this file. All parameters referenced here map
1:1 to ENV variables defined in SCHEMA.md.

## 1. Core Concept

- Trade only in the direction of the higher-timeframe trend.
- Use two moving averages (`MA_LOW` period, `MA_HIGH` period) on the entry timeframe to
  time the actual entry, only acting on a **fresh cross** (not "MA_LOW is above MA_HIGH",
  which is a state — the trigger is the cross event itself).
- Confirm the same directional bias exists on one or more higher timeframes before
  allowing the entry-timeframe cross to be actioned.

## 2. Definitions

- **MA(period, type, timeframe)** — a moving average of the given `period` and `type`
  (`SMA` or `EMA`, from `MA_TYPE`), computed on the closed candles of `timeframe`.
- **Bullish trend on timeframe T** = `MA(MA_LOW, T) > MA(MA_HIGH, T)` on the latest closed
  candle of T.
- **Bearish trend on timeframe T** = `MA(MA_LOW, T) < MA(MA_HIGH, T)` on the latest closed
  candle of T.
- **Entry Trend MA Filter (optional)** — if either (or both) of these pairs are set:
  - Pair 1: `TREND_MA_LOW_1` + `TREND_MA_HIGH_1`
  - Pair 2: `TREND_MA_LOW_2` + `TREND_MA_HIGH_2`
  then in addition to higher-timeframe trend confirmation, entry must also align with the enabled
  entry-timeframe trend check(s) on `ENTRY_TIMEFRAME`:
  - Bullish gate (per enabled pair): `MA(TREND_MA_LOW_X) > MA(TREND_MA_HIGH_X)`
  - Bearish gate (per enabled pair): `MA(TREND_MA_LOW_X) < MA(TREND_MA_HIGH_X)`
  (MA type follows `MA_TYPE`).
- **MA Cross Up** on timeframe T at candle `i` = `MA_LOW[i-1] <= MA_HIGH[i-1]` AND
  `MA_LOW[i] > MA_HIGH[i]` (cross happened exactly on the most recently closed candle).
- **MA Cross Down** on timeframe T at candle `i` = `MA_LOW[i-1] >= MA_HIGH[i-1]` AND
  `MA_LOW[i] < MA_HIGH[i]`.
- All MA/cross checks use **closed candles only**. The currently-forming candle is never
  used for signal decisions (avoids repainting).

## 3. Entry Rules

### 3.1 BUY Entry

All of the following must be true, evaluated on the same signal-check event (i.e. a new
closed candle on `ENTRY_TIMEFRAME`):

1. **Trend confirmation**: Bullish trend is true on `TREND_TIMEFRAME_1` **and**
   `TREND_TIMEFRAME_2` (i.e. `MA_LOW > MA_HIGH` on both, using each timeframe's own latest
   closed candle).
2. **Entry trigger**: An **MA Cross Up** occurred on `ENTRY_TIMEFRAME` on the latest closed
   candle.
3. **Entry trend MA gate (optional)**: if one or both `TREND_MA` pairs are enabled, then all enabled
   entry-timeframe trend MA checks must be bullish.
4. No existing open position for `SYMBOL` in the BUY direction (respect
   `MAX_CONCURRENT_POSITIONS`, see SCHEMA.md).

If all conditions hold → open a BUY position.

### 3.2 SELL Entry

All of the following must be true:

1. **Trend confirmation**: Bearish trend is true on `TREND_TIMEFRAME_1` **and**
   `TREND_TIMEFRAME_2` (`MA_LOW < MA_HIGH` on both).
2. **Entry trigger**: An **MA Cross Down** occurred on `ENTRY_TIMEFRAME` on the latest
   closed candle.
3. **Entry trend MA gate (optional)**: if one or both `TREND_MA` pairs are enabled, then all enabled
   entry-timeframe trend MA checks must be bearish.
4. No existing open position for `SYMBOL` in the SELL direction.

If all conditions hold → open a SELL position.

### 3.3 Notes on trend timeframes

- v1 ships with exactly two trend timeframes (`TREND_TIMEFRAME_1`, `TREND_TIMEFRAME_2`),
  both must agree with the entry direction (logical AND, not majority vote).
- The design must allow a future `TREND_TIMEFRAMES` list (comma-separated, e.g.
  `M15,M30,H1`) with an ALL-must-agree rule, without changing the strategy function
  signature (see DESIGN.md §3). Until that's implemented, `TREND_TIMEFRAME_1/2` are the
  contract.
- Trend timeframe MAs use the **same** `MA_LOW`/`MA_HIGH`/`MA_TYPE` parameters as the
  entry timeframe. (If per-timeframe MA periods are needed later, that's a v2 change and
  must be reflected in SCHEMA.md first.)

## 4. Exit Rules (v1)

1. **Stop Loss** — mandatory on every position. Computed either as:
   - Fixed distance in points (`SL_POINTS`), or
   - ATR-based (`SL_ATR_MULTIPLIER` × ATR(`ATR_PERIOD`) on `ENTRY_TIMEFRAME`), or
   - Dollar-based (`SL_DOLLAR` absolute dollar amount per position, converted to a price distance using symbol info: trade_tick_value, trade_tick_size, point),
     selected via `SL_MODE` (`FIXED` / `ATR` / `DOLLAR`).
2. **Take Profit** — mandatory on every position. Computed either as:
   - Fixed distance in points (`TP_POINTS`), or
   - ATR-based (`TP_ATR_MULTIPLIER` × ATR(`ATR_PERIOD`) on `ENTRY_TIMEFRAME`), or
   - Dollar-based (`TP_DOLLAR` absolute dollar amount per position, converted to a price distance using symbol info: trade_tick_value, trade_tick_size, point),
     selected via `TP_MODE` (`FIXED` / `ATR` / `DOLLAR`).
3. **Opposite signal exit (optional, `EXIT_ON_OPPOSITE_SIGNAL=true/false`)** — if enabled,
   a valid opposite-direction entry signal closes the current open position before (or
   instead of) opening the new one.
4. **Trailing stop (optional, `TRAILING_STOP_ENABLED=true/false`)** — if enabled, trail by
   `TRAILING_STOP_POINTS` once price has moved `TRAILING_STOP_ACTIVATION_POINTS` in favor.
5. No time-based exit in v1 (e.g. no "close at end of day") unless later added as an ENV
   toggle.

## 5. Position Sizing / Risk

1. Sizing mode via `SIZING_MODE`:
   - `FIXED_LOT` — always use `FIXED_LOT_SIZE`.
   - `RISK_PERCENT` — lot size computed so that the distance to SL corresponds to
     `RISK_PERCENT_PER_TRADE` of current account equity.
2. Respect broker's minimum/maximum lot step for `SYMBOL` (read from MT5 symbol info at
   runtime, not hardcoded).
3. Reject the trade (log + skip) if computed lot size is below the broker minimum lot
   given the account's current equity.
4. Optional `MAX_SPREAD_POINTS` guard — skip entry if current spread exceeds this value at
   signal time (protects against low-liquidity / news-spike spreads).
5. Optional `MAX_DAILY_LOSS_PERCENT` circuit breaker — if the account's realized loss for
   the current day exceeds this, stop opening new positions until the next day (live mode
   only).

## 6. Stop-Trading Guard (Capital Exhaustion / Margin Rejection)

These are hard stop conditions intended to prevent undefined behavior and repeated broker rejections.

1. **Backtest stop (virtual account)**: if the backtest running balance becomes `<= 0` at any point, the backtest must stop immediately (terminate the run and produce the report from results up to that point).
2. **Live stop (real account)**: if either account `balance <= 0` OR `equity <= 0`, the live engine must stop trading immediately (exit the main loop).
3. **Live stop (insufficient funds / margin rejection)**: if an order placement is rejected due to insufficient funds / insufficient margin, the live engine must stop trading immediately (do not keep retrying or continue the loop).

## 7. Signal Evaluation Timing

- **Live mode**: evaluate signals exactly once per newly closed `ENTRY_TIMEFRAME` candle
  (not on every tick). Detect a new closed candle by comparing the latest candle's open
  time to the last-processed open time.
- **Backtest mode**: iterate bar-by-bar in chronological order on `ENTRY_TIMEFRAME`; for
  each entry-timeframe bar close, resample/fetch the corresponding latest closed candle of
  each trend timeframe **as of that point in time** (no look-ahead — a trend timeframe
  candle can only be used once it has actually closed relative to the entry-timeframe
  bar's close time).

## 8. Look-Ahead Bias Prevention

- Backtest must never use a trend-timeframe candle whose close time is after the
  entry-timeframe candle's close time being evaluated.
- Indicator warm-up: the first usable signal on any timeframe requires at least
  `max(MA_LOW, MA_HIGH) + 1` closed candles of history on that timeframe. Bars before that
  are skipped (no signal, not a "no cross" false negative).

## 9. Symbol & Broker Considerations

- `SYMBOL` (e.g. `XAUUSDm`) — the effective tradable symbol as named by the broker; do not
  assume a canonical name, always resolve via `MetaTrader5.symbol_info(SYMBOL)`.
- Respect `SYMBOL` digits/point size when computing SL/TP distances from `SL_POINTS` /
  `TP_POINTS`.
- `MAGIC_NUMBER` tags all orders placed by this bot, so its own positions can be
  distinguished from manual/other-EA positions when scanning open positions.

## 10. Example Config → Behavior

Given:
```
MA_LOW=5
MA_HIGH=10
MA_TYPE=EMA
ENTRY_TIMEFRAME=M5
TREND_TIMEFRAME_1=M15
TREND_TIMEFRAME_2=M30
```
A BUY is opened only when: EMA5 > EMA10 on the latest closed M15 candle, AND EMA5 > EMA10
on the latest closed M30 candle, AND on the latest closed M5 candle EMA5 just crossed above
EMA10 (it was ≤ on the prior M5 candle). If any one of these three conditions is false, no
trade — the bot keeps waiting.
