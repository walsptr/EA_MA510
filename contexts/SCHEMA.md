# SCHEMA.md — Configuration & Data Schemas

## 1. Environment Variables — Full Reference

### 1.1 Mode & Symbol

| Var | Type | Required | Default | Notes |
|---|---|---|---|---|
| `MODE` | `BACKTEST` \| `LIVE` | yes | — | Selects the runner. |
| `SYMBOL` | string | yes | — | Broker-specific symbol name, e.g. `XAUUSDm`. |

### 1.2 Timeframes

| Var | Type | Required | Default | Notes |
|---|---|---|---|---|
| `ENTRY_TIMEFRAME` | enum | yes | — | One of `M1,M5,M15,M30,H1,H4,D1`. |
| `TREND_TIMEFRAME_1` | enum | yes | — | Same enum as above. |
| `TREND_TIMEFRAME_2` | enum | yes | — | Same enum as above. |

### 1.3 Moving Average

| Var | Type | Required | Default | Notes |
|---|---|---|---|---|
| `MA_LOW` | int | yes | — | Must be `> 0` and `< MA_HIGH`. |
| `MA_HIGH` | int | yes | — | Must be `> MA_LOW`. |
| `MA_TYPE` | `SMA` \| `EMA` | no | `EMA` | |

### 1.3.1 Entry Trend MA Filter (optional, entry timeframe only)

When enabled, BUY/SELL signals on `ENTRY_TIMEFRAME` are only valid if one or more additional MA trend
pairs on `ENTRY_TIMEFRAME` also align with the entry direction. MA type follows `MA_TYPE`.

| Var | Type | Required | Default | Notes |
|---|---|---|---|---|
| `TREND_MA_LOW_1` | int | optional | none | Pair 1. If set, `TREND_MA_HIGH_1` must also be set. Must be `> 0` and `< TREND_MA_HIGH_1`. |
| `TREND_MA_HIGH_1` | int | optional | none | Pair 1. If set, `TREND_MA_LOW_1` must also be set. Must be `> 0` and `> TREND_MA_LOW_1`. |
| `TREND_MA_LOW_2` | int | optional | none | Pair 2. If set, `TREND_MA_HIGH_2` must also be set. Must be `> 0` and `< TREND_MA_HIGH_2`. |
| `TREND_MA_HIGH_2` | int | optional | none | Pair 2. If set, `TREND_MA_LOW_2` must also be set. Must be `> 0` and `> TREND_MA_LOW_2`. |

### 1.4 Backtest Range

| Var | Type | Required | Default | Notes |
|---|---|---|---|---|
| `BACKTEST_START_DATE` | `YYYY-MM-DD` | required if `MODE=BACKTEST` | — | |
| `BACKTEST_END_DATE` | `YYYY-MM-DD` | required if `MODE=BACKTEST` | — | Must be after start date. |
| `BACKTEST_WARMUP_DAYS` | int | no | `0` | Extra days fetched before `BACKTEST_START_DATE` to warm up indicators (MA/ATR). Trading still starts at `BACKTEST_START_DATE`. |
| `BACKTEST_INITIAL_BALANCE` | float | no | `1000` | Starting virtual balance for equity curve/sizing. Must be `> 0`. |
| `BACKTEST_SPREAD_POINTS` | float | no | `0` (use live spread if available) | Simulated spread applied to fills. |
| `BACKTEST_SLIPPAGE_POINTS` | float | no | `0` | Simulated slippage applied to fills. |
| `BACKTEST_USE_MT5` | bool | no | Windows: `true`, non-Windows: `false` | If `true`, fetch real historical data from an MT5 terminal. If `false`, use synthetic data. |

### 1.5 Position Sizing

