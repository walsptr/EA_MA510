# EA MA510 — MA Cross Trend-Following Bot (MT5 / Python)

> **Rule-based Moving Average Cross EA + Multi-Timeframe Trend Filter, written in pure Python.**
> Backtest **or** Live trading with identical signal logic — single entrypoint, all tuning via `.env`.

![Tests](https://img.shields.io/badge/tests-60%20passed-brightgreen)
![Strategy](https://img.shields.io/badge/strategy-MA%20Cross%20%2B%20Trend%20Filter-blue)
![MT5](https://img.shields.io/badge/MT5-Compatible%20(Windows%20Live)-informational)
![Backtest](https://img.shields.io/badge/backtest-synthetic%20%2B%20real%20MT5%20history-informational)

---

## 🎯 Strategi (RULES.md)

EA ini menjalankan strategi **3-Timeframe Moving Average Cross + Trend Confirmation** (100% rule-based, tidak ada black-box scoring):

1. **Trend Filter (2 Timeframe Tinggi)** — Semua sinyal entry HANYA diterima jika ARAH TREND di `TREND_TIMEFRAME_1` **DAN** `TREND_TIMEFRAME_2` **SAMA ARAH** (cek: `MA(MA_LOW) > MA(MA_HIGH)` untuk bullish, `<` untuk bearish).
2. **Entry Trigger (1 Timeframe Entry)** — Open position **HANYA pada event CROSS BARU** `MA(MA_LOW)` memotong `MA(MA_HIGH)` di `ENTRY_TIMEFRAME` (bukan state "MA sudah di atas").
3. **Exit** — SL/TP per position sesuai config, atau `EXIT_ON_OPPOSITE_SIGNAL=true` (close existing jika sinyal berlawanan muncul).

Contoh default (XAUUSD, EMA 5/10):
- Entry TF: **M5** (trigger MA Cross)
- Trend TF1: **M15** + Trend TF2: **M30** (keduanya harus bullish → baru boleh BUY)

> 📚 Lihat [contexts/RULES.md](file:///home/syawal/Project/EA-MA510/contexts/RULES.md) untuk rule entry/exit LENGKAP (sumber kebenaran trading logic).

---

## ✨ Fitur Unggulan

| Fitur | Keterangan |
|---|---|
| **⚙️ 100% Config via ENV** | Semua parameter (MA periods, TF, sizing, SL/TP, range backtest) di-file `.env` — **TIDAK ada magic number di code**. Lihat [SCHEMA.md](file:///home/syawal/Project/EA-MA510/contexts/SCHEMA.md). |
| **💰 3 SL/TP Mode: FIXED / ATR / **DOLLAR** | — `DOLLAR` mode unggulan: set `SL_DOLLAR=5.0` → **risiko MAKSIMAL $5 per posisi** (terlepas dari lot size / pair apa). Bot otomatis hitung price distance-nya. |
| **🧪 Synthetic Mode + Progress Log** | Backtest bisa pakai data **synthetic** (set `BACKTEST_USE_MT5=false`) tanpa perlu MT5 Terminal. Progress logging **setiap 5% bar** dengan ETA hitung mundur → TIDAK ada "program terasa hang". |
| **🔀 Identical Signal: Backtest ↔ Live** | Backtest dan Live memanggil **fungsi `evaluate_signal()` YANG SAMA** di `src/strategy.py` — tidak ada logic fork (menghilangkan bug "backtest bagus, live jelek karena logic beda"). |
| **🛡️ No Look-Ahead (Backtest Correctness)** | Setiap candle trend-TF yang dipakai saat eval signal di bar `t` **WAJIB punya `close_time <= t`** (dijaga oleh `slice_up_to_time`). Hasil backtest tidak overfit / tidak merefleksikan data masa depan. |
| **🔑 Setiap Position Punya SL** | Tidak ada code path yang open position tanpa SL valid (jika SL calc gagal → trade di-skip, log error, **lanjut**, tidak open unprotected). |
| **🧪 Unit Test Suite: 60/60 pytest PASS** | Test terpisah per module: config, indicators (MA/cross/ATR), strategy (clean buy/sell/no signal), risk_manager (sizing + DOLLAR mode), data_feed, order_executor, reporting, **dan 1 test end-to-end backtest**. |
| **⚠️ Fail-Fast on Invalid Config** | ENV salah / missing / inconsistent → **error JELAS di startup SEBELUM** connect MT5 / mulai loop (bukan gagal di tengah run). |

---

## 📂 Struktur Folder

```
EA-MA510/
├── main.py                  # Entrypoint (SATU-SATUNYA file .py di root). Jangan pindahkan.
├── conftest.py              # Marker pytest (agar sys.path inject src.* di test). Jangan hapus.
├── .env.example             # Template ENV. Copy → .env sebelum pakai.
├── .gitignore               # Mengabaikan .env (RAHASIA!), venv, __pycache__, logs/, reports/, .trae/.
├── requirements.txt         # Minimal deps. MetaTrader5 = Windows-only, TIDAK dimasukkan.
├── AGENTS.md                # Instruksi khusus untuk AI Coding Agent (baca sebelum ubah code!).
│
├── src/                     # Semua logic code (Python package standar)
│   ├── __init__.py          # Package marker (kosong).
│   ├── config.py            # Load + validasi ENV. Semua ENV di-validasi di sini terlebih dahulu.
│   ├── logger.py            # Logger setup.
│   ├── indicators.py        # MA (SMA/EMA), cross detection, ATR (pure pandas/numpy).
│   ├── strategy.py          # ⭐ evaluate_signal() — PURE function (NO MT5 call, NO datetime.now, fully testable).
│   ├── risk_manager.py      # compute_trade_plan(): FIXED_LOT vs RISK_PERCENT sizing. SL/TP FIXED/ATR/DOLLAR math.
│   ├── data_feed.py         # get_history (MT5 riil) + generate_synthetic_candles + resample.
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
└── contexts/                # ⭐ Sumber Kebenaran Spesifikasi — WAJIB baca sebelum modifikasi!
    ├── PRD.md               # Apa yang dibangun, scope, goals, non-goals.
    ├── RULES.md             # 🚨 SUMBER KEBENARAN STRATEGI (entry/exit/sizing). Jika code beda → RULES.MD MENANG!
    ├── ARCHITECTURE.md      # Batasan module, data flow (mana logic harus taro di mana).
    ├── DESIGN.md            # Function/class signature, pseudo-code, algorithms.
    └── SCHEMA.md            # 🚨 SEMUA ENV variable (name, type, required, default, validation).
```

---

## 🚀 Quick Start

### Prasyarat
- Python **3.10+**
- (Linux/MacOS) Tidak perlu install MetaTrader5 — backtest akan pakai **synthetic data otomatis**.
- (Windows, mau data historis RIIL) Install MT5 Terminal.exe dan login ke account demo terlebih dahulu.

---

### 1) Install Dependencies (Semua OS)

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

**(Opsional, HANYA WINDOWS untuk Live / Data Riil MT5 History):**
```powershell
pip install MetaTrader5   # ⚠️ WINDOWS-ONLY! Akan FAIL di Linux/MacOS. Backtest synthetic TIDAK PERLU ini.
```

---

### 2) Buat `.env` dari Template

```bash
# Linux / MacOS:
cp .env.example .env

# Windows:
#   copy .env.example .env
```

Edit `.env` sesuai kebutuhan Anda (symbol, range date, sizing, SL/TP mode). Lihat [contexts/SCHEMA.md](file:///home/syawal/Project/EA-MA510/contexts/SCHEMA.md) untuk daftar ENV LENGKAP beserta type/required/default/validation-nya.

**Contoh minimal (Backtest synthetic mode — jalan di SEMUA OS):**
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
BACKTEST_USE_MT5=false          # ← Pakai synthetic, tidak perlu MT5 install

SIZING_MODE=FIXED_LOT
FIXED_LOT_SIZE=0.1

SL_MODE=DOLLAR
SL_DOLLAR=5.0                   # Risiko MAKSIMAL $5 per posisi
TP_MODE=DOLLAR
TP_DOLLAR=15.0                  # Target $15 per posisi (R:R = 1:3)
ATR_PERIOD=14

LOG_LEVEL=INFO
LOG_DIR=./logs
REPORT_DIR=./reports
```

---

### 3) Jalankan Backtest

```bash
python main.py
```

Anda akan melihat **progress logging setiap 5%** (contoh output):
```
[BACKTEST] Data siap → M5:25920 bars, M15:8640 bars, M30:4320 bars (sumber=SYNTHETIC). Loop dimulai...
[BACKTEST]   0% | bar 16/25920 | elapsed 0s | ETA ???
[BACKTEST]   5% | bar 1296/25920 | elapsed 2s | ETA 33s
[BACKTEST]  10% | bar 2592/25920 | elapsed 3s | ETA 30s
...
[BACKTEST] 100% | bar 25920/25920 | elapsed 35s
[BACKTEST] SELESAI 100% dalam 36s. 312 trade(s) tercatat.
```

Setelah selesai → **report hasil backtest** akan ada di `reports/backtest_<YYYYMMDD_HHMMSS>/`:
- `summary.json` — semua metrics (win rate, profit factor, max drawdown, expectancy, total return, dll)
- `trades.csv` — log semua trade: entry_time, direction, entry_price, sl, tp, close_time, close_price, pnl, pips
- `equity_curve.csv` — bar timestamp vs equity

---

### 4) Live Mode (⚠️ SELALU GUNAKAN DEMO ACCOUNT DULU!)

```env
MODE=LIVE
BACKTEST_USE_MT5=true          # Tidak dipakai di mode LIVE
MT5_LOGIN=463721066
MT5_PASSWORD=YourDemoPassword123
MT5_SERVER=Exness-MT5Trial17
# Opsional: MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
LIVE_POLL_INTERVAL_SECONDS=5
```

> **⚠️ PERINGATAN KEAMANAN — BACA SEBELUM MODE LIVE:**
> 1. Mode LIVE default **DRY-RUN** (jika flag `LIVE_SEND_REAL_ORDERS` tidak di-set ke `true`) — tidak pernah kirim order real kecuali Anda SET SECARA EKSPLISIT.
> 2. **JANGAN PERNAH** gunakan account funded REAL sebelum perilaku bot divalidasi berhari-hari / berminggu-minggu di **DEMO**.
> 3. `.env` berisi `MT5_LOGIN` + `MT5_PASSWORD` — file ini **SUDAH DI-IGNORE oleh .gitignore**, JANGAN pernah di-commit / dishare.

---

## 🧪 Jalankan Test Suite

```bash
# Semua test:
python -m pytest tests/ -v

# Hasil expected:
# 60 passed, 0 failed, 0 errors
```

---

## ⚙️ Environment Variables — Highlight (Ringkas)

Daftar LENGKAP ada di [contexts/SCHEMA.md](file:///home/syawal/Project/EA-MA510/contexts/SCHEMA.md). Yang paling sering di-tune:

| Env | Values | Penting |
|---|---|---|
| `MODE` | `BACKTEST` / `LIVE` | ✅ |
| `SYMBOL` | e.g. `XAUUSDm` (check broker-specific suffix!) | ✅ |
| `ENTRY_TIMEFRAME`, `TREND_TIMEFRAME_1`, `TREND_TIMEFRAME_2` | `M1/M5/M15/M30/H1/H4/D1` | ✅ |
| `MA_LOW`, `MA_HIGH`, `MA_TYPE` | `5 10 EMA` (default) | ✅ |
| `BACKTEST_START_DATE` / `_END_DATE` / `_INITIAL_BALANCE` | `YYYY-MM-DD` / float | ✅ BACKTEST |
| `BACKTEST_USE_MT5` | `false`=synthetic, `true`=coba MT5 history (Windows only) | |
| `SIZING_MODE` | `FIXED_LOT` / `RISK_PERCENT` | ✅ |
| `SL_MODE` / `TP_MODE` | `FIXED` / `ATR` / **`DOLLAR`** | ✅ |
| `SL_DOLLAR` / `TP_DOLLAR` | `5.0` / `15.0` → risiko $5, target $15 PER POSISI | Jika SL_MODE=DOLLAR |
| `MAX_CONCURRENT_POSITIONS` | `1` default | |
| `LOG_LEVEL` / `LOG_DIR` / `REPORT_DIR` | `INFO` / `./logs` / `./reports` | |

---

## 🧭 Spec Documents (Jangan Sentuh Strategy Sebelum Baca Ini!)

Semua file ada di folder `contexts/` → **jika ada pertentangan antara code × RULES.md/SCHEMA.md → DOKUMEN INI YANG MENANG.**

| File | Isi |
|---|---|
| [contexts/PRD.md](file:///home/syawal/Project/EA-MA510/contexts/PRD.md) | Product Requirement: goals, scope, FR/NFR. |
| [contexts/RULES.md](file:///home/syawal/Project/EA-MA510/contexts/RULES.md) | 🚨 **Strategi Trading** — entry BUY/SELL, exit, filter trend. |
| [contexts/ARCHITECTURE.md](file:///home/syawal/Project/EA-MA510/contexts/ARCHITECTURE.md) | Module boundaries, mana logic taro di mana, data flow. |
| [contexts/DESIGN.md](file:///home/syawal/Project/EA-MA510/contexts/DESIGN.md) | Function signatures, pseudo-code, algoritma konkret. |
| [contexts/SCHEMA.md](file:///home/syawal/Project/EA-MA510/contexts/SCHEMA.md) | 🚨 **Environment Variables LENGKAP** (nama, type, required, default, validation). |
| [AGENTS.md](file:///home/syawal/Project/EA-MA510/AGENTS.md) | Instruksi build order + ground rules untuk AI agent / developer. |

---

## 🛠️ Troubleshooting

| Gejala | Penyebab + Solusi |
|---|---|
| **Config error: `BACKTEST_USE_MT5=true` di non-Windows / MetaTrader5 tidak terinstall** | `MetaTrader5` package itu **Windows-only**. Solusi: jalankan di Windows + install `MetaTrader5`, atau set `BACKTEST_USE_MT5=false` untuk mode synthetic. |
| `pip install MetaTrader5` FAIL di Linux / Mac | **Sudah diantisipasi**. PyPI package MetaTrader5 **hanya support Windows (butuh MT5 Terminal.exe)**. Backtest synthetic mode berjalan TANPA package ini (skip install). Data historis riil → gunakan Windows / VPS Windows. |
| **ConfigError: XX wajib diisi** | Cek ENV Anda sesuai SCHEMA.md. Jika SL_MODE=DOLLAR → `SL_DOLLAR` harus diisi dan >0. Jika RISK_PERCENT → `RISK_PERCENT_PER_TRADE` (0-100). |
| Backtest tidak menghasilkan trade sama sekali (0 trade) | 1) Trend filter ketat: kedua trend TF TIDAK PERNAH searah MA cross. Coba ganti parameter MA atau gunakan synthetic (pasti menghasilkan cross). 2) Spread terlalu tinggi (MAX_SPREAD_POINTS terlalu kecil). |
| `.env` (password MT5) terlanjur ter-add di git | JANGAN commit! Jalankan `git rm --cached -r .env` lalu cek `git status` — file harus hilang dari staged. |

---

## 🧱 Build Order (Jika Anda Mau Menambah Fitur)

Lihat [AGENTS.md](file:///home/syawal/Project/EA-MA510/AGENTS.md) §3 untuk urutan layer. Singkatnya:

1. **Config** (validasi ENV) — selesaikan dulu sebelum layer lain.
2. **Data feed + indicators** — verified output dengan fixture.
3. **Strategy** — pure + fully unit tested.
4. **Risk manager** — sizing/SL/TP math.
5. **Order executor** — BacktestExecutor dulu (0 risiko), baru Live.
6. **Backtest engine → reporting → live engine → main.py dispatch**.

> 💡 **Ground Rule Kritis (from AGENTS.md):**
> - `strategy.py` TETAP PURE: NO MT5 calls, NO file I/O, NO `datetime.now()` di dalamnya.
> - NO look-ahead di backtest: selalu gunakan `slice_up_to_time()`.
> - NEVER open position tanpa SL valid (skip trade, bukan nebak-nebak).

---

## ⚖️ License

For personal / internal trading use. Strategy rules are transparent and auditable from `contexts/RULES.md`. Live trading involves substantial risk of loss — **pastikan Anda memahami strategi dan risiko sebelum funding real account.**
