import time
from typing import Optional, Any
from src.config import Config
from src.strategy import evaluate_signal, Signal
from src.data_feed import get_latest


class LiveEngine:
    def __init__(self, cfg: Config, logger, mt5_client=None, order_executor=None):
        self.cfg = cfg
        self.logger = logger
        self.mt5_client = mt5_client
        self.order_executor = order_executor
        self._last_processed_entry_candle_time: Optional[Any] = None
        import os
        self._send_real_orders = os.environ.get("LIVE_SEND_REAL_ORDERS", "false").strip().lower() in ("1", "true", "yes", "on")

    def _single_iteration(self) -> bool:
        entry_tf = self.cfg.entry_timeframe
        tf1 = self.cfg.trend_timeframe_1
        tf2 = self.cfg.trend_timeframe_2
        symbol = self.cfg.symbol

        try:
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
            self.logger.info(f"[LIVE] Signal {latest_time}: direction={signal.direction} | reason={signal.reason} | close={signal.entry_timeframe_close_price}")
        else:
            self.logger.info(f"[LIVE] Signal {latest_time}: TIDAK TERDEFINISI (error evaluasi)")

        if signal is not None and signal.direction != "NONE":
            if self._send_real_orders:
                self.logger.warning(f"[LIVE] LIVE_SEND_REAL_ORDERS=true → akan open {signal.direction}. Fitur order_send TIDAK TERIMPLEMENTASI di skeleton ini (gunakan BacktestOrderExecutor untuk test).")
            else:
                self.logger.info(f"[LIVE] WOULD OPEN {signal.direction} @ {signal.entry_timeframe_close_price} | reason={signal.reason} (LIVE_SEND_REAL_ORDERS=false → tidak mengirim order sungguhan)")
        return True

    def run(self, max_iterations: Optional[int] = None) -> None:
        self.logger.info("[LIVE] Starting LiveEngine polling loop...")
        if not self._send_real_orders:
            self.logger.info("[LIVE] ⚠️  Mode DRY-RUN (LIVE_SEND_REAL_ORDERS=false). Tidak akan mengirim order sungguhan.")
        else:
            self.logger.warning("[LIVE] ⚠️  LIVE_SEND_REAL_ORDERS=true! Pastikan Anda menggunakan DEMO account, JANGAN real funded account.")
        it = 0
        try:
            while True:
                cont = self._single_iteration()
                if not cont:
                    self.logger.info("[LIVE] _single_iteration return False → exit loop.")
                    break
                it += 1
                if max_iterations is not None and it >= max_iterations:
                    self.logger.info(f"[LIVE] Mencapai max_iterations={max_iterations} → exit loop (test mode).")
                    break
                time.sleep(max(1, self.cfg.live_poll_interval_seconds))
        except KeyboardInterrupt:
            self.logger.info("[LIVE] KeyboardInterrupt → graceful shutdown.")
        self.logger.info("[LIVE] LiveEngine selesai.")
