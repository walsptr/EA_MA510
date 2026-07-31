import pytest
import sys
import os
import ast
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
import pandas as pd
import numpy as np

from src.config import Config
from src.indicators import moving_average, detect_cross, trend_direction, CrossState
from src.strategy import Signal, evaluate_signal


def make_df(data_list):
    n = len(data_list)
    times = pd.date_range(start="2025-01-01 00:00", periods=n, freq="5min")
    return pd.DataFrame({"time": times, "close": list(data_list)})


def make_buy_cfg():
    return Config(
        mode="BACKTEST",
        symbol="XAUUSDm",
        entry_timeframe="M5",
        trend_timeframe_1="M15",
        trend_timeframe_2="M30",
        ma_low=5,
        ma_high=10,
        ma_type="EMA",
        trend_ma_low_1=None,
        trend_ma_high_1=None,
        trend_ma_low_2=None,
        trend_ma_high_2=None,
        backtest_start_date=date(2025, 1, 1),
        backtest_end_date=date(2025, 1, 2),
        backtest_warmup_days=0,
        backtest_initial_balance=1000,
        backtest_spread_points=0,
        backtest_slippage_points=0,
        backtest_use_mt5=False,
        sizing_mode="FIXED_LOT",
        fixed_lot_size=0.1,
        risk_percent_per_trade=None,
        sl_mode="FIXED",
        sl_points=100,
        sl_atr_multiplier=None,
        sl_dollar=None,
        tp_mode="FIXED",
        tp_points=200,
        tp_atr_multiplier=None,
        tp_dollar=None,
        atr_period=14,
        trailing_stop_enabled=False,
        trailing_stop_points=None,
        trailing_stop_activation_points=None,
        exit_on_opposite_signal=False,
        max_concurrent_positions=1,
        max_spread_points=None,
        max_daily_loss_percent=None,
        trading_window_start=None,
        trading_window_end=None,
        magic_number=1,
        live_poll_interval_seconds=5,
        live_warmup_days=0,
        mt5_login=None,
        mt5_password=None,
        mt5_server=None,
        mt5_terminal_path=None,
        log_level="INFO",
        log_dir="./logs",
        report_dir="./reports",
        display_timezone="UTC",
    )


def _make_bullish_tf_df(n=20):
    base = 100.0
    data = []
    for i in range(n):
        base += 1.0
        data.append(base)
    return make_df(data)


def _make_bearish_tf_df(n=20):
    base = 100.0
    data = []
    for i in range(n):
        base -= 1.0
        data.append(base)
    return make_df(data)


def _make_flat_tf_df(n=20):
    return make_df([100.0] * n)


def _build_entry_cross_up():
    prices = [
        110.0, 108.0, 106.0, 104.0, 102.0,
        100.0,  98.0,  96.0,  94.0,  92.0,
         91.0,  90.5,  90.0,  89.5,  89.0,
         89.2,  89.0,  88.8,  88.5, 105.0,
    ]
    return make_df(prices)


def _build_entry_cross_down():
    prices = [
        90.0,  92.0,  94.0,  96.0,  98.0,
        100.0, 102.0, 104.0, 106.0, 108.0,
        109.0, 109.5, 110.0, 110.5, 111.0,
        110.8, 111.0, 111.2, 111.5,  95.0,
    ]
    return make_df(prices)


def test_buy_signal_clean():
    cfg = make_buy_cfg()
    entry_df = _build_entry_cross_up()
    tf1_df = _make_bullish_tf_df(20)
    tf2_df = _make_bullish_tf_df(20)

    ma5 = moving_average(entry_df.close, 5, "EMA")
    ma10 = moving_average(entry_df.close, 10, "EMA")
    cross = detect_cross(ma5, ma10)
    assert cross == CrossState.CROSS_UP, f"Expected CROSS_UP but got {cross}. Check entry price pattern."

    candles = {
        cfg.entry_timeframe: entry_df,
        cfg.trend_timeframe_1: tf1_df,
        cfg.trend_timeframe_2: tf2_df,
    }
    sig = evaluate_signal(candles, cfg)
    assert sig.direction == "BUY", f"Expected BUY, got {sig.direction} reason={sig.reason}"
    assert sig.reason == "cross_up + t1=BULLISH + t2=BULLISH"


