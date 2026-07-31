import pytest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import load_config, ConfigError
from src.risk_manager import SymbolInfo, Signal, TradePlan, compute_trade_plan, round_to_step

# ===== Fixtures =====
@pytest.fixture
def xauusd_symbol_info():
    """XAUUSD: point=0.01, 1 point per lot 1.0 = $1"""
    return SymbolInfo(
        point=0.01,
        trade_tick_value=1.0,
        trade_tick_size=0.01,
        volume_step=0.01,
        volume_min=0.01,
        volume_max=100.0,
        digits=2,
    )

@pytest.fixture
def eurusd_symbol_info():
    """EURUSD: point=0.00001, 1 point per lot 1.0 = $1 (standard micro)"""
    return SymbolInfo(
        point=0.00001,
        trade_tick_value=0.1,  # per point 1 lot 1.0
        trade_tick_size=0.00001,
        volume_step=0.01,
        volume_min=0.01,
        volume_max=100.0,
        digits=5,
    )

def _make_config_dollar_xauusd_fixed_lot(monkeypatch, sl_dollar, tp_dollar, lot=0.5):
    env = {
        "MODE": "BACKTEST",
        "SYMBOL": "XAUUSDm",
        "ENTRY_TIMEFRAME": "M5",
        "TREND_TIMEFRAME_1": "M15",
        "TREND_TIMEFRAME_2": "M30",
        "MA_LOW": "5",
        "MA_HIGH": "10",
        "BACKTEST_START_DATE": "2025-01-01",
        "BACKTEST_END_DATE": "2025-12-31",
        "BACKTEST_SPREAD_POINTS": "0",
        "SIZING_MODE": "FIXED_LOT",
        "FIXED_LOT_SIZE": str(lot),
        "SL_MODE": "DOLLAR",
        "SL_DOLLAR": str(sl_dollar),
        "TP_MODE": "DOLLAR",
        "TP_DOLLAR": str(tp_dollar),
    }
    for k in list(os.environ.keys()):
        if k.isupper() and len(k) > 2:
            monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return load_config(use_dotenv=False)

# ===== TR-5.1: BUY XAUUSD DOLLAR, lot=0.5, SL=$5 → sl_price harus berada di bawah entry, total PnL saat SL ≈ -$5 =====
def test_risk_buy_xauusd_dollar_5sl(monkeypatch, xauusd_symbol_info):
    cfg = _make_config_dollar_xauusd_fixed_lot(monkeypatch, sl_dollar=5.0, tp_dollar=15.0, lot=0.5)
    entry_price = 2000.00
    signal = Signal(direction="BUY", entry_timeframe_close_price=entry_price)
    plan = compute_trade_plan(signal, cfg, xauusd_symbol_info, account_equity=1000.0, atr_value=None)
    assert plan is not None
    assert plan.direction == "BUY"
    assert plan.lot_size == 0.5
    # BUY: sl_price < entry < tp_price
    assert plan.sl_price < entry_price
    assert plan.tp_price > entry_price
    # Hitung expected sl_distance: $5 / 0.5 lot = $10 per lot = 10 points XAUUSD = $0.10 price
    expected_sl_distance = 5.0 / (0.5 * 1.0) * 0.01  # 5 / 0.5 = 10 points → 10 * 0.01 = 0.1
    assert abs(plan.sl_price - (entry_price - expected_sl_distance)) < 0.01  # tolerance 1 point
    # Expected TP: $15 / 0.5 = 30 points = 0.3
    expected_tp_distance = 15.0 / (0.5 * 1.0) * 0.01
    assert abs(plan.tp_price - (entry_price + expected_tp_distance)) < 0.01


def test_risk_dollar_mode_respects_spread_in_backtest(monkeypatch, xauusd_symbol_info):
    cfg = _make_config_dollar_xauusd_fixed_lot(monkeypatch, sl_dollar=5.0, tp_dollar=15.0, lot=0.5)
    monkeypatch.setenv("BACKTEST_SPREAD_POINTS", "20")
    cfg = load_config(use_dotenv=False)

    entry_price = 2000.00
    signal = Signal(direction="BUY", entry_timeframe_close_price=entry_price)
    plan = compute_trade_plan(signal, cfg, xauusd_symbol_info, account_equity=1000.0, atr_value=None)
    assert plan is not None

    point = xauusd_symbol_info.point
    open_price = entry_price + (cfg.backtest_spread_points * point) / 2
    expected_sl_distance = 5.0 / (0.5 * 1.0) * point
    expected_tp_distance = 15.0 / (0.5 * 1.0) * point

    assert abs(plan.sl_price - (open_price - expected_sl_distance)) < point
    assert abs(plan.tp_price - (open_price + expected_tp_distance)) < point

