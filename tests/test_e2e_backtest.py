import pytest
import pandas
import tempfile
import os
import json
import sys
from datetime import date

from src.backtest_engine import run_backtest
from src.reporting import generate_report
from src.config import Config


def make_e2e_cfg(tmpdir, **overrides) -> Config:
    log_dir = os.path.join(tmpdir, "logs")
    report_dir = os.path.join(tmpdir, "reports")
    base = dict(
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
        backtest_end_date=date(2025, 1, 5),
        backtest_warmup_days=0,
        backtest_initial_balance=1000.0,
        backtest_spread_points=0,
        backtest_slippage_points=0,
        backtest_use_mt5=False,
        sizing_mode="FIXED_LOT",
        fixed_lot_size=0.5,
        risk_percent_per_trade=None,
        sl_mode="DOLLAR",
        sl_points=None,
        sl_atr_multiplier=None,
        sl_dollar=5.0,
        tp_mode="DOLLAR",
        tp_points=None,
        tp_atr_multiplier=None,
        tp_dollar=15.0,
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
        magic_number=99999,
        live_poll_interval_seconds=5,
        live_warmup_days=0,
        mt5_login=None,
        mt5_password=None,
        mt5_server=None,
        mt5_terminal_path=None,
        log_level="INFO",
        log_dir=log_dir,
        report_dir=report_dir,
        display_timezone="UTC",
    )
    base.update(overrides)
    return Config(**base)


def test_e2e_run_backtest_synthetic_dollar_mode_no_exception():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = make_e2e_cfg(tmpdir)
        trade_log, equity_curve = run_backtest(cfg, use_mt5=False)
        assert isinstance(trade_log, list)
        assert isinstance(equity_curve, list)
        assert len(equity_curve) >= 1


def test_trade_sl_tp_invariants_buy_sell():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = make_e2e_cfg(tmpdir)
        trade_log, equity_curve = run_backtest(cfg, use_mt5=False)
        valid_close_reasons = {"SL_HIT", "TP_HIT", "OPPOSITE_SIGNAL", "TRAILING_STOP", "MANUAL", "EOD_BACKTEST"}
        for t in trade_log:
            closed = (getattr(t, 'pnl', None) is not None) or (getattr(t, 'close_reason', None) is not None)
            if not closed:
                continue
            if t.direction == "BUY":
                assert t.sl_price is not None
                assert t.tp_price is not None
                assert t.sl_price < t.open_price, f"BUY SL >= open: sl={t.sl_price}, open={t.open_price}"
                assert t.open_price < t.tp_price, f"BUY open >= TP: open={t.open_price}, tp={t.tp_price}"
            elif t.direction == "SELL":
                assert t.sl_price is not None
                assert t.tp_price is not None
                assert t.tp_price < t.open_price, f"SELL TP >= open: tp={t.tp_price}, open={t.open_price}"
                assert t.open_price < t.sl_price, f"SELL open >= SL: open={t.open_price}, sl={t.sl_price}"
            if getattr(t, 'close_reason', None):
                assert t.close_reason in valid_close_reasons, f"Invalid close_reason: {t.close_reason}"


def test_report_files_exist_and_summary_matches():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = make_e2e_cfg(tmpdir)
        trade_log, equity_curve = run_backtest(cfg, use_mt5=False)
        output_dir = os.path.join(cfg.report_dir, "test_e2e_run")
        summary = generate_report(trade_log, equity_curve, output_dir, cfg)
        assert os.path.exists(os.path.join(output_dir, "trades.csv"))
        assert os.path.exists(os.path.join(output_dir, "equity_curve.csv"))
        assert os.path.exists(os.path.join(output_dir, "summary.json"))
        closed_from_log = len([t for t in trade_log if getattr(t, 'pnl', None) is not None])
        assert summary["total_trades"] == closed_from_log, f"summary.total_trades={summary['total_trades']} != closed_from_log={closed_from_log}"
        with open(os.path.join(output_dir, "summary.json"), "r") as f:
            loaded = json.load(f)
        assert "config_snapshot" in loaded
        assert "profit_factor" in loaded
        assert isinstance(loaded["profit_factor"], (int, float))


def test_live_engine_init_and_one_iteration(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = os.path.join(tmpdir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        from src.logger import setup_logger
        logger = setup_logger(log_dir, "WARNING")
        cfg = make_e2e_cfg(tmpdir, mode="LIVE")
        import src.live_engine as live_engine_module

        idx = pandas.date_range("2025-01-01", periods=210, freq="5min", tz="UTC")
        df = pandas.DataFrame(
            {
                "open": [1.0] * len(idx),
                "high": [1.0] * len(idx),
                "low": [1.0] * len(idx),
                "close": [1.0] * len(idx),
            },
            index=idx,
        )

        monkeypatch.setattr(live_engine_module, "get_latest", lambda *_args, **_kwargs: df)
        monkeypatch.setattr(live_engine_module, "get_latest_by_days", lambda *_args, **_kwargs: df)
        monkeypatch.setattr(
            live_engine_module,
            "evaluate_signal",
            lambda _candles, _cfg: live_engine_module.Signal(
                direction="NONE",
                reason="test",
                entry_time=df.index[-1],
                entry_timeframe_close_price=float(df.close.iloc[-1]),
            ),
        )

        class FakeMT5Client:
            def account_info(self):
                return {"balance": 1000.0, "equity": 1000.0}

        from src.live_engine import LiveEngine
        engine = LiveEngine(cfg, logger, mt5_client=FakeMT5Client(), order_executor=None)
        engine.run(max_iterations=1)


def test_main_backtest_smoke_script_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_overrides = {
            "MODE": "BACKTEST",
            "SYMBOL": "XAUUSDm",
            "ENTRY_TIMEFRAME": "M5",
            "TREND_TIMEFRAME_1": "M15",
            "TREND_TIMEFRAME_2": "M30",
            "MA_LOW": "5",
            "MA_HIGH": "10",
            "MA_TYPE": "EMA",
            "BACKTEST_START_DATE": "2025-01-01",
            "BACKTEST_END_DATE": "2025-01-03",
            "BACKTEST_INITIAL_BALANCE": "5000",
            "SIZING_MODE": "FIXED_LOT",
            "FIXED_LOT_SIZE": "0.1",
            "SL_MODE": "DOLLAR",
            "SL_DOLLAR": "10.0",
            "TP_MODE": "DOLLAR",
            "TP_DOLLAR": "30.0",
            "ATR_PERIOD": "14",
            "MAGIC_NUMBER": "12345",
            "LOG_LEVEL": "WARNING",
            "LOG_DIR": os.path.join(tmpdir, "logs"),
            "REPORT_DIR": os.path.join(tmpdir, "reports"),
            "BACKTEST_USE_MT5": "false",
        }
        old_env = {k: os.environ.get(k) for k in env_overrides}
        for k, v in env_overrides.items():
            os.environ[k] = v
        try:
            import subprocess
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env = os.environ.copy()
            env.update(env_overrides)
            env["PYTHONPATH"] = project_root
            result = subprocess.run(
                [sys.executable, "-c", """
import sys
import os
sys.path.insert(0, os.environ.get('PYTHONPATH', ''))
from main import main
sys.exit(main())
"""],
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
                cwd=project_root,
            )
            if result.returncode != 0:
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
            assert result.returncode == 0, f"main() exit code {result.returncode}. stderr: {result.stderr[-500:]}"
        finally:
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