| Var | Type | Required | Default | Notes |
|---|---|---|---|---|
| `SIZING_MODE` | `FIXED_LOT` \| `RISK_PERCENT` | no | `FIXED_LOT` | |
| `FIXED_LOT_SIZE` | float | required if `SIZING_MODE=FIXED_LOT` | `0.01` | |
| `RISK_PERCENT_PER_TRADE` | float (0–100) | required if `SIZING_MODE=RISK_PERCENT` | — | |

### 1.6 Stop Loss / Take Profit

| Var | Type | Required | Default | Notes |
|---|---|---|---|---|
| `SL_MODE` | `FIXED` \| `ATR` \| `DOLLAR` | no | `FIXED` | |
| `SL_POINTS` | float | required if `SL_MODE=FIXED` | — | In broker points. |
| `SL_ATR_MULTIPLIER` | float | required if `SL_MODE=ATR` | — | |
| `SL_DOLLAR` | float | required if `SL_MODE=DOLLAR` | — | Absolute dollar amount per position (not per lot). Must be > 0. |
| `TP_MODE` | `FIXED` \| `ATR` \| `DOLLAR` | no | `FIXED` | |
| `TP_POINTS` | float | required if `TP_MODE=FIXED` | — | |
| `TP_ATR_MULTIPLIER` | float | required if `TP_MODE=ATR` | — | |
| `TP_DOLLAR` | float | required if `TP_MODE=DOLLAR` | — | Absolute dollar amount per position (not per lot). Must be > 0. |
| `ATR_PERIOD` | int | no | `14` | Used when either SL or TP mode is `ATR`. |

### 1.7 Trailing Stop (optional)

| Var | Type | Required | Default | Notes |
|---|---|---|---|---|
| `TRAILING_STOP_ENABLED` | bool | no | `false` | |
| `TRAILING_STOP_POINTS` | float | required if enabled | — | |
| `TRAILING_STOP_ACTIVATION_POINTS` | float | required if enabled | — | Profit distance before trailing starts. |

### 1.8 Trade Management

| Var | Type | Required | Default | Notes |
|---|---|---|---|---|
| `EXIT_ON_OPPOSITE_SIGNAL` | bool | no | `false` | |
| `TRADING_WINDOW_START` | `HH:MM` | no | none (disabled) | Entry window start time, interpreted in `DISPLAY_TIMEZONE`. |
| `TRADING_WINDOW_END` | `HH:MM` | no | none (disabled) | Entry window end time, interpreted in `DISPLAY_TIMEZONE`. Supports crossing midnight when START > END. |
| `MAX_CONCURRENT_POSITIONS` | int | no | `1` | Per direction or total — implementation must document which; recommended: total open positions for `SYMBOL` opened by this bot's `MAGIC_NUMBER`. |
| `MAX_SPREAD_POINTS` | float | no | none (no guard) | Live mode entry guard. |
| `MAX_DAILY_LOSS_PERCENT` | float | no | none (no breaker) | Live mode circuit breaker. |
| `MAGIC_NUMBER` | int | no | `20260101` | Identifies this bot's orders. |

### 1.9 Live Mode / MT5 Connection

| Var | Type | Required | Default | Notes |
|---|---|---|---|---|
| `LIVE_POLL_INTERVAL_SECONDS` | int | no | `5` | |
| `LIVE_WARMUP_DAYS` | int | no | `0` | If > 0, LIVE fetches candles using a day-based lookback (per timeframe) to warm up indicators after startup. |
| `MT5_LOGIN` | int | no (if terminal already logged in) | — | |
| `MT5_PASSWORD` | string | no | — | Never logged, never committed. |
| `MT5_SERVER` | string | no | — | |
| `MT5_TERMINAL_PATH` | string | no | — | Path to `terminal64.exe` if not on default path. |

### 1.10 Logging / Output

| Var | Type | Required | Default | Notes |
|---|---|---|---|---|
| `LOG_LEVEL` | `DEBUG`\|`INFO`\|`WARNING`\|`ERROR` | no | `INFO` | |
| `LOG_DIR` | string | no | `./logs` | |
| `REPORT_DIR` | string | no | `./reports` | Backtest output location. |
| `DISPLAY_TIMEZONE` | string | no | `UTC` | IANA timezone name for report/log display. Examples: `UTC`, `Asia/Jakarta`. |

