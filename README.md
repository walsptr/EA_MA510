# EA MA510 — MA Cross Trend-Following Bot (MT5 / Python)

> **Rule-based Moving Average Cross EA + Multi-Timeframe Trend Filter, written in pure Python.**
> Backtest **or** Live trading with identical signal logic — single entrypoint, all tuning via `.env`.

![Tests](https://img.shields.io/badge/tests-60%20passed-brightgreen)
![Strategy](https://img.shields.io/badge/strategy-MA%20Cross%20%2B%20Trend%20Filter-blue)
![MT5](https://img.shields.io/badge/MT5-Compatible%20(Windows%20Live)-informational)
![Backtest](https://img.shields.io/badge/backtest-synthetic%20%2B%20real%20MT5%20history-informational)

---

## 🎯 Strategy (RULES.md)

This bot runs a **3-timeframe Moving Average Cross + Trend Confirmation** strategy (100% rule-based, no black-box scoring):

1. **Trend Filter (2 Higher Timeframes)** — An entry signal is only accepted if trend direction on `TREND_TIMEFRAME_1` **AND** `TREND_TIMEFRAME_2` agrees (check: `MA(MA_LOW) > MA(MA_HIGH)` for bullish, `<` for bearish).
2. **Entry Trigger (Entry Timeframe)** — A position is opened **only on a fresh cross event** where `MA(MA_LOW)` crosses `MA(MA_HIGH)` on `ENTRY_TIMEFRAME` (not the state “MA is already above”).
3. **Exit** — SL/TP per position per config, plus optional `EXIT_ON_OPPOSITE_SIGNAL=true` to close an existing position when an opposite valid signal appears.

Default example (XAUUSD, EMA 5/10):
- Entry TF: **M5** (MA Cross trigger)
- Trend TF1: **M15** and Trend TF2: **M30** (both must be bullish to allow BUY)

See [contexts/RULES.md](contexts/RULES.md) for the full, authoritative entry/exit rules.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| **⚙️ 100% Config via ENV** | All parameters (MA periods, timeframes, sizing, SL/TP, backtest range) live in `.env` — no magic numbers in code. See [contexts/SCHEMA.md](contexts/SCHEMA.md). |
| **💰 3 SL/TP Modes: FIXED / ATR / DOLLAR** | DOLLAR mode: set `SL_DOLLAR=5.0` → target **max $5 risk per position** (independent of lot size). The bot converts it to a price distance using symbol info. |
| **🧪 Synthetic Mode + Progress Log** | Backtests can run on synthetic data (`BACKTEST_USE_MT5=false`) without an MT5 terminal. Progress logs every 5% with ETA. |
| **🔀 Identical Signals: Backtest ↔ Live** | Backtest and live both call the same `evaluate_signal()` in `src/strategy.py` (no logic forks). |
| **🛡️ No Look-Ahead (Backtest Correctness)** | Any trend-TF candle used at time `t` must satisfy `close_time <= t` (enforced by `slice_up_to_time`). |
| **🔑 Every Position Has an SL** | No code path opens a position without a valid SL. If SL calculation fails → skip the trade (log + continue). |
| **🧪 Unit Test Suite** | Tests cover config, indicators, strategy, risk manager, data feed, order executor, reporting, and an end-to-end backtest. |
| **⚠️ Fail-Fast on Invalid Config** | Missing/invalid/inconsistent ENV fails early at startup (before connecting to MT5 / starting loops). |

---

## 📂 Project Structure

```
EA-MA510/
├── main.py                  # Entrypoint (the only .py file at repo root). Do not move it.
├── conftest.py              # Pytest marker (injects src.* into sys.path for tests). Do not delete it.
├── .env.example             # ENV template. Copy to .env before running.
├── .gitignore               # Ignores .env (secrets), venv, __pycache__, logs/, reports/, .trae/.
├── requirements.txt         # Minimal deps. MetaTrader5 is Windows-only and not included here.
├── AGENTS.md                # Repo rules for AI agent / contributors (read before changing code).
│
├── src/                     # All application logic (standard Python package)
│   ├── __init__.py          # Package marker (empty).
│   ├── config.py            # Loads + validates ENV. All ENV validation happens here first.
│   ├── logger.py            # Logger setup.
│   ├── indicators.py        # MA (SMA/EMA), cross detection, ATR (pure pandas/numpy).
│   ├── strategy.py          # ⭐ evaluate_signal() — PURE function (NO MT5 call, NO datetime.now, fully testable).
│   ├── risk_manager.py      # compute_trade_plan(): FIXED_LOT vs RISK_PERCENT sizing. SL/TP FIXED/ATR/DOLLAR math.
│   ├── data_feed.py         # get_history (real MT5) + generate_synthetic_candles + resample.
│   ├── mt5_client.py        # Wrapper MetaTrader5 package (connect, login, symbol_info).
│   ├── order_executor.py    # BacktestOrderExecutor + (future) LiveOrderExecutor. SL BEFORE TP conservative.
│   ├── backtest_engine.py   # Loop backtest: slice_up_to_time, signal → plan → open position, progress logging.
│   ├── reporting.py         # Summary metrics (win_rate, profit_factor, max_drawdown, expectancy) + export CSV/JSON.
│   └── live_engine.py       # Live mode: poll MT5 setiap LIVE_POLL_INTERVAL_SECONDS, eval signal tiap candle baru.
│
├── tests/                   # 10 files pytest = 60 test cases. Jalankan: python -m pytest tests/ -v
│   ├── test_config.py
│   ├── test_indicators.py
│   ├── test_strategy.py
│   ├── test_risk_manager.py
│   ├── test_data_feed.py
│   ├── test_order_executor.py
│   ├── test_backtest_engine.py
│   ├── test_reporting.py
│   ├── test_logger.py
│   └── test_e2e_backtest.py
│
└── contexts/                # ⭐ Spec source of truth — read before making strategy changes
    ├── PRD.md               # Product goals, scope, non-goals.
    ├── RULES.md             # 🚨 Strategy source of truth (entry/exit/sizing). If code disagrees, RULES.md wins.
    ├── ARCHITECTURE.md      # Module boundaries and data flow.
    ├── DESIGN.md            # Function/class signatures, pseudo-code, algorithms.
    └── SCHEMA.md            # 🚨 All ENV variables (name, type, required, defaults, validation).
```

---

## 🚀 Quick Start

### Prerequisites
- Python **3.10+**
- (Linux/macOS) You do not need MetaTrader5 — backtests can run on synthetic data.
- (Windows, for real MT5 history) Install MT5 Terminal.exe and login to a demo account first.

---

### 1) Install Dependencies (All OS)

```bash
cd EA-MA510
python -m venv .venv

# Linux / MacOS:
source .venv/bin/activate

# Windows (PowerShell):
#   .venv\Scripts\Activate.ps1

pip install -r requirements.txt
# ↑ Install: pandas, numpy, python-dotenv, pytest.
```

**(Optional, Windows only for live / real MT5 history):**
```powershell
pip install MetaTrader5   # ⚠️ WINDOWS ONLY (will fail on Linux/macOS). Synthetic backtests do not require it.
```

---

### 2) Create `.env` from Template

```bash
# Linux / MacOS:
cp .env.example .env

# Windows:
#   copy .env.example .env
```

Edit `.env` as needed (symbol, date range, sizing, SL/TP mode). See [contexts/SCHEMA.md](contexts/SCHEMA.md) for the complete ENV reference (types, required/defaults, validations).

**Minimal example (Synthetic backtest — runs on all OS):**
```env
MODE=BACKTEST
SYMBOL=XAUUSDm

ENTRY_TIMEFRAME=M5
TREND_TIMEFRAME_1=M15
TREND_TIMEFRAME_2=M30

MA_LOW=5
MA_HIGH=10
MA_TYPE=EMA

BACKTEST_START_DATE=2026-01-01
BACKTEST_END_DATE=2026-06-30
BACKTEST_INITIAL_BALANCE=1000
BACKTEST_SPREAD_POINTS=20
BACKTEST_SLIPPAGE_POINTS=5
BACKTEST_USE_MT5=false          # ← Synthetic mode, no MT5 install needed

SIZING_MODE=FIXED_LOT
FIXED_LOT_SIZE=0.1

SL_MODE=DOLLAR
SL_DOLLAR=5.0                   # Max $5 risk per position
TP_MODE=DOLLAR
TP_DOLLAR=15.0                  # $15 target per position (R:R = 1:3)
ATR_PERIOD=14

LOG_LEVEL=INFO
LOG_DIR=./logs
REPORT_DIR=./reports
```

---

### 3) Run Backtest

```bash
python main.py
```

You will see **progress logging every 5%** (example output):
```
[BACKTEST] Data siap → M5:25920 bars, M15:8640 bars, M30:4320 bars (sumber=SYNTHETIC). Loop dimulai...
[BACKTEST]   0% | bar 16/25920 | elapsed 0s | ETA ???
[BACKTEST]   5% | bar 1296/25920 | elapsed 2s | ETA 33s
[BACKTEST]  10% | bar 2592/25920 | elapsed 3s | ETA 30s
...
[BACKTEST] 100% | bar 25920/25920 | elapsed 35s
[BACKTEST] SELESAI 100% dalam 36s. 312 trade(s) tercatat.
```

After completion, the **backtest report** is written to `reports/backtest_<YYYYMMDD_HHMMSS>/`:
- `summary.json` — metrics (win rate, profit factor, max drawdown, expectancy, total return, etc.)
- `trades.csv` — full trade log (entry_time, direction, entry_price, sl, tp, close_time, close_price, pnl, etc.)
- `equity_curve.csv` — timestamp vs equity/balance

---

### 4) Live Mode (⚠️ ALWAYS START WITH A DEMO ACCOUNT)

```env
MODE=LIVE
BACKTEST_USE_MT5=true          # Not used in LIVE mode
MT5_LOGIN=463721066
MT5_PASSWORD=YourDemoPassword123
MT5_SERVER=Exness-MT5Trial17
# Opsional: MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
LIVE_POLL_INTERVAL_SECONDS=5
```

> **⚠️ SECURITY WARNING — READ BEFORE LIVE MODE:**
> 1. LIVE mode **sends orders** to the connected MT5 account. Always assume real execution.
> 2. **NEVER** use a real funded account before validating behavior for days/weeks on a **DEMO** account.
> 3. `.env` contains `MT5_LOGIN` + `MT5_PASSWORD` — it is ignored by `.gitignore`. Never commit or share it.

---

## 🧪 Run the Test Suite

```bash
# All tests:
python -m pytest tests/ -v

# Hasil expected:
# 60 passed, 0 failed, 0 errors
```

---

## ⚙️ Environment Variables — Highlights

The full list is in [contexts/SCHEMA.md](contexts/SCHEMA.md). Commonly tuned vars:

| Env | Values | Important |
|---|---|---|
| `MODE` | `BACKTEST` / `LIVE` | ✅ |
| `SYMBOL` | e.g. `XAUUSDm` (check broker-specific suffix!) | ✅ |
| `ENTRY_TIMEFRAME`, `TREND_TIMEFRAME_1`, `TREND_TIMEFRAME_2` | `M1/M5/M15/M30/H1/H4/D1` | ✅ |
| `MA_LOW`, `MA_HIGH`, `MA_TYPE` | `5 10 EMA` (default) | ✅ |
| `BACKTEST_START_DATE` / `_END_DATE` / `_INITIAL_BALANCE` | `YYYY-MM-DD` / float | ✅ BACKTEST |
| `BACKTEST_USE_MT5` | `false`=synthetic, `true`=coba MT5 history (Windows only) | |
| `SIZING_MODE` | `FIXED_LOT` / `RISK_PERCENT` | ✅ |
| `SL_MODE` / `TP_MODE` | `FIXED` / `ATR` / **`DOLLAR`** | ✅ |
| `SL_DOLLAR` / `TP_DOLLAR` | `5.0` / `15.0` → $5 risk, $15 target per position | If SL_MODE=DOLLAR |
| `MAX_CONCURRENT_POSITIONS` | `1` default | |
| `LOG_LEVEL` / `LOG_DIR` / `REPORT_DIR` | `INFO` / `./logs` / `./reports` | |

---

## 🧭 Spec Documents (Read Before Changing Strategy)

All files live in `contexts/`. If code disagrees with RULES.md/SCHEMA.md, **the documents win**.

| File | Isi |
|---|---|
| [contexts/PRD.md](contexts/PRD.md) | Product requirements: goals, scope, FR/NFR. |
| [contexts/RULES.md](contexts/RULES.md) | 🚨 Trading strategy source of truth: BUY/SELL entry, exits, filters. |
| [contexts/ARCHITECTURE.md](contexts/ARCHITECTURE.md) | Module boundaries and data flow. |
| [contexts/DESIGN.md](contexts/DESIGN.md) | Function signatures, pseudo-code, concrete algorithms. |
| [contexts/SCHEMA.md](contexts/SCHEMA.md) | 🚨 Full environment variable reference (name, type, required, defaults, validation). |
| [AGENTS.md](AGENTS.md) | Build order + ground rules for contributors. |

---

## 🛠️ Troubleshooting

| Symptom | Cause + Fix |
|---|---|
| **Config error: `BACKTEST_USE_MT5=true` on non-Windows / MetaTrader5 not installed** | The `MetaTrader5` PyPI package is **Windows-only**. Fix: run on Windows and install `MetaTrader5`, or set `BACKTEST_USE_MT5=false` for synthetic mode. |
| `pip install MetaTrader5` fails on Linux/macOS | Expected: MetaTrader5 is **Windows-only** (requires MT5 Terminal.exe). Synthetic backtests do not require it. For real MT5 history, use Windows/VPS Windows. |
| **ConfigError: XX is required** | Check your `.env` against SCHEMA.md. If `SL_MODE=DOLLAR` → `SL_DOLLAR` is required and >0. If `SIZING_MODE=RISK_PERCENT` → `RISK_PERCENT_PER_TRADE` (0-100]. |
| Backtest produces 0 trades | 1) Strict filters: trend TFs never align with MA cross. Try different MA params or use synthetic data. 2) Spread guard too strict (MAX_SPREAD_POINTS too small). |
| `.env` accidentally added to git | Do not commit. Run `git rm --cached -r .env` and verify `git status` shows it is no longer staged. |

---

## 🧱 Build Order (If You Want to Add Features)

See [AGENTS.md](AGENTS.md) §3 for the full layering. In short:

1. **Config** (ENV validation) — finish this before other layers.
2. **Data feed + indicators** — verify outputs with fixtures.
3. **Strategy** — pure + fully unit tested.
4. **Risk manager** — sizing/SL/TP math.
5. **Order executor** — BacktestExecutor first (0 risk), then Live.
6. **Backtest engine → reporting → live engine → main.py dispatch**.

> **Critical ground rules (from AGENTS.md):**
> - `strategy.py` stays pure: no MT5 calls, no file I/O, no `datetime.now()`.
> - No look-ahead in backtests: always use `slice_up_to_time()`.
> - Never open a position without a valid SL (skip the trade; do not guess).

---

## ⚖️ License

For personal / internal trading use. Strategy rules are transparent and auditable from `contexts/RULES.md`. Live trading involves substantial risk of loss — **make sure you fully understand the strategy and risks before funding a real account.**
