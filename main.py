import os
import sys
from datetime import datetime
from src.config import load_config, ConfigError
from src.logger import setup_logger
from src.backtest_engine import run_backtest
from src.reporting import generate_report

try:
    from src.live_engine import LiveEngine
    _LIVE_ENGINE_AVAILABLE = True
except ImportError as e:
    _LIVE_ENGINE_AVAILABLE = False
    _LIVE_IMPORT_ERROR = str(e)


def main() -> int:
    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"[CONFIG ERROR] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[UNEXPECTED ERROR saat load config] {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    try:
        os.makedirs(cfg.log_dir, exist_ok=True)
        os.makedirs(cfg.report_dir, exist_ok=True)
    except Exception as e:
        print(f"[IO ERROR] Gagal buat direktori log/report: {e}", file=sys.stderr)
        return 1

    try:
        logger = setup_logger(cfg.log_dir, cfg.log_level)
    except Exception as e:
        print(f"[LOGGER ERROR] {e}", file=sys.stderr)
        return 1

    logger.info("=" * 60)
    logger.info(f"EA MA510 MA Cross Trend-Following Bot STARTUP")
    logger.info(f"MODE = {cfg.mode}")
    logger.info(f"SYMBOL = {cfg.symbol} | ENTRY_TF = {cfg.entry_timeframe}")
    logger.info(f"TREND_TF1 = {cfg.trend_timeframe_1} | TREND_TF2 = {cfg.trend_timeframe_2}")
    logger.info(f"MA(LOW={cfg.ma_low}, HIGH={cfg.ma_high}, TYPE={cfg.ma_type})")
    logger.info(f"SIZING = {cfg.sizing_mode} | SL_MODE = {cfg.sl_mode} | TP_MODE = {cfg.tp_mode}")
    logger.info("=" * 60)

    exit_code = 0
    try:
        if cfg.mode == "BACKTEST":
            logger.info(f"[MAIN] Starting BACKTEST mode: {cfg.backtest_start_date} → {cfg.backtest_end_date}")
            logger.info(f"[MAIN] Initial balance = ${cfg.backtest_initial_balance:,.2f}")
            import os as _os
            use_mt5_env = _os.environ.get("BACKTEST_USE_MT5", "false").strip().lower() in ("1", "true", "yes", "on")
            use_mt5 = use_mt5_env
            if use_mt5_env:
                try:
                    import MetaTrader5 as _mt5_probe  # noqa: F401
                    logger.info("[MAIN] BACKTEST_USE_MT5=true → mencoba menggunakan data riil MT5. Jika gagal fallback ke synthetic.")
                except ImportError:
                    logger.warning(
                        "[MAIN] ⚠️  BACKTEST_USE_MT5=true tapi package MetaTrader5 TIDAK TERINSTALL / TIDAK TERSEDIA di OS ini. "
                        "MetaTrader5 PyPI package HANYA BERJALAN DI WINDOWS (butuh MT5 Terminal.exe). "
                        "AUTO FALLBACK ke SYNTHETIC data (tidak perlu install MT5)."
                    )
                    use_mt5 = False
            else:
                logger.info("[MAIN] Menggunakan SYNTHETIC data (BACKTEST_USE_MT5=false). Tidak memerlukan MT5 terminal.")

            trade_log, equity_curve = run_backtest(cfg, use_mt5=use_mt5)
            logger.info(f"[MAIN] Backtest selesai: {len(trade_log)} trade log entries, {len(equity_curve)} equity curve points.")

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(cfg.report_dir, f"backtest_{ts}")

            summary = generate_report(trade_log, equity_curve, output_dir, cfg)
            logger.info(f"[MAIN] Report di-generate ke: {output_dir}")

            logger.info("-" * 40)
            logger.info(f"[REPORT] Total Trades        : {summary.get('total_trades', 0)}")
            logger.info(f"[REPORT] Win Rate            : {summary.get('win_rate_pct', 0):.2f}%")
            logger.info(f"[REPORT] Profit Factor       : {summary.get('profit_factor', 0):.4f}")
            logger.info(f"[REPORT] Total Return        : {summary.get('total_return_pct', 0):.2f}%")
            logger.info(f"[REPORT] Max Drawdown        : {summary.get('max_drawdown_pct', 0):.2f}%")
            logger.info(f"[REPORT] Expectancy / Trade  : ${summary.get('expectancy_per_trade', 0):.4f}")
            logger.info(f"[REPORT] Periode             : {summary.get('start_date', '?')} → {summary.get('end_date', '?')}")
            logger.info("-" * 40)
            logger.info(f"[MAIN] BACKTEST mode selesai sukses.")

        elif cfg.mode == "LIVE":
            logger.info("[MAIN] Starting LIVE mode...")
            logger.warning("[MAIN] ⚠️  PERINGATAN: Selalu gunakan DEMO account untuk mode LIVE sampai Anda 100% yakin perilaku bot. JANGAN pernah gunakan account funded REAL sebelum divalidasi berulang kali.")
            if not _LIVE_ENGINE_AVAILABLE:
                logger.error(f"[MAIN] LiveEngine tidak tersedia (ImportError: {_LIVE_IMPORT_ERROR}). Mode LIVE tidak bisa dijalankan.")
                exit_code = 2
            else:
                engine = LiveEngine(cfg, logger, mt5_client=None, order_executor=None)
                engine.run(max_iterations=None)
                logger.info("[MAIN] LIVE mode selesai.")
        else:
            logger.error(f"[MAIN] MODE tidak dikenal: {cfg.mode}")
            exit_code = 1

    except KeyboardInterrupt:
        logger.info("[MAIN] Diterima KeyboardInterrupt → shutdown...")
        exit_code = 0
    except Exception as e:
        logger.exception(f"[MAIN] FATAL ERROR selama eksekusi {cfg.mode}: {type(e).__name__}: {e}")
        exit_code = 1
    finally:
        logger.info(f"[MAIN] Exit code = {exit_code}")
        logger.info("=" * 60)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