def test_buy_cross_up_but_tf2_bearish():
    cfg = make_buy_cfg()
    entry_df = _build_entry_cross_up()
    tf1_df = _make_bullish_tf_df(20)
    tf2_df = _make_bearish_tf_df(20)

    candles = {
        cfg.entry_timeframe: entry_df,
        cfg.trend_timeframe_1: tf1_df,
        cfg.trend_timeframe_2: tf2_df,
    }
    sig = evaluate_signal(candles, cfg)
    assert sig.direction == "NONE"


def test_buy_cross_up_but_tf1_flat():
    cfg = make_buy_cfg()
    entry_df = _build_entry_cross_up()
    tf1_df = _make_flat_tf_df(20)
    tf2_df = _make_bullish_tf_df(20)

    candles = {
        cfg.entry_timeframe: entry_df,
        cfg.trend_timeframe_1: tf1_df,
        cfg.trend_timeframe_2: tf2_df,
    }
    sig = evaluate_signal(candles, cfg)
    assert sig.direction == "NONE"


def test_sell_signal_clean():
    cfg = make_buy_cfg()
    entry_df = _build_entry_cross_down()
    tf1_df = _make_bearish_tf_df(20)
    tf2_df = _make_bearish_tf_df(20)

    ma5 = moving_average(entry_df.close, 5, "EMA")
    ma10 = moving_average(entry_df.close, 10, "EMA")
    cross = detect_cross(ma5, ma10)
    assert cross == CrossState.CROSS_DOWN, f"Expected CROSS_DOWN but got {cross}. Check entry price pattern."

    candles = {
        cfg.entry_timeframe: entry_df,
        cfg.trend_timeframe_1: tf1_df,
        cfg.trend_timeframe_2: tf2_df,
    }
    sig = evaluate_signal(candles, cfg)
    assert sig.direction == "SELL", f"Expected SELL, got {sig.direction} reason={sig.reason}"
    assert sig.reason == "cross_down + t1=BEARISH + t2=BEARISH"


def test_insufficient_history():
    cfg = make_buy_cfg()
    entry_df = make_df([100.0, 101.0, 102.0])
    tf1_df = make_df([100.0] * 20)
    tf2_df = make_df([100.0] * 20)

    candles = {
        cfg.entry_timeframe: entry_df,
        cfg.trend_timeframe_1: tf1_df,
        cfg.trend_timeframe_2: tf2_df,
    }
    sig = evaluate_signal(candles, cfg)
    assert sig.direction == "NONE"
    assert "insufficient history" in sig.reason


def test_no_cross_ma_low_always_above():
    cfg = make_buy_cfg()
    entry_df = _make_bullish_tf_df(20)
    tf1_df = _make_bullish_tf_df(20)
    tf2_df = _make_bullish_tf_df(20)

    ma5 = moving_average(entry_df.close, 5, "EMA")
    ma10 = moving_average(entry_df.close, 10, "EMA")
    cross = detect_cross(ma5, ma10)
    assert cross == CrossState.NONE

    candles = {
        cfg.entry_timeframe: entry_df,
        cfg.trend_timeframe_1: tf1_df,
        cfg.trend_timeframe_2: tf2_df,
    }
    sig = evaluate_signal(candles, cfg)
    assert sig.direction == "NONE"


