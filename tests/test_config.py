import pytest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import Config, ConfigError, load_config

def _env_base():
    """Return dict dengan ENV minimum yang valid (MODE=BACKTEST dengan FIXED SL/TP)."""
    return {
        "MODE": "BACKTEST",
        "SYMBOL": "XAUUSDm",
        "ENTRY_TIMEFRAME": "M5",
        "TREND_TIMEFRAME_1": "M15",
        "TREND_TIMEFRAME_2": "M30",
        "MA_LOW": "5",
        "MA_HIGH": "10",
        "BACKTEST_START_DATE": "2025-01-01",
        "BACKTEST_END_DATE": "2025-12-31",
        "SIZING_MODE": "FIXED_LOT",
        "FIXED_LOT_SIZE": "0.01",
        "SL_MODE": "FIXED",
        "SL_POINTS": "100",
        "TP_MODE": "FIXED",
        "TP_POINTS": "200",
    }

def _set_env(monkeypatch, env_dict):
    """Bersihkan ENV lama dan set variable dari env_dict."""
    for k in list(os.environ.keys()):
        if k in ["MODE","SYMBOL","ENTRY_TIMEFRAME","TREND_TIMEFRAME_1","TREND_TIMEFRAME_2",
                 "MA_LOW","MA_HIGH","MA_TYPE","BACKTEST_START_DATE","BACKTEST_END_DATE",
                 "BACKTEST_INITIAL_BALANCE","BACKTEST_SPREAD_POINTS","BACKTEST_SLIPPAGE_POINTS",
                 "SIZING_MODE","FIXED_LOT_SIZE","RISK_PERCENT_PER_TRADE",
                 "SL_MODE","SL_POINTS","SL_ATR_MULTIPLIER","SL_DOLLAR",
                 "TP_MODE","TP_POINTS","TP_ATR_MULTIPLIER","TP_DOLLAR",
                 "ATR_PERIOD","TRAILING_STOP_ENABLED","TRAILING_STOP_POINTS",
                 "TRAILING_STOP_ACTIVATION_POINTS","EXIT_ON_OPPOSITE_SIGNAL",
                 "MAX_CONCURRENT_POSITIONS","MAX_SPREAD_POINTS","MAX_DAILY_LOSS_PERCENT",
                 "MAGIC_NUMBER","LIVE_POLL_INTERVAL_SECONDS",
                 "MT5_LOGIN","MT5_PASSWORD","MT5_SERVER","MT5_TERMINAL_PATH",
                 "LOG_LEVEL","LOG_DIR","REPORT_DIR"]:
            monkeypatch.delenv(k, raising=False)
    for k, v in env_dict.items():
        monkeypatch.setenv(k, v)

# ===== TR-4.1: DOLLAR mode valid berhasil dimuat =====
def test_config_dollar_mode_valid(monkeypatch):
    env = _env_base()
    env["SL_MODE"] = "DOLLAR"
    env["SL_DOLLAR"] = "1.0"
    env.pop("SL_POINTS")
    env["TP_MODE"] = "DOLLAR"
    env["TP_DOLLAR"] = "2.0"
    env.pop("TP_POINTS")
    _set_env(monkeypatch, env)
    cfg = load_config(use_dotenv=False)
    assert cfg.sl_mode == "DOLLAR"
    assert cfg.sl_dollar == 1.0
    assert cfg.tp_mode == "DOLLAR"
    assert cfg.tp_dollar == 2.0

# ===== TR-4.2: SL_MODE=DOLLAR tanpa SL_DOLLAR → raise ConfigError =====
def test_config_dollar_missing_sl_dollar(monkeypatch):
    env = _env_base()
    env["SL_MODE"] = "DOLLAR"
    if "SL_DOLLAR" in env:
        del env["SL_DOLLAR"]
    env.pop("SL_POINTS", None)
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError):
        load_config(use_dotenv=False)

# ===== TR-4.3: SL_DOLLAR=0 → raise ConfigError =====
def test_config_dollar_sl_zero(monkeypatch):
    env = _env_base()
    env["SL_MODE"] = "DOLLAR"
    env["SL_DOLLAR"] = "0"
    env.pop("SL_POINTS", None)
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError):
        load_config(use_dotenv=False)

# ===== TR-4.4: SL_DOLLAR=-5 → raise ConfigError =====
def test_config_dollar_sl_negative(monkeypatch):
    env = _env_base()
    env["SL_MODE"] = "DOLLAR"
    env["SL_DOLLAR"] = "-5"
    env.pop("SL_POINTS", None)
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError):
        load_config(use_dotenv=False)

# ===== TR-4.5: Backward compatibility FIXED mode tetap valid =====
def test_config_fixed_mode_backward_compat(monkeypatch):
    env = _env_base()  # pakai base FIXED
    _set_env(monkeypatch, env)
    cfg = load_config(use_dotenv=False)
    assert cfg.sl_mode == "FIXED"
    assert cfg.sl_points == 100
    assert cfg.tp_mode == "FIXED"
    assert cfg.tp_points == 200
    # field dollar harus None
    assert cfg.sl_dollar is None
    assert cfg.tp_dollar is None

# ===== TP_DOLLAR negative juga harus error =====
def test_config_dollar_tp_negative(monkeypatch):
    env = _env_base()
    env["TP_MODE"] = "DOLLAR"
    env["TP_DOLLAR"] = "-10"
    env.pop("TP_POINTS", None)
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError):
        load_config(use_dotenv=False)
