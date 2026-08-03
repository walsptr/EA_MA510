import pytest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import date

from src.config import Config
from src.risk_manager import TradePlan, SymbolInfo
from src.order_executor import (
    Position,
    TradeResult,
    TradeLogEntry,
    EquityPoint,
    BacktestOrderExecutor,
    is_insufficient_funds_or_margin,
    sanitize_mt5_comment,
)


def make_xau_symbol_info() -> SymbolInfo:
    return SymbolInfo(
        point=0.01,
        trade_tick_value=1.0,
        trade_tick_size=0.01,
        volume_step=0.01,
        volume_min=0.01,
        volume_max=100.0,
        digits=2,
    )


def make_test_cfg() -> Config:
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
        backtest_end_date=date(2025, 12, 31),
        backtest_warmup_days=0,
        backtest_initial_balance=1000.0,
        backtest_spread_points=0,
        backtest_slippage_points=0,
        backtest_use_mt5=False,
        sizing_mode="FIXED_LOT",
        fixed_lot_size=0.1,
        risk_percent_per_trade=None,
        sl_mode="FIXED",
        sl_points=100.0,
        sl_atr_multiplier=None,
        sl_dollar=None,
        tp_mode="FIXED",
        tp_points=200.0,
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


ts1 = pd.Timestamp("2025-01-01 00:05:00")
ts2 = pd.Timestamp("2025-01-01 00:10:00")


def test_open_position_adds_to_positions_and_log():
    cfg = make_test_cfg()
    symbol_info = make_xau_symbol_info()
    ex = BacktestOrderExecutor(1000.0, cfg, symbol_info)
    plan = TradePlan(direction="BUY", lot_size=0.1, sl_price=1995.0, tp_price=2010.0)
    result = ex.open_position(
        plan,
        at_time=pd.Timestamp("2025-01-01 00:05:00"),
        entry_price=2000.0,
        signal_reason="test cross up",
    )
    assert result.success is True
    assert len(ex.positions) == 1
    assert len(ex.trade_log) == 1
    assert ex.trade_log[0].close_time is None
    assert ex.trade_log[0].pnl is None


def test_sl_before_tp_conservative_buy():
    cfg = make_test_cfg()
    symbol_info = make_xau_symbol_info()
    ex = BacktestOrderExecutor(1000.0, cfg, symbol_info)
    plan = TradePlan(direction="BUY", lot_size=1.0, sl_price=1990.0, tp_price=2010.0)
    ex.open_position(plan, at_time=ts1, entry_price=2000.0, signal_reason="test")
    bar = pd.Series(
        {
            "time": ts2,
            "low": 1989.0,
            "high": 2015.0,
            "close": 2005.0,
        }
    )
    results = ex.check_sl_tp_hits(bar)
    assert len(results) == 1
    assert results[0].close_reason == "SL_HIT"
    assert results[0].close_price == 1990.0
    assert len(ex.positions) == 0
    assert results[0].pnl is not None
    assert results[0].pnl < 0


def test_tp_hit_only_buy():
    cfg = make_test_cfg()
    symbol_info = make_xau_symbol_info()
    ex = BacktestOrderExecutor(1000.0, cfg, symbol_info)
    plan = TradePlan(direction="BUY", lot_size=0.5, sl_price=1995.0, tp_price=2010.0)
    ex.open_position(plan, at_time=ts1, entry_price=2000.0)
    bar = pd.Series(
        {
            "time": ts2,
            "low": 2002.0,
            "high": 2012.0,
            "close": 2011.0,
        }
    )
    results = ex.check_sl_tp_hits(bar)
    assert len(results) == 1
    assert results[0].close_reason == "TP_HIT"
    assert results[0].pnl > 0


def test_sell_tp_hit_below_entry():
    cfg = make_test_cfg()
    symbol_info = make_xau_symbol_info()
    ex = BacktestOrderExecutor(1000.0, cfg, symbol_info)
    plan = TradePlan(direction="SELL", lot_size=1.0, sl_price=2010.0, tp_price=1990.0)
    ex.open_position(plan, at_time=ts1, entry_price=2000.0)
    bar = pd.Series(
        {
            "time": ts2,
            "low": 1988.0,
            "high": 2002.0,
            "close": 1995.0,
        }
    )
    results = ex.check_sl_tp_hits(bar)
    assert len(results) == 1
    assert results[0].close_reason == "TP_HIT"
    assert results[0].pnl > 0


