import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
import pandas as pd
import pytest

from src.config import Config
from src.data_feed import (
    generate_synthetic_candles,
    TIMEFRAME_DURATION_MAP,
    _empty_schema_df,
    get_synthetic_for_all_timeframes,
)
from src.strategy import evaluate_signal


def _make_buy_cfg():
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
        backtest_end_date=date(2025, 1, 2),
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
        mt5_login=None,
        mt5_password=None,
        mt5_server=None,
        mt5_terminal_path=None,
        log_level="INFO",
        log_dir="./logs",
        report_dir="./reports",
        display_timezone="UTC",
    )


def _make_bullish_synthetic(tf: str, n: int = 30, base_price: float = 2000.0):
    start = date(2025, 1, 1)
    dur = TIMEFRAME_DURATION_MAP[tf]
    from datetime import datetime, timedelta as td
    start_dt = datetime(2025, 1, 1)
    end_dt = start_dt + dur * (n + 5)
    df = generate_synthetic_candles(
        tf, start_dt, end_dt,
        pattern="flat",
        base_price=base_price,
        digits=2,
    )
    base = base_price
    trend_closes = []
    for i in range(len(df)):
        base += base * 0.002
        trend_closes.append(round(base, 2))
    df["close"] = trend_closes
    df["open"] = [trend_closes[0]] + trend_closes[:-1]
    df["high"] = df[["open", "close"]].max(axis=1) * 1.001
    df["low"] = df[["open", "close"]].min(axis=1) * 0.999
    return df


def test_synthetic_columns_schema():
    df = generate_synthetic_candles(
        "M5", date(2025, 1, 1), date(2025, 1, 2), pattern="flat"
    )
    required = {
        "time", "close_time", "open", "high", "low", "close",
        "tick_volume", "spread",
    }
    assert required.issubset(set(df.columns)), (
        f"Missing columns: {required - set(df.columns)}"
    )


def test_synthetic_close_time_duration():
    df = generate_synthetic_candles(
        "M5", date(2025, 1, 1), date(2025, 1, 2), pattern="flat"
    )
    expected_delta = pd.Timedelta(minutes=5)
    for idx, row in df.iterrows():
        diff = row.close_time - row.time
        assert diff == expected_delta, (
            f"Row {idx}: expected {expected_delta}, got {diff}. "
            f"time={row.time}, close_time={row.close_time}"
        )


def test_synthetic_long_enough_for_strategy():
    cfg = _make_buy_cfg()
    entry_df = generate_synthetic_candles(
        cfg.entry_timeframe,
        date(2025, 1, 1),
        date(2025, 1, 2),
        pattern="bull_cross_then_bear",
    )
    assert len(entry_df) >= 20, f"entry_df len={len(entry_df)} < 20"

    tf1_df = _make_bullish_synthetic(cfg.trend_timeframe_1, n=30)
    tf2_df = _make_bullish_synthetic(cfg.trend_timeframe_2, n=30)

    min_bars = max(cfg.ma_low, cfg.ma_high) + 1
    assert len(entry_df) >= min_bars
    assert len(tf1_df) >= min_bars
    assert len(tf2_df) >= min_bars

    candles = {
        cfg.entry_timeframe: entry_df,
        cfg.trend_timeframe_1: tf1_df,
        cfg.trend_timeframe_2: tf2_df,
    }
    sig = evaluate_signal(candles, cfg)
    assert "insufficient history" not in sig.reason, (
        f"Got 'insufficient history' but entry={len(entry_df)}, "
        f"tf1={len(tf1_df)}, tf2={len(tf2_df)}, min_bars={min_bars}"
    )


def test_mt5_import_defensive():
    from src.mt5_client import MT5Client
    cfg = _make_buy_cfg()
    client = MT5Client(cfg)
    try:
        import MetaTrader5 as _mt5_probe  # noqa: F401
        pytest.skip("MetaTrader5 terinstall di environment ini; test defensive import hanya relevan jika package tidak ada.")
    except ImportError:
        pass
    with pytest.raises(RuntimeError) as exc_info:
        client.initialize()
    msg = str(exc_info.value)
    assert "MetaTrader5" in msg or "MetaTrader 5" in msg, (
        f"RuntimeError message should mention MetaTrader5, got: {msg!r}"
    )


def test_empty_schema_df_has_correct_columns():
    df = _empty_schema_df()
    expected = [
        "time", "close_time", "open", "high", "low", "close",
        "tick_volume", "spread",
    ]
    assert list(df.columns) == expected
    assert len(df) == 0


def test_synthetic_bull_cross_has_enough_candles():
    df = generate_synthetic_candles(
        "M5", date(2025, 1, 1), date(2025, 1, 2),
        pattern="bull_cross_then_bear",
    )
    assert len(df) > 11
    assert len(df) >= 20


def test_synthetic_time_sorted_and_rangeindex():
    df = generate_synthetic_candles(
        "M5", date(2025, 1, 1), date(2025, 1, 2), pattern="flat"
    )
    times = df["time"].tolist()
    for i in range(1, len(times)):
        assert times[i] > times[i - 1], "time not sorted ascending"
    assert isinstance(df.index, pd.RangeIndex), (
        f"Expected RangeIndex, got {type(df.index)}"
    )