### 1.11 Example `.env`

```env
MODE=BACKTEST

SYMBOL=XAUUSDm
ENTRY_TIMEFRAME=M5
TREND_TIMEFRAME_1=M15
TREND_TIMEFRAME_2=M30

MA_LOW=5
MA_HIGH=10
MA_TYPE=EMA

BACKTEST_START_DATE=2025-01-01
BACKTEST_END_DATE=2025-12-31
BACKTEST_INITIAL_BALANCE=1000
BACKTEST_SPREAD_POINTS=20
BACKTEST_SLIPPAGE_POINTS=5

SIZING_MODE=RISK_PERCENT
RISK_PERCENT_PER_TRADE=1

# SL_MODE=ATR
# SL_ATR_MULTIPLIER=1.5
# TP_MODE=ATR
# TP_ATR_MULTIPLIER=2.5
SL_MODE=DOLLAR
SL_DOLLAR=5.0
TP_MODE=DOLLAR
TP_DOLLAR=15.0
ATR_PERIOD=14

TRAILING_STOP_ENABLED=false

EXIT_ON_OPPOSITE_SIGNAL=false
MAX_CONCURRENT_POSITIONS=1
MAX_SPREAD_POINTS=50
MAX_DAILY_LOSS_PERCENT=5
MAGIC_NUMBER=20260130

LIVE_POLL_INTERVAL_SECONDS=5
MT5_LOGIN=
MT5_PASSWORD=
MT5_SERVER=
MT5_TERMINAL_PATH=

LOG_LEVEL=INFO
LOG_DIR=./logs
REPORT_DIR=./reports
DISPLAY_TIMEZONE=UTC

# Trading window (optional)
# TRADING_WINDOW_START=07:00
# TRADING_WINDOW_END=16:00
```

## 2. Timeframe Enum → MT5 Constant Mapping

| ENV string | MetaTrader5 constant |
|---|---|
| `M1` | `mt5.TIMEFRAME_M1` |
| `M5` | `mt5.TIMEFRAME_M5` |
| `M15` | `mt5.TIMEFRAME_M15` |
| `M30` | `mt5.TIMEFRAME_M30` |
| `H1` | `mt5.TIMEFRAME_H1` |
| `H4` | `mt5.TIMEFRAME_H4` |
| `D1` | `mt5.TIMEFRAME_D1` |

This mapping lives in `data_feed.py` (or a small `timeframes.py` constant module) —
never hardcode the MT5 integer constant elsewhere.

## 3. Config Validation Rules (summary — see DESIGN.md §1 for the loader algorithm)

- `MA_LOW < MA_HIGH`, both `> 0`.
- `TREND_MA` pairs are optional. If any value within a pair is set, the other value in the pair must also be set; each must be `> 0` and `low < high`.
- `ENTRY_TIMEFRAME`, `TREND_TIMEFRAME_1`, `TREND_TIMEFRAME_2` ∈ the enum in §2.
- If `MODE=BACKTEST`: `BACKTEST_START_DATE < BACKTEST_END_DATE`, both valid dates.
- If `MODE=BACKTEST`: `BACKTEST_INITIAL_BALANCE > 0`.
- Sizing/SL/TP conditional-required fields per §1.5–1.6.
- If `SL_MODE=DOLLAR` then `SL_DOLLAR` is required and must be `> 0`.
- If `TP_MODE=DOLLAR` then `TP_DOLLAR` is required and must be `> 0`.
- If `TRAILING_STOP_ENABLED=true`: both trailing fields required.
- `MAX_CONCURRENT_POSITIONS >= 1`.

## 4. Candle DataFrame Schema

Returned by `data_feed.py` for every timeframe, used throughout `strategy.py`,
`indicators.py`, and the engines:

