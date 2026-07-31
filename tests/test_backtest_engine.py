import pytest
import os
import sys
import copy
import random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import date

from src.config import Config
from src.backtest_engine import slice_up_to_time, run_backtest


def make_backtest_cfg() -> Config:
    return Config(
        mode="BACKTEST",
        symbol="XAUUSDm",
        entry_timeframe="M5",
        trend_timeframe_1="M15",
        trend_timeframe_2="M30",
        ma_low=5,
        ma_high=10,
        ma_type="EMA",
        backtest_start_date=date(2025, 1, 1),
        backtest_end_date=date(2025, 1, 3),
        backtest_initial_balance=1000.0,
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
        magic_number=12345,
        live_poll_interval_seconds=5,
        mt5_login=None,
        mt5_password=None,
        mt5_server=None,
        mt5_terminal_path=None,
        log_level="INFO",
        log_dir="./logs",
        report_dir="./reports",
        display_timezone="UTC",
    )


def test_slice_up_to_time_no_look_ahead():
    times = [
        pd.Timestamp("2025-01-01 10:00:00"),
        pd.Timestamp("2025-01-01 10:05:00"),
        pd.Timestamp("2025-01-01 10:10:00"),
    ]
    df = pd.DataFrame({
        "time": times,
        "close_time": [
            pd.Timestamp("2025-01-01 10:00:00"),
            pd.Timestamp("2025-01-01 10:05:00"),
            pd.Timestamp("2025-01-01 10:10:00"),
        ],
        "open": [1.0, 2.0, 3.0],
        "high": [1.0, 2.0, 3.0],
        "low": [1.0, 2.0, 3.0],
        "close": [1.0, 2.0, 3.0],
        "tick_volume": [0, 0, 0],
        "spread": [0, 0, 0],
    })
    t = pd.Timestamp("2025-01-01 10:07:00")
    result = slice_up_to_time(df, t)
    assert len(result) == 2
    assert not (result["close_time"] > t).any()


def test_run_backtest_smoke_synthetic_no_exception():
    cfg = make_backtest_cfg()
    trade_log, equity_curve = run_backtest(cfg, use_mt5=False)
    assert isinstance(trade_log, list)
    assert isinstance(equity_curve, list)
    if len(trade_log) > 0:
        assert hasattr(trade_log[0], 'trade_id')
    if len(equity_curve) > 0:
        assert hasattr(equity_curve[0], 'equity')


def test_backtest_dollar_mode_sl_price_valid():
    cfg = copy.deepcopy(make_backtest_cfg())
    object.__setattr__(cfg, 'sl_mode', 'DOLLAR')
    object.__setattr__(cfg, 'sl_dollar', 5.0)
    object.__setattr__(cfg, 'sl_points', None)
    object.__setattr__(cfg, 'tp_mode', 'DOLLAR')
    object.__setattr__(cfg, 'tp_dollar', 15.0)
    object.__setattr__(cfg, 'tp_points', None)

    trade_log, equity_curve = run_backtest(cfg, use_mt5=False)

    for t in trade_log:
        if getattr(t, 'pnl', None) is not None or getattr(t, 'close_reason', None) is not None:
            assert t.sl_price is not None and not pd.isna(t.sl_price)
            assert t.tp_price is not None and not pd.isna(t.tp_price)
            if t.direction == "BUY":
                assert t.sl_price < t.open_price < t.tp_price, \
                    f"BUY invariant violation: sl={t.sl_price}, open={t.open_price}, tp={t.tp_price}"
            elif t.direction == "SELL":
                assert t.tp_price < t.open_price < t.sl_price


def test_backtest_deterministic_with_same_data():
    cfg = make_backtest_cfg()
    random.seed(42)
    np.random.seed(42)
    trade_log_1, equity_curve_1 = run_backtest(cfg, use_mt5=False)
    random.seed(42)
    np.random.seed(42)
    trade_log_2, equity_curve_2 = run_backtest(cfg, use_mt5=False)
    assert len(trade_log_1) == len(trade_log_2)
    assert len(equity_curve_1) == len(equity_curve_2)
