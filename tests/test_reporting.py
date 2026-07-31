import pytest
import pandas as pd
import os
import json
import tempfile
from datetime import date
from dataclasses import asdict

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.reporting import generate_report
from src.config import Config
from src.order_executor import TradeLogEntry, EquityPoint


def make_minimal_cfg(initial_balance=1000.0):
    return Config(
        mode="BACKTEST",
        symbol="XAUUSDm",
        entry_timeframe="M5", trend_timeframe_1="M15", trend_timeframe_2="M30",
        ma_low=5, ma_high=10, ma_type="EMA",
        trend_ma_low_1=None, trend_ma_high_1=None, trend_ma_low_2=None, trend_ma_high_2=None,
        backtest_start_date=date(2025, 1, 1), backtest_end_date=date(2025, 1, 2),
        backtest_warmup_days=0,
        backtest_initial_balance=initial_balance,
        backtest_spread_points=0, backtest_slippage_points=0, backtest_use_mt5=False,
        sizing_mode="FIXED_LOT", fixed_lot_size=0.1, risk_percent_per_trade=None,
        sl_mode="FIXED", sl_points=100, sl_atr_multiplier=None, sl_dollar=None,
        tp_mode="FIXED", tp_points=200, tp_atr_multiplier=None, tp_dollar=None,
        atr_period=14,
        trailing_stop_enabled=False, trailing_stop_points=None, trailing_stop_activation_points=None,
        exit_on_opposite_signal=False, max_concurrent_positions=1,
        max_spread_points=None, max_daily_loss_percent=None,
        trading_window_start=None, trading_window_end=None,
        magic_number=1, live_poll_interval_seconds=5,
        live_warmup_days=0,
        mt5_login=None, mt5_password=None, mt5_server=None, mt5_terminal_path=None,
        log_level="INFO", log_dir="./logs", report_dir="./reports", display_timezone="UTC",
    )


def make_3_closed_trades():
    t1 = TradeLogEntry(trade_id=1, symbol="XAUUSDm", direction="BUY",
                       open_time=pd.Timestamp("2025-01-01 10:00:00"), open_price=2000.0,
                       close_time=pd.Timestamp("2025-01-01 11:00:00"), close_price=2001.0,
                       lot_size=0.1, sl_price=1999.0, tp_price=2002.0,
                       close_reason="TP_HIT", pnl=10.0, pnl_pct_equity=1.0, balance_after=1010.0,
                       signal_reason="test", magic_number=1)
    t2 = TradeLogEntry(trade_id=2, symbol="XAUUSDm", direction="SELL",
                       open_time=pd.Timestamp("2025-01-01 12:00:00"), open_price=2001.0,
                       close_time=pd.Timestamp("2025-01-01 13:00:00"), close_price=2001.5,
                       lot_size=0.1, sl_price=2003.0, tp_price=1999.0,
                       close_reason="SL_HIT", pnl=-5.0, pnl_pct_equity=-0.5, balance_after=1005.0,
                       signal_reason="test", magic_number=1)
    t3 = TradeLogEntry(trade_id=3, symbol="XAUUSDm", direction="BUY",
                       open_time=pd.Timestamp("2025-01-01 14:00:00"), open_price=2002.0,
                       close_time=pd.Timestamp("2025-01-01 15:00:00"), close_price=2003.0,
                       lot_size=0.1, sl_price=2001.0, tp_price=2004.0,
                       close_reason="TP_HIT", pnl=7.0, pnl_pct_equity=0.7, balance_after=1012.0,
                       signal_reason="test", magic_number=1)
    return [t1, t2, t3]


def make_equity_curve_for_3_trades():
    return [
        EquityPoint(time=pd.Timestamp("2025-01-01 09:00:00"), balance=1000.0, equity=1000.0, drawdown_pct=0.0),
        EquityPoint(time=pd.Timestamp("2025-01-01 10:30:00"), balance=1000.0, equity=1008.0, drawdown_pct=0.0),
        EquityPoint(time=pd.Timestamp("2025-01-01 11:00:00"), balance=1010.0, equity=1010.0, drawdown_pct=0.0),
        EquityPoint(time=pd.Timestamp("2025-01-01 12:30:00"), balance=1010.0, equity=1002.0, drawdown_pct=0.8),
        EquityPoint(time=pd.Timestamp("2025-01-01 13:00:00"), balance=1005.0, equity=1005.0, drawdown_pct=0.5),
        EquityPoint(time=pd.Timestamp("2025-01-01 15:00:00"), balance=1012.0, equity=1012.0, drawdown_pct=0.0),
    ]


def test_summary_metrics_3_trades_correct():
    cfg = make_minimal_cfg()
    tl = make_3_closed_trades()
    ec = make_equity_curve_for_3_trades()
    with tempfile.TemporaryDirectory() as tmpdir:
        summary = generate_report(tl, ec, tmpdir, cfg)
        assert summary["total_trades"] == 3
        assert summary["win_rate_pct"] == pytest.approx(66.6667, abs=0.01)
        assert summary["profit_factor"] == pytest.approx((10 + 7) / abs(-5), abs=0.01)
        assert summary["expectancy_per_trade"] == pytest.approx(12 / 3, abs=0.01)
        assert summary["largest_win"] == pytest.approx(10.0, abs=0.01)
        assert summary["largest_loss"] == pytest.approx(-5.0, abs=0.01)


def test_trades_csv_has_correct_columns_schema():
    tl = make_3_closed_trades()
    ec = make_equity_curve_for_3_trades()
    cfg = make_minimal_cfg()
    with tempfile.TemporaryDirectory() as tmpdir:
        generate_report(tl, ec, tmpdir, cfg)
        df = pd.read_csv(os.path.join(tmpdir, "trades.csv"))
        expected_cols = {"trade_id", "symbol", "direction", "open_time", "open_price", "close_time", "close_price", "lot_size", "sl_price", "tp_price", "close_reason", "pnl", "pnl_pct_equity", "balance_after", "signal_reason", "magic_number"}
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"
        assert len(df) == 3


def test_equity_curve_csv_columns():
    tl = make_3_closed_trades()
    ec = make_equity_curve_for_3_trades()
    cfg = make_minimal_cfg()
    with tempfile.TemporaryDirectory() as tmpdir:
        generate_report(tl, ec, tmpdir, cfg)
        df = pd.read_csv(os.path.join(tmpdir, "equity_curve.csv"))
        for col in ("time", "balance", "equity", "drawdown_pct"):
            assert col in df.columns, f"Missing column: {col}"
        assert len(df) == len(ec)


def test_max_drawdown_pct_correct():
    ec_custom = [
        EquityPoint(time=pd.Timestamp("2025-01-01 09:00:00"), balance=1000.0, equity=1000.0, drawdown_pct=0.0),
        EquityPoint(time=pd.Timestamp("2025-01-01 10:00:00"), balance=1000.0, equity=950.0, drawdown_pct=5.0),
        EquityPoint(time=pd.Timestamp("2025-01-01 11:00:00"), balance=1000.0, equity=900.0, drawdown_pct=10.0),
        EquityPoint(time=pd.Timestamp("2025-01-01 12:00:00"), balance=1100.0, equity=1100.0, drawdown_pct=0.0),
    ]
    tl_empty = []
    cfg = make_minimal_cfg(initial_balance=1000.0)
    with tempfile.TemporaryDirectory() as tmpdir:
        summary = generate_report(tl_empty, ec_custom, tmpdir, cfg)
        assert summary["max_drawdown_pct"] == pytest.approx(10.0, abs=0.01)
        assert summary["total_return_pct"] == pytest.approx(10.0, abs=0.01)
