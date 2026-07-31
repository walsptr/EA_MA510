# DESIGN.md — Detailed Design

This document translates ARCHITECTURE.md and RULES.md into concrete function/class
signatures and algorithms. It is the level of detail an AI coding agent should implement
directly against.

## 1. Config (`config.py`)

```python
@dataclass(frozen=True)
class Config:
    mode: Literal["BACKTEST", "LIVE"]

    # Symbol & timeframes
    symbol: str
    entry_timeframe: str        # "M1","M5","M15","M30","H1","H4","D1"
    trend_timeframe_1: str
    trend_timeframe_2: str

    # MA settings
    ma_low: int
    ma_high: int
    ma_type: Literal["SMA", "EMA"]

    # Entry trend MA filter (optional, entry timeframe only)
    trend_ma_low_1: int | None
    trend_ma_high_1: int | None
    trend_ma_low_2: int | None
    trend_ma_high_2: int | None

    # Backtest range
    backtest_start_date: date | None   # required if mode == BACKTEST
    backtest_end_date: date | None

    # Risk / sizing
    sizing_mode: Literal["FIXED_LOT", "RISK_PERCENT"]
    fixed_lot_size: float | None
    risk_percent_per_trade: float | None

    sl_mode: Literal["FIXED", "ATR", "DOLLAR"]
    sl_points: float | None
    sl_atr_multiplier: float | None
    sl_dollar: float | None
    tp_mode: Literal["FIXED", "ATR", "DOLLAR"]
    tp_points: float | None
    tp_atr_multiplier: float | None
    tp_dollar: float | None
    atr_period: int

    trailing_stop_enabled: bool
    trailing_stop_points: float | None
    trailing_stop_activation_points: float | None

    exit_on_opposite_signal: bool
    max_concurrent_positions: int
    max_spread_points: float | None
    max_daily_loss_percent: float | None

    magic_number: int
    live_poll_interval_seconds: int

    # MT5 credentials (LIVE only, optional if terminal already logged in)
    mt5_login: int | None
    mt5_password: str | None
    mt5_server: str | None
    mt5_terminal_path: str | None
```

