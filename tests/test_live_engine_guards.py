import os
import sys
import logging
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.live_engine as live_engine_module
from src.config import Config
from src.live_engine import LiveEngine


def make_live_cfg() -> Config:
    return Config(
        mode="LIVE",
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
        live_poll_interval_seconds=1,
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


class FakeMT5Client:
    def __init__(self, balance: float, equity: float):
        self._balance = balance
        self._equity = equity
        self.shutdown_called = False

    def account_info(self):
        return {"balance": self._balance, "equity": self._equity}

    def shutdown(self):
        self.shutdown_called = True


def test_live_engine_stops_when_balance_non_positive(monkeypatch):
    cfg = make_live_cfg()
    logger = logging.getLogger("test_live_engine_stops_when_balance_non_positive")
    mt5_client = FakeMT5Client(balance=0.0, equity=100.0)
    engine = LiveEngine(cfg, logger, mt5_client=mt5_client, order_executor=None)

    def _should_not_run_iteration():
        raise AssertionError("_single_iteration should not be called when account balance/equity <= 0")

    monkeypatch.setattr(engine, "_single_iteration", _should_not_run_iteration)
    monkeypatch.setattr(live_engine_module.time, "sleep", lambda *_: None)

    engine.run(max_iterations=10)
    assert mt5_client.shutdown_called is False


def test_live_engine_stops_when_equity_non_positive(monkeypatch):
    cfg = make_live_cfg()
    logger = logging.getLogger("test_live_engine_stops_when_equity_non_positive")
    mt5_client = FakeMT5Client(balance=100.0, equity=0.0)
    engine = LiveEngine(cfg, logger, mt5_client=mt5_client, order_executor=None)

    def _should_not_run_iteration():
        raise AssertionError("_single_iteration should not be called when account balance/equity <= 0")

    monkeypatch.setattr(engine, "_single_iteration", _should_not_run_iteration)
    monkeypatch.setattr(live_engine_module.time, "sleep", lambda *_: None)

    engine.run(max_iterations=10)
    assert mt5_client.shutdown_called is False

