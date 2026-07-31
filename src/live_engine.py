import time
from typing import Optional, Any
import pandas as pd
from src.config import Config
from src.strategy import evaluate_signal, Signal
from src.data_feed import get_latest, get_latest_by_days
from src.indicators import atr as atr_fn
from src.mt5_client import MT5Client
from src.order_executor import LiveOrderExecutor, InsufficientFundsOrMarginError
from src.risk_manager import compute_trade_plan, Signal as RiskSignal, SymbolInfo as RiskSymbolInfo


class LiveEngine:
    def __init__(self, cfg: Config, logger, mt5_client=None, order_executor=None):
        self.cfg = cfg
        self.logger = logger
        self.mt5_client = mt5_client
        self.order_executor = order_executor
        self._last_processed_entry_candle_time: Optional[Any] = None
        self._owns_mt5_client = False

    def _single_iteration(self) -> bool:
        entry_tf = self.cfg.entry_timeframe
        tf1 = self.cfg.trend_timeframe_1
        tf2 = self.cfg.trend_timeframe_2
        symbol = self.cfg.symbol

        try:
            lookback_days = getattr(self.cfg, "live_warmup_days", 0) or 0
            if lookback_days > 0:
                entry_df = get_latest_by_days(symbol, entry_tf, lookback_days=lookback_days)
                tf1_df = get_latest_by_days(symbol, tf1, lookback_days=lookback_days)
                tf2_df = get_latest_by_days(symbol, tf2, lookback_days=lookback_days)
            else:
                entry_df = get_latest(symbol, entry_tf, n=200)
                tf1_df = get_latest(symbol, tf1, n=200)
                tf2_df = get_latest(symbol, tf2, n=200)
        except Exception as e:
            self.logger.warning(f"[LIVE] Gagal fetch candles: {e}. Akan retry.")
            return True

        if len(entry_df) == 0:
            self.logger.warning("[LIVE] entry_df kosong (tanpa data). Pastikan MT5 tersedia atau gunakan MODE=BACKTEST.")
            return True

        latest_entry = entry_df.iloc[-1]
        latest_time = latest_entry.time if "time" in latest_entry.index else latest_entry.name
        tz = getattr(self.cfg, "display_timezone", "UTC") or "UTC"
        try:
            ts = pd.Timestamp(latest_time)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            ts_disp = ts.tz_convert(tz)
            latest_time_disp = ts_disp.isoformat()
        except Exception:
            latest_time_disp = str(latest_time)

        if latest_time == self._last_processed_entry_candle_time:
            return True

        candles_dict = {entry_tf: entry_df, tf1: tf1_df, tf2: tf2_df}
        try:
            signal = evaluate_signal(candles_dict, self.cfg)
        except Exception as e:
            self.logger.error(f"[LIVE] evaluate_signal error: {e}")
            signal = None

        self._last_processed_entry_candle_time = latest_time

        if signal is not None:
            self.logger.info(f"[LIVE] Signal {latest_time_disp}: direction={signal.direction} | reason={signal.reason} | close={signal.entry_timeframe_close_price}")
        else:
            self.logger.info(f"[LIVE] Signal {latest_time_disp}: TIDAK TERDEFINISI (error evaluasi)")

        if signal is not None and signal.direction != "NONE":
            start = getattr(self.cfg, "trading_window_start", None)
            end = getattr(self.cfg, "trading_window_end", None)
            if start is not None and end is not None:
                try:
                    tod = ts_disp.time()
                    within = (start <= tod < end) if (start < end) else (tod >= start or tod < end)
                except Exception:
                    within = True
                if not within:
                    self.logger.info(f"[LIVE] SKIP entry (outside trading window) {latest_time_disp}")
                    return True
            if self.cfg.max_spread_points is not None and "spread" in latest_entry.index:
                try:
                    if float(latest_entry.spread) > float(self.cfg.max_spread_points):
                        self.logger.info(f"[LIVE] SKIP entry (spread too high) {latest_time_disp} spread={latest_entry.spread} max={self.cfg.max_spread_points}")
                        return True
                except Exception:
                    pass
            if self.mt5_client is None:
                self.logger.error("[LIVE] mt5_client is None -> cannot place orders.")
                return True

            if self.order_executor is None:
                self.order_executor = LiveOrderExecutor(self.cfg, logger=self.logger)

            try:
                if hasattr(self.order_executor, "can_open_new_position"):
                    if not self.order_executor.can_open_new_position(signal.direction, self.cfg.max_concurrent_positions, symbol=symbol):
                        self.logger.info(f"[LIVE] SKIP entry (max_concurrent_positions / existing direction) {latest_time_disp}")
                        return True
            except Exception as e:
                self.logger.warning(f"[LIVE] Failed to evaluate open-position constraints: {e}. Will continue.")

            acct = None
            try:
                acct = self.mt5_client.account_info()
            except Exception as e:
                self.logger.warning(f"[LIVE] Failed to read account_info: {e}")

            if acct is None:
                self.logger.warning("[LIVE] account_info unavailable -> skip order placement this cycle.")
                return True

            equity = float(acct.get("equity", 0.0))
            sym_info_raw = self.mt5_client.symbol_info(symbol)
            if sym_info_raw is None:
                self.logger.warning(f"[LIVE] symbol_info unavailable for {symbol!r} -> skip order placement this cycle.")
                return True

            sym_info = RiskSymbolInfo(**sym_info_raw)

            atr_value = None
            if self.cfg.sl_mode == "ATR" or self.cfg.tp_mode == "ATR":
                try:
                    atr_series = atr_fn(entry_df.high, entry_df.low, entry_df.close, self.cfg.atr_period)
                    atr_clean = atr_series.dropna()
                    if len(atr_clean) > 0:
                        atr_value = float(atr_clean.iloc[-1])
                except Exception:
                    atr_value = None

            risk_sig = RiskSignal(
                direction=signal.direction,
                entry_timeframe_close_price=signal.entry_timeframe_close_price,
            )
            plan = compute_trade_plan(risk_sig, self.cfg, sym_info, equity, atr_value)
            if plan is None:
                self.logger.info(f"[LIVE] SKIP entry (trade plan rejected by risk manager) {latest_time_disp}")
                return True

            try:
                result = self.order_executor.open_position(
                    plan=plan,
                    at_time=latest_time,
                    signal_reason=signal.reason,
                    symbol=symbol,
                )
            except InsufficientFundsOrMarginError as e:
                self.logger.error(f"[LIVE] STOP: order rejected due to insufficient funds/margin: {e}")
                return False
            except Exception as e:
                self.logger.error(f"[LIVE] order_executor.open_position error: {e}")
                return True

            if result.success:
                self.logger.info(f"[LIVE] Order opened: position_id={result.position_id} | {result.message}")
            else:
                self.logger.warning(f"[LIVE] Order failed: {result.message}")
        return True

    def run(self, max_iterations: Optional[int] = None) -> None:
        self.logger.info("[LIVE] Starting LiveEngine polling loop...")
        it = 0

        if self.mt5_client is None:
            self.mt5_client = MT5Client(self.cfg)
            self._owns_mt5_client = True

        if self._owns_mt5_client:
            try:
                self.mt5_client.initialize()
                self.mt5_client.login()
            except Exception as e:
                self.logger.error(f"[LIVE] MT5 connect/login failed: {e}")
                try:
                    self.mt5_client.shutdown()
                except Exception:
                    pass
                return

        try:
            while True:
                try:
                    acct = self.mt5_client.account_info() if self.mt5_client is not None else None
                except Exception:
                    acct = None

                if acct is not None:
                    try:
                        bal = float(acct.get("balance", 0.0))
                        eq = float(acct.get("equity", 0.0))
                        if bal <= 0 or eq <= 0:
                            self.logger.error(f"[LIVE] STOP: account balance/equity <= 0 (balance={bal}, equity={eq}). Exiting loop.")
                            break
                    except Exception:
                        pass

                cont = self._single_iteration()
                if not cont:
                    self.logger.info("[LIVE] _single_iteration return False -> exit loop.")
                    break
                it += 1
                if max_iterations is not None and it >= max_iterations:
                    self.logger.info(f"[LIVE] Mencapai max_iterations={max_iterations} -> exit loop (test mode).")
                    break
                time.sleep(max(1, self.cfg.live_poll_interval_seconds))
        except KeyboardInterrupt:
            self.logger.info("[LIVE] KeyboardInterrupt -> graceful shutdown.")
        finally:
            if self._owns_mt5_client and self.mt5_client is not None:
                try:
                    self.mt5_client.shutdown()
                except Exception as e:
                    self.logger.warning(f"[LIVE] MT5 shutdown error: {e}")
        self.logger.info("[LIVE] LiveEngine selesai.")