def test_buy_signal_entry_trend_ma_enabled_allows():
    cfg = make_buy_cfg()
    object.__setattr__(cfg, "trend_ma_low_1", 3)
    object.__setattr__(cfg, "trend_ma_high_1", 8)

    entry_df = _build_entry_cross_up()
    tf1_df = _make_bullish_tf_df(20)
    tf2_df = _make_bullish_tf_df(20)

    tma1_low = moving_average(entry_df.close, cfg.trend_ma_low_1, cfg.ma_type)
    tma1_high = moving_average(entry_df.close, cfg.trend_ma_high_1, cfg.ma_type)
    assert trend_direction(tma1_low, tma1_high) == "BULLISH"

    candles = {
        cfg.entry_timeframe: entry_df,
        cfg.trend_timeframe_1: tf1_df,
        cfg.trend_timeframe_2: tf2_df,
    }
    sig = evaluate_signal(candles, cfg)
    assert sig.direction == "BUY", f"Expected BUY, got {sig.direction} reason={sig.reason}"
    assert "entry_trend_1=BULLISH" in sig.reason
    assert "entry_trend_2" not in sig.reason


def test_buy_cross_up_but_entry_trend_ma_blocks():
    cfg = make_buy_cfg()
    object.__setattr__(cfg, "trend_ma_low_1", 3)
    object.__setattr__(cfg, "trend_ma_high_1", 8)
    object.__setattr__(cfg, "trend_ma_low_2", 4)
    object.__setattr__(cfg, "trend_ma_high_2", 18)

    entry_df = _build_entry_cross_up()
    tf1_df = _make_bullish_tf_df(20)
    tf2_df = _make_bullish_tf_df(20)

    tma2_low = moving_average(entry_df.close, cfg.trend_ma_low_2, cfg.ma_type)
    tma2_high = moving_average(entry_df.close, cfg.trend_ma_high_2, cfg.ma_type)
    assert trend_direction(tma2_low, tma2_high) != "BULLISH"

    candles = {
        cfg.entry_timeframe: entry_df,
        cfg.trend_timeframe_1: tf1_df,
        cfg.trend_timeframe_2: tf2_df,
    }
    sig = evaluate_signal(candles, cfg)
    assert sig.direction == "NONE"
    assert "entry_trend_1=" in sig.reason
    assert "entry_trend_2=" in sig.reason


def test_buy_signal_entry_trend_ma_pair_2_only_allows():
    cfg = make_buy_cfg()
    object.__setattr__(cfg, "trend_ma_low_2", 5)
    object.__setattr__(cfg, "trend_ma_high_2", 13)

    entry_df = _build_entry_cross_up()
    tf1_df = _make_bullish_tf_df(20)
    tf2_df = _make_bullish_tf_df(20)

    tma2_low = moving_average(entry_df.close, cfg.trend_ma_low_2, cfg.ma_type)
    tma2_high = moving_average(entry_df.close, cfg.trend_ma_high_2, cfg.ma_type)
    assert trend_direction(tma2_low, tma2_high) == "BULLISH"

    candles = {
        cfg.entry_timeframe: entry_df,
        cfg.trend_timeframe_1: tf1_df,
        cfg.trend_timeframe_2: tf2_df,
    }
    sig = evaluate_signal(candles, cfg)
    assert sig.direction == "BUY"
    assert "entry_trend_1" not in sig.reason
    assert "entry_trend_2=BULLISH" in sig.reason



def test_module_pure_imports():
    strategy_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "src",
        "strategy.py",
    )
    with open(strategy_path, "r") as f:
        source = f.read()

    tree = ast.parse(source)
    mt5_imported = False
    datetime_module_imported = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "MetaTrader5":
                    mt5_imported = True
                if alias.name == "datetime":
                    datetime_module_imported = True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "MetaTrader5":
                mt5_imported = True
            if node.module == "datetime":
                datetime_module_imported = True

    assert not mt5_imported, "strategy.py tidak boleh import MetaTrader5"
    assert not datetime_module_imported, "strategy.py tidak boleh import datetime modul"
    assert "datetime.now" not in source, "strategy.py tidak boleh mengandung datetime.now"
