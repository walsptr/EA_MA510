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
                 "TREND_MA_LOW_1","TREND_MA_HIGH_1","TREND_MA_LOW_2","TREND_MA_HIGH_2",
                 "BACKTEST_WARMUP_DAYS","BACKTEST_INITIAL_BALANCE","BACKTEST_SPREAD_POINTS","BACKTEST_SLIPPAGE_POINTS",
                 "SIZING_MODE","FIXED_LOT_SIZE","RISK_PERCENT_PER_TRADE",
                 "SL_MODE","SL_POINTS","SL_ATR_MULTIPLIER","SL_DOLLAR",
                 "TP_MODE","TP_POINTS","TP_ATR_MULTIPLIER","TP_DOLLAR",
                 "ATR_PERIOD","TRAILING_STOP_ENABLED","TRAILING_STOP_POINTS",
                 "TRAILING_STOP_ACTIVATION_POINTS","EXIT_ON_OPPOSITE_SIGNAL",
                 "MAX_CONCURRENT_POSITIONS","MAX_SPREAD_POINTS","MAX_DAILY_LOSS_PERCENT",
                 "MAGIC_NUMBER","LIVE_POLL_INTERVAL_SECONDS",
                 "LIVE_WARMUP_DAYS",
                 "MT5_LOGIN","MT5_PASSWORD","MT5_SERVER","MT5_TERMINAL_PATH",
                 "LOG_LEVEL","LOG_DIR","REPORT_DIR","DISPLAY_TIMEZONE",
                 "TRADING_WINDOW_START","TRADING_WINDOW_END"]:
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


def test_config_trading_window_valid(monkeypatch):
    env = _env_base()
    env["TRADING_WINDOW_START"] = "07:00"
    env["TRADING_WINDOW_END"] = "16:00"
    _set_env(monkeypatch, env)
    cfg = load_config(use_dotenv=False)
    assert cfg.trading_window_start is not None
    assert cfg.trading_window_end is not None


def test_config_trading_window_missing_end(monkeypatch):
    env = _env_base()
    env["TRADING_WINDOW_START"] = "07:00"
    env.pop("TRADING_WINDOW_END", None)
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError):
        load_config(use_dotenv=False)


def test_config_trading_window_invalid_format(monkeypatch):
    env = _env_base()
    env["TRADING_WINDOW_START"] = "7"
    env["TRADING_WINDOW_END"] = "16:00"
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError):
        load_config(use_dotenv=False)


def test_config_trading_window_equal_start_end_invalid(monkeypatch):
    env = _env_base()
    env["TRADING_WINDOW_START"] = "07:00"
    env["TRADING_WINDOW_END"] = "07:00"
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError):
        load_config(use_dotenv=False)


def test_config_backtest_warmup_days_negative(monkeypatch):
    env = _env_base()
    env["BACKTEST_WARMUP_DAYS"] = "-1"
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError):
        load_config(use_dotenv=False)


def test_config_backtest_initial_balance_zero_invalid(monkeypatch):
    env = _env_base()
    env["BACKTEST_INITIAL_BALANCE"] = "0"
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError) as excinfo:
        load_config(use_dotenv=False)
    assert "BACKTEST_INITIAL_BALANCE harus > 0" in str(excinfo.value)


def test_config_backtest_initial_balance_negative_invalid(monkeypatch):
    env = _env_base()
    env["BACKTEST_INITIAL_BALANCE"] = "-100"
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError) as excinfo:
        load_config(use_dotenv=False)
    assert "BACKTEST_INITIAL_BALANCE harus > 0" in str(excinfo.value)



def test_config_live_warmup_days_negative(monkeypatch):
    env = _env_base()
    env["LIVE_WARMUP_DAYS"] = "-1"
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError):
        load_config(use_dotenv=False)


def test_config_trend_ma_partial_set_raises(monkeypatch):
    env = _env_base()
    env["TREND_MA_LOW_1"] = "5"
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError):
        load_config(use_dotenv=False)


def test_config_trend_ma_pair_1_only_valid(monkeypatch):
    env = _env_base()
    env["TREND_MA_LOW_1"] = "3"
    env["TREND_MA_HIGH_1"] = "8"
    _set_env(monkeypatch, env)
    cfg = load_config(use_dotenv=False)
    assert cfg.trend_ma_low_1 == 3
    assert cfg.trend_ma_high_1 == 8
    assert cfg.trend_ma_low_2 is None
    assert cfg.trend_ma_high_2 is None


def test_config_trend_ma_pair_2_only_valid(monkeypatch):
    env = _env_base()
    env["TREND_MA_LOW_2"] = "5"
    env["TREND_MA_HIGH_2"] = "13"
    _set_env(monkeypatch, env)
    cfg = load_config(use_dotenv=False)
    assert cfg.trend_ma_low_1 is None
    assert cfg.trend_ma_high_1 is None
    assert cfg.trend_ma_low_2 == 5
    assert cfg.trend_ma_high_2 == 13



def test_config_trend_ma_invalid_order_raises(monkeypatch):
    env = _env_base()
    env["TREND_MA_LOW_1"] = "10"
    env["TREND_MA_HIGH_1"] = "10"
    _set_env(monkeypatch, env)
    with pytest.raises(ConfigError):
        load_config(use_dotenv=False)


def test_config_trend_ma_enabled_valid(monkeypatch):
    env = _env_base()
    env["TREND_MA_LOW_1"] = "3"
    env["TREND_MA_HIGH_1"] = "8"
    env["TREND_MA_LOW_2"] = "5"
    env["TREND_MA_HIGH_2"] = "13"
    _set_env(monkeypatch, env)
    cfg = load_config(use_dotenv=False)
    assert cfg.trend_ma_low_1 == 3
    assert cfg.trend_ma_high_1 == 8
    assert cfg.trend_ma_low_2 == 5
    assert cfg.trend_ma_high_2 == 13