| Column | Type | Notes |
|---|---|---|
| `time` | `datetime64[ns, UTC]` | Candle **open** time. |
| `close_time` | `datetime64[ns, UTC]` | Candle close time = `time + timeframe_duration`. Used for no-look-ahead slicing. |
| `open` | float | |
| `high` | float | |
| `low` | float | |
| `close` | float | |
| `tick_volume` | int | From MT5 `tick_volume`. |
| `spread` | int | From MT5, points. |

Sorted ascending by `time`. Index is a plain `RangeIndex` (not datetime-indexed) so that
`.iloc[-1]` reliably means "latest closed candle" in both engines.

## 5. Trade Log Schema (backtest output, also usable for live trade history export)

CSV/DB table `trades`:

| Column | Type | Notes |
|---|---|---|
| `trade_id` | int | Auto-increment. |
| `symbol` | string | |
| `direction` | `BUY`\|`SELL` | |
| `open_time` | datetime | In `trades.csv`, this value is written in `DISPLAY_TIMEZONE`. |
| `open_time_hm` | string | `HH:MM` formatted time in `DISPLAY_TIMEZONE`. |
| `open_price` | float | |
| `close_time` | datetime | nullable while open. In `trades.csv`, this value is written in `DISPLAY_TIMEZONE`. |
| `close_time_hm` | string | `HH:MM` formatted time in `DISPLAY_TIMEZONE`. |
| `close_price` | float | nullable while open. |
| `lot_size` | float | |
| `sl_price` | float | |
| `tp_price` | float | |
| `close_reason` | `SL_HIT`\|`TP_HIT`\|`OPPOSITE_SIGNAL`\|`TRAILING_STOP`\|`MANUAL`\|`EOD_BACKTEST` | |
| `pnl` | float | Account currency, net of simulated spread/commission if modeled. |
| `pnl_pct_equity` | float | PnL as % of equity at open time. |
| `balance_after` | float | Running balance after this trade closes. |
| `signal_reason` | string | Copied from `Signal.reason` at open time, for auditability. |
| `magic_number` | int | |

## 6. Backtest Report Output

Written to `REPORT_DIR/<run_timestamp>/`:

- `trades.csv` — full trade log (schema §5).
- `equity_curve.csv` — columns: `time`, `balance`, `equity`, `drawdown_pct`.
- `summary.json` — aggregate metrics:

```json
{
  "config_snapshot": { "...": "full resolved Config as dict, for reproducibility" },
  "total_trades": 0,
  "win_rate_pct": 0.0,
  "profit_factor": 0.0,
  "total_return_pct": 0.0,
  "max_drawdown_pct": 0.0,
  "expectancy_per_trade": 0.0,
  "average_win": 0.0,
  "average_loss": 0.0,
  "largest_win": 0.0,
  "largest_loss": 0.0,
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD"
}
```

## 7. Live Position State (in-memory / optional persistence)

If persisted across restarts (recommended for `MAX_CONCURRENT_POSITIONS` accuracy and the
daily-loss breaker), store in a local SQLite table `open_positions` mirroring the fields
of the trade log (§5) with `close_time`/`close_price`/`close_reason`/`pnl` left null while
open, plus:

| Column | Type | Notes |
|---|---|---|
| `mt5_ticket` | int | MT5 order/position ticket, for reconciliation on restart. |
| `last_processed_entry_candle_time` | datetime | Persisted so a restart doesn't re-evaluate/duplicate a signal already acted on. |

## 8. Log Line Schema (structured logging)

Each log line (JSON-lines recommended) should include at minimum:

```json
{
  "timestamp": "ISO8601",
  "level": "INFO",
  "mode": "LIVE",
  "symbol": "XAUUSDm",
  "event": "signal_evaluated | order_sent | order_result | position_closed | error | reconnect",
  "detail": { "...": "event-specific fields" }
}
```