`load_config() -> Config`:
1. Load `.env` if present.
2. Read every var, cast to correct type, apply defaults from SCHEMA.md where allowed.
3. Validate (raise `ConfigError` with a clear message, don't silently default):
   - `ma_low < ma_high`.
   - `entry_timeframe`, `trend_timeframe_1/2` are valid MT5 timeframe strings.
   - if `mode == BACKTEST`: `backtest_start_date` and `backtest_end_date` present and
     `start < end`.
   - if `sizing_mode == RISK_PERCENT`: `risk_percent_per_trade` present and in `(0, 100]`.
   - if `sizing_mode == FIXED_LOT`: `fixed_lot_size` present and `> 0`.
   - SL/TP mode-specific required fields present depending on mode:
     - If `SL_MODE=FIXED`: `sl_points` is required and must be > 0.
     - If `SL_MODE=ATR`: `sl_atr_multiplier` is required and must be > 0.
     - If `SL_MODE=DOLLAR`: `sl_dollar` is required and must be > 0.
     - If `TP_MODE=FIXED`: `tp_points` is required and must be > 0.
     - If `TP_MODE=ATR`: `tp_atr_multiplier` is required and must be > 0.
     - If `TP_MODE=DOLLAR`: `tp_dollar` is required and must be > 0.
4. Return the frozen `Config`.

## 2. Indicators (`indicators.py`)

```python
def moving_average(close: pd.Series, period: int, ma_type: str) -> pd.Series:
    if ma_type == "SMA":
        return close.rolling(window=period).mean()
    elif ma_type == "EMA":
        return close.ewm(span=period, adjust=False).mean()
    raise ValueError(f"Unknown ma_type: {ma_type}")

class CrossState(Enum):
    NONE = "none"
    CROSS_UP = "cross_up"
    CROSS_DOWN = "cross_down"

def detect_cross(ma_low: pd.Series, ma_high: pd.Series) -> CrossState:
    """Evaluates only the last two values (latest closed bar vs previous)."""
    if len(ma_low) < 2 or ma_low.iloc[-2:].isna().any() or ma_high.iloc[-2:].isna().any():
        return CrossState.NONE
    prev_diff = ma_low.iloc[-2] - ma_high.iloc[-2]
    curr_diff = ma_low.iloc[-1] - ma_high.iloc[-1]
    if prev_diff <= 0 and curr_diff > 0:
        return CrossState.CROSS_UP
    if prev_diff >= 0 and curr_diff < 0:
        return CrossState.CROSS_DOWN
    return CrossState.NONE

def trend_direction(ma_low: pd.Series, ma_high: pd.Series) -> Literal["BULLISH","BEARISH","FLAT"]:
    if ma_low.iloc[-1] > ma_high.iloc[-1]:
        return "BULLISH"
    if ma_low.iloc[-1] < ma_high.iloc[-1]:
        return "BEARISH"
    return "FLAT"

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()
```

## 3. Strategy (`strategy.py`)

```python
@dataclass(frozen=True)
class Signal:
    direction: Literal["BUY", "SELL", "NONE"]
    reason: str            # human-readable, always populated (even for NONE, e.g. "trend timeframes disagree")
    entry_time: datetime
    entry_timeframe_close_price: float

def evaluate_signal(candles: dict[str, pd.DataFrame], cfg: Config) -> Signal:
    """
    candles keys: cfg.entry_timeframe, cfg.trend_timeframe_1, cfg.trend_timeframe_2
    Each DataFrame schema: see SCHEMA.md §4 (columns: time, open, high, low, close, ...)
    Each DataFrame must already contain only CLOSED candles up to the evaluation point
    (backtest slicing / live "latest closed" filtering happens before this call —
    strategy.py never trims data itself, keeping it a pure function of its input).
    """
    entry_df = candles[cfg.entry_timeframe]
    t1_df = candles[cfg.trend_timeframe_1]
    t2_df = candles[cfg.trend_timeframe_2]

    # warm-up guard
    min_bars = max(cfg.ma_low, cfg.ma_high) + 1
    if len(entry_df) < min_bars or len(t1_df) < min_bars or len(t2_df) < min_bars:
        return Signal("NONE", "insufficient history for MA warm-up", entry_df.iloc[-1].time, entry_df.iloc[-1].close)

    entry_ma_low = moving_average(entry_df.close, cfg.ma_low, cfg.ma_type)
    entry_ma_high = moving_average(entry_df.close, cfg.ma_high, cfg.ma_type)
    cross = detect_cross(entry_ma_low, entry_ma_high)

    entry_trend_1 = None
    entry_trend_2 = None
    if cfg.trend_ma_low_1 and cfg.trend_ma_high_1 and cfg.trend_ma_low_2 and cfg.trend_ma_high_2:
        entry_trend_1 = trend_direction(
            moving_average(entry_df.close, cfg.trend_ma_low_1, cfg.ma_type),
            moving_average(entry_df.close, cfg.trend_ma_high_1, cfg.ma_type),
        )
        entry_trend_2 = trend_direction(
            moving_average(entry_df.close, cfg.trend_ma_low_2, cfg.ma_type),
            moving_average(entry_df.close, cfg.trend_ma_high_2, cfg.ma_type),
        )

    t1_trend = trend_direction(
        moving_average(t1_df.close, cfg.ma_low, cfg.ma_type),
        moving_average(t1_df.close, cfg.ma_high, cfg.ma_type),
    )
    t2_trend = trend_direction(
        moving_average(t2_df.close, cfg.ma_low, cfg.ma_type),
        moving_average(t2_df.close, cfg.ma_high, cfg.ma_type),
    )

    last = entry_df.iloc[-1]

    if cross == CrossState.CROSS_UP and t1_trend == "BULLISH" and t2_trend == "BULLISH":
        if entry_trend_1 and entry_trend_2 and not (entry_trend_1 == "BULLISH" and entry_trend_2 == "BULLISH"):
            return Signal("NONE", "entry trend MA gate blocked", last.time, last.close)
        return Signal("BUY", "cross_up + both trend timeframes bullish", last.time, last.close)

    if cross == CrossState.CROSS_DOWN and t1_trend == "BEARISH" and t2_trend == "BEARISH":
        if entry_trend_1 and entry_trend_2 and not (entry_trend_1 == "BEARISH" and entry_trend_2 == "BEARISH"):
            return Signal("NONE", "entry trend MA gate blocked", last.time, last.close)
        return Signal("SELL", "cross_down + both trend timeframes bearish", last.time, last.close)

    return Signal("NONE", f"no aligned signal (cross={cross.value}, t1={t1_trend}, t2={t2_trend})", last.time, last.close)
```

## 4. Risk Manager (`risk_manager.py`)

```python
@dataclass(frozen=True)
class TradePlan:
    direction: Literal["BUY", "SELL"]
    lot_size: float
    sl_price: float
    tp_price: float

def compute_trade_plan(signal: Signal, cfg: Config, symbol_info: SymbolInfo,
                        account_equity: float, atr_value: float | None) -> TradePlan | None:
    """Returns None if the computed lot size is below the broker minimum (reject trade)."""
    point = symbol_info.point
    entry_price = signal.entry_timeframe_close_price

    # --- Compute sl_distance (3 modes: ATR / FIXED / DOLLAR) ---
    if cfg.sl_mode == "ATR":
        sl_distance = cfg.sl_atr_multiplier * atr_value
    elif cfg.sl_mode == "FIXED":
        sl_distance = cfg.sl_points * point
    elif cfg.sl_mode == "DOLLAR":
        # We need the lot size first. For FIXED_LOT: use cfg.fixed_lot_size directly.
        # For RISK_PERCENT: treat SL_DOLLAR as a fixed risk amount, compute lot so total risk = SL_DOLLAR.
        # value_per_point_per_lot = symbol_info.trade_tick_value / symbol_info.trade_tick_size * point
        # sl_distance_in_points = sl_dollar / (preliminary_lot * value_per_point_per_lot)
        # sl_distance = sl_distance_in_points * point
        value_per_point_per_lot = symbol_info.trade_tick_value / symbol_info.trade_tick_size * point
        if cfg.sizing_mode == "FIXED_LOT":
            preliminary_lot = cfg.fixed_lot_size
        else:
            # RISK_PERCENT + SL_DOLLAR: SL_DOLLAR is a fixed risk amount.
            # Use a preliminary_lot targeting risk=sl_dollar at 1 point SL, then
            # use it to compute sl_distance_in_points (two-pass approximation).
            preliminary_lot = cfg.sl_dollar / value_per_point_per_lot
        sl_distance_in_points = cfg.sl_dollar / (preliminary_lot * value_per_point_per_lot)
        sl_distance = sl_distance_in_points * point

    # --- Compute tp_distance (3 modes: ATR / FIXED / DOLLAR) ---
    if cfg.tp_mode == "ATR":
        tp_distance = cfg.tp_atr_multiplier * atr_value
    elif cfg.tp_mode == "FIXED":
        tp_distance = cfg.tp_points * point
    elif cfg.tp_mode == "DOLLAR":
        # (do the same for tp_distance with tp_dollar)
        value_per_point_per_lot = symbol_info.trade_tick_value / symbol_info.trade_tick_size * point
        if cfg.sizing_mode == "FIXED_LOT":
            preliminary_lot = cfg.fixed_lot_size
        else:
            # RISK_PERCENT + TP_DOLLAR: use tp_dollar as the basis for preliminary_lot
            preliminary_lot = cfg.tp_dollar / value_per_point_per_lot
        tp_distance_in_points = cfg.tp_dollar / (preliminary_lot * value_per_point_per_lot)
        tp_distance = tp_distance_in_points * point

    if signal.direction == "BUY":
        sl_price = entry_price - sl_distance
        tp_price = entry_price + tp_distance
    else:
        sl_price = entry_price + sl_distance
        tp_price = entry_price - tp_distance

    if cfg.sizing_mode == "FIXED_LOT":
        lot = cfg.fixed_lot_size
    else:
        # RISK_PERCENT: if SL_MODE=DOLLAR then sl_dollar is a fixed risk amount;
        # otherwise use a percentage of equity as usual.
        if cfg.sl_mode == "DOLLAR":
            risk_amount = cfg.sl_dollar
        else:
            risk_amount = account_equity * (cfg.risk_percent_per_trade / 100)
        value_per_point_per_lot = symbol_info.trade_tick_value / symbol_info.trade_tick_size * point
        lot = risk_amount / (sl_distance / point * value_per_point_per_lot)

    lot = round_to_step(lot, symbol_info.volume_step, symbol_info.volume_min, symbol_info.volume_max)
    if lot < symbol_info.volume_min:
        return None

    return TradePlan(signal.direction, lot, sl_price, tp_price)
```

## 5. Order Executor (`order_executor.py`)

Common interface:

```python
class OrderExecutor(Protocol):
    def open_position(self, plan: TradePlan, cfg: Config, at_time: datetime) -> TradeResult: ...
    def close_position(self, position_id: int, at_time: datetime, price: float, reason: str) -> TradeResult: ...
    def get_open_positions(self) -> list[Position]: ...
    def update_trailing_stops(self, current_price: float) -> None: ...
```

- `LiveOrderExecutor` implements this using `MetaTrader5.order_send` (`TRADE_ACTION_DEAL`
  for opens, `TRADE_ACTION_SLTP`/close deal for exits), with `magic=cfg.magic_number`,
  retries on requote/timeout per MT5 result codes.
- `BacktestOrderExecutor` maintains an in-memory list of `Position` objects, an equity
  curve list, and a trade log list. On each new bar it checks whether high/low breached
  SL/TP and closes accordingly (SL checked before TP if both are breached in the same bar,
  to be conservative). Every fill and close appends a row to the trade log
  (see SCHEMA.md §5).

## 6. Backtest Engine (`backtest_engine.py`)

Algorithm:
```
history = { tf: data_feed.get_history(symbol, tf, start, end) for tf in required_timeframes }
executor = BacktestOrderExecutor(starting_balance)

for i, bar in enumerate(history[entry_timeframe]):
    if i < warmup_bars: continue

    entry_slice = history[entry_timeframe][: i+1]
    t1_slice = slice_up_to_time(history[trend_tf_1], bar.time)   # no look-ahead
    t2_slice = slice_up_to_time(history[trend_tf_2], bar.time)

    executor.update_trailing_stops(bar.close)
    executor.check_sl_tp_hits(bar)   # may close open positions this bar

    if executor.balance <= 0:
        break

    signal = strategy.evaluate_signal({entry_tf: entry_slice, trend_tf_1: t1_slice, trend_tf_2: t2_slice}, cfg)

    if signal.direction != "NONE":
        if cfg.exit_on_opposite_signal:
            executor.close_opposite_positions(signal.direction, bar)
        if executor.can_open_new_position(signal.direction, cfg.max_concurrent_positions):
            plan = risk_manager.compute_trade_plan(signal, cfg, symbol_info, executor.equity, atr_value)
            if plan:
                executor.open_position(plan, cfg, bar.time)

reporting.generate_report(executor.trade_log, executor.equity_curve, output_dir)
```

`slice_up_to_time(df, t)` returns all candles whose **close time** ≤ `t` (RULES.md §8 —
this is the look-ahead guard).

## 7. Live Engine (`live_engine.py`)

Algorithm:
```
mt5_client.connect(cfg)
last_processed_entry_candle_time = None

while True:
    if account_balance() <= 0 or account_equity() <= 0:
        break

    candles = { tf: data_feed.get_latest(symbol, tf, n=warmup_bars + buffer) for tf in required_timeframes }
    latest_entry_candle = candles[entry_timeframe].iloc[-1]

    executor.update_trailing_stops(current_tick_price)
    executor.check_daily_loss_breaker(cfg)

    if latest_entry_candle.time != last_processed_entry_candle_time:
        signal = strategy.evaluate_signal(candles, cfg)
        logger.info(signal)
        if signal.direction != "NONE":
            if executor.can_open_new_position(signal.direction, cfg.max_concurrent_positions):
                if current_spread() <= cfg.max_spread_points:
                    plan = risk_manager.compute_trade_plan(signal, cfg, symbol_info, account_equity(), atr_value)
                    if plan:
                        executor.open_position(plan, cfg, now())
        last_processed_entry_candle_time = latest_entry_candle.time

    sleep(cfg.live_poll_interval_seconds)
```

Reconnect handling: wrap the loop body in try/except around MT5 calls; on failure, log,
call `mt5_client.reconnect()` with exponential backoff (cap e.g. 60s), and continue the
loop without crashing the process.

## 8. Error Handling Conventions

- Config errors → raise and exit immediately (before connecting to MT5 or starting any
  loop).
- MT5 API errors (connection, data fetch, order send) → caught, logged with the MT5
  error code/description, and handled per-context (retry for connection/data, log +
  skip-this-cycle for a single failed order send — never crash the whole process on a
  single failed order).
- Capital exhaustion stop guard:
  - Backtest: if virtual `balance <= 0`, stop the run immediately.
  - Live: if `balance <= 0` OR `equity <= 0`, stop the main loop immediately.
  - Live: if an order is rejected due to insufficient funds / insufficient margin, stop the main loop immediately.
- Strategy/indicator errors (e.g. malformed candle data) → treated as "no signal this
  cycle", logged as a warning, loop continues.

## 9. Testing Notes

- `strategy.evaluate_signal` must be unit-testable with hand-built `pd.DataFrame`
  fixtures (no MT5 dependency) — this is the most important test surface, since it's
  shared by both modes.
- `indicators.detect_cross` and `indicators.trend_direction` should have dedicated unit
  tests covering: no cross, cross up, cross down, flat/equal MA edge case, insufficient
  data.
- `risk_manager.compute_trade_plan` should be tested for both `FIXED_LOT` and
  `RISK_PERCENT` sizing modes, and for the "lot below broker minimum → None" path.