# ===== TR-5.2: SELL EURUSD DOLLAR, lot=1.0, TP=$10 → tp_price di bawah entry =====
def test_risk_sell_eurusd_dollar_tp_10(monkeypatch):
    # Buat symbol info EURUSD yang trade_tick_value=1.0 per $0.0001 (standard)
    si = SymbolInfo(
        point=0.0001,
        trade_tick_value=1.0,
        trade_tick_size=0.0001,
        volume_step=0.01,
        volume_min=0.01,
        volume_max=100.0,
        digits=4,
    )
    # Config DOLLAR mode + FIXED_LOT 1.0
    env = {
        "MODE": "BACKTEST", "SYMBOL": "EURUSD", "ENTRY_TIMEFRAME": "M5",
        "TREND_TIMEFRAME_1": "M15", "TREND_TIMEFRAME_2": "M30",
        "MA_LOW": "5", "MA_HIGH": "10",
        "BACKTEST_START_DATE": "2025-01-01", "BACKTEST_END_DATE": "2025-12-31",
        "SIZING_MODE": "FIXED_LOT", "FIXED_LOT_SIZE": "1.0",
        "SL_MODE": "DOLLAR", "SL_DOLLAR": "10",
        "TP_MODE": "DOLLAR", "TP_DOLLAR": "10",
    }
    for k in list(os.environ.keys()):
        if k.isupper() and len(k) > 2:
            monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    cfg = load_config(use_dotenv=False)
    entry_price = 1.08500
    signal = Signal(direction="SELL", entry_timeframe_close_price=entry_price)
    plan = compute_trade_plan(signal, cfg, si, account_equity=1000.0, atr_value=None)
    assert plan is not None
    assert plan.direction == "SELL"
    assert plan.lot_size == 1.0
    # SELL: tp < entry < sl
    assert plan.tp_price < entry_price
    assert plan.sl_price > entry_price
    # $10 TP dengan 1 lot → 10 points EURUSD = 0.0010
    expected_tp_distance = 10.0 / (1.0 * 1.0) * 0.0001  # 0.0010
    assert abs(plan.tp_price - (entry_price - expected_tp_distance)) < 0.0002

# ===== TR-5.3: Regression FIXED mode tetap benar =====
def test_risk_fixed_mode_regression(monkeypatch, xauusd_symbol_info):
    env = {
        "MODE": "BACKTEST", "SYMBOL": "XAUUSDm", "ENTRY_TIMEFRAME": "M5",
        "TREND_TIMEFRAME_1": "M15", "TREND_TIMEFRAME_2": "M30",
        "MA_LOW": "5", "MA_HIGH": "10",
        "BACKTEST_START_DATE": "2025-01-01", "BACKTEST_END_DATE": "2025-12-31",
        "SIZING_MODE": "FIXED_LOT", "FIXED_LOT_SIZE": "1.0",
        "SL_MODE": "FIXED", "SL_POINTS": "50",
        "TP_MODE": "FIXED", "TP_POINTS": "150",
    }
    for k in list(os.environ.keys()):
        if k.isupper() and len(k) > 2:
            monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    cfg = load_config(use_dotenv=False)
    entry = 2000.00
    signal = Signal(direction="BUY", entry_timeframe_close_price=entry)
    plan = compute_trade_plan(signal, cfg, xauusd_symbol_info, account_equity=1000.0, atr_value=None)
    assert plan is not None
    # 50 points XAUUSD (point=0.01) = 0.5
    assert abs(plan.sl_price - (entry - 0.5)) < 0.001
    # 150 points = 1.5
    assert abs(plan.tp_price - (entry + 1.5)) < 0.001

# ===== TR-5.4: Harga SL/TP dibulatkan sesuai digits (XAUUSD=2 digits) =====
def test_risk_price_rounding_digits(monkeypatch, xauusd_symbol_info):
    cfg = _make_config_dollar_xauusd_fixed_lot(monkeypatch, sl_dollar=2.5, tp_dollar=7.5, lot=0.33)
    signal = Signal(direction="BUY", entry_timeframe_close_price=2000.00)
    plan = compute_trade_plan(signal, cfg, xauusd_symbol_info, account_equity=1000.0)
    assert plan is not None
    # Verifikasi hanya 2 angka desimal
    assert round(plan.sl_price, 2) == plan.sl_price
    assert round(plan.tp_price, 2) == plan.tp_price

# ===== TR-5.5: SL_DOLLAR terlalu kecil → return None =====
def test_risk_sl_dollar_too_small_return_none(monkeypatch, xauusd_symbol_info):
    # SL $0.0001 dengan lot 1.0 → sl_distance < point
    cfg = _make_config_dollar_xauusd_fixed_lot(monkeypatch, sl_dollar=0.000001, tp_dollar=1.0, lot=1.0)
    signal = Signal(direction="BUY", entry_timeframe_close_price=2000.00)
    plan = compute_trade_plan(signal, cfg, xauusd_symbol_info, account_equity=1000.0)
    assert plan is None

# ===== Checkpoint 24: RISK_PERCENT + SL_MODE=DOLLAR interaksi =====
def test_risk_percent_plus_dollar_mode(monkeypatch, xauusd_symbol_info):
    # SL_DOLLAR = $10 sebagai fixed risk
    env = {
        "MODE": "BACKTEST", "SYMBOL": "XAUUSDm", "ENTRY_TIMEFRAME": "M5",
        "TREND_TIMEFRAME_1": "M15", "TREND_TIMEFRAME_2": "M30",
        "MA_LOW": "5", "MA_HIGH": "10",
        "BACKTEST_START_DATE": "2025-01-01", "BACKTEST_END_DATE": "2025-12-31",
        "SIZING_MODE": "RISK_PERCENT", "RISK_PERCENT_PER_TRADE": "1",  # 1% of 1000 = $10
        "SL_MODE": "DOLLAR", "SL_DOLLAR": "10",
        "TP_MODE": "DOLLAR", "TP_DOLLAR": "20",
    }
    for k in list(os.environ.keys()):
        if k.isupper() and len(k) > 2:
            monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    cfg = load_config(use_dotenv=False)
    entry = 2000.00
    signal = Signal(direction="BUY", entry_timeframe_close_price=entry)
    account_equity = 1000.0
    plan = compute_trade_plan(signal, cfg, xauusd_symbol_info, account_equity=account_equity)
    assert plan is not None
    # Dengan risk_amount=$10, XAUUSD: 1 point=$1 per 1 lot. Lot 1.0 → sl_distance 10 points = 0.1
    # Jadi lot 1.0, sl_distance 0.1 → entry - 0.1
    assert plan.lot_size >= xauusd_symbol_info.volume_min
    assert plan.sl_price < entry
    assert plan.tp_price > entry