def test_close_position_updates_balance():
    cfg = make_test_cfg()
    symbol_info = make_xau_symbol_info()
    ex = BacktestOrderExecutor(1000.0, cfg, symbol_info)
    plan = TradePlan(direction="BUY", lot_size=1.0, sl_price=1990.0, tp_price=2010.0)
    res_open = ex.open_position(plan, at_time=ts1, entry_price=2000.0)
    ticket = res_open.position_id
    res_close = ex.close_position(ticket, at_time=ts2, close_price=2005.0, reason="MANUAL")
    assert res_close.pnl == pytest.approx(500.0, abs=0.01)
    assert ex.balance == pytest.approx(1500.0, abs=0.01)


def test_can_open_new_position_direction_same_rejected():
    cfg = make_test_cfg()
    symbol_info = make_xau_symbol_info()
    ex = BacktestOrderExecutor(1000.0, cfg, symbol_info)
    plan = TradePlan(direction="BUY", lot_size=0.1, sl_price=1995.0, tp_price=2010.0)
    ex.open_position(plan, at_time=ts1, entry_price=2000.0)
    assert ex.can_open_new_position("BUY", max_concurrent=1) is False
    assert ex.can_open_new_position("SELL", max_concurrent=1) is False
    assert ex.can_open_new_position("BUY", max_concurrent=2) is False
    assert ex.can_open_new_position("SELL", max_concurrent=2) is True


def test_simulate_pnl_sign():
    cfg = make_test_cfg()
    symbol_info = make_xau_symbol_info()
    ex = BacktestOrderExecutor(1000.0, cfg, symbol_info)

    plan_buy = TradePlan(direction="BUY", lot_size=1.0, sl_price=1990.0, tp_price=2010.0)
    ex.open_position(plan_buy, at_time=ts1, entry_price=2000.0)
    ticket = ex.positions[0].ticket
    pos_buy = ex.positions[0]
    pnl_up = ex._simulate_pnl(pos_buy, 2002.0)
    pnl_down = ex._simulate_pnl(pos_buy, 1998.0)
    assert pnl_up > 0
    assert pnl_down < 0
    ex.close_position(ticket, at_time=ts2, close_price=2000.0, reason="CLEANUP")

    plan_sell = TradePlan(direction="SELL", lot_size=1.0, sl_price=2010.0, tp_price=1990.0)
    ex.open_position(plan_sell, at_time=ts1, entry_price=2000.0)
    pos_sell = ex.positions[0]
    pnl_down_sell = ex._simulate_pnl(pos_sell, 1998.0)
    pnl_up_sell = ex._simulate_pnl(pos_sell, 2002.0)
    assert pnl_down_sell > 0
    assert pnl_up_sell < 0


def test_is_insufficient_funds_or_margin_by_retcode():
    assert is_insufficient_funds_or_margin(10019, "anything") is True
    assert is_insufficient_funds_or_margin(10009, "Request completed") is False


def test_is_insufficient_funds_or_margin_by_message():
    assert is_insufficient_funds_or_margin(None, "TRADE_RETCODE_NO_MONEY") is True
    assert is_insufficient_funds_or_margin(None, "insufficient funds") is True
    assert is_insufficient_funds_or_margin(None, "not enough margin") is True
    assert is_insufficient_funds_or_margin(None, "some other error") is False


def test_sanitize_mt5_comment_fallback_when_empty():
    assert sanitize_mt5_comment("") == "EA_MA510"
    assert sanitize_mt5_comment(None) == "EA_MA510"


def test_sanitize_mt5_comment_ascii_and_max_len():
    s = "cross_up + entry_trend_1=BULLISH + t1=BULLISH + t2=BULLISH ✓✓✓"
    out = sanitize_mt5_comment(s, max_len=31)
    assert isinstance(out, str)
    assert 1 <= len(out) <= 31
    out.encode("ascii")
