from typing import Optional

from src.config import Config


class MT5Client:
    def __init__(self, cfg: Config):
        self.login_id = cfg.mt5_login
        self.password = cfg.mt5_password
        self.server = cfg.mt5_server
        self.terminal_path = cfg.mt5_terminal_path

    def _import_mt5(self):
        try:
            import MetaTrader5 as mt5
            return mt5
        except ImportError:
            raise RuntimeError(
                "MetaTrader5 package tidak tersedia. "
                "Install via pip install MetaTrader5 atau gunakan mode synthetic untuk backtest."
            )

    def initialize(self) -> bool:
        mt5 = self._import_mt5()
        try:
            if self.terminal_path:
                result = mt5.initialize(self.terminal_path)
            else:
                result = mt5.initialize()
            if not result:
                raise RuntimeError(
                    f"MT5 initialize() gagal. Error code: {mt5.last_error()}"
                )
            return True
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"MT5 initialize() error: {e}")

    def shutdown(self):
        mt5 = self._import_mt5()
        try:
            mt5.shutdown()
        except Exception as e:
            print(f"[WARNING] MT5 shutdown() error: {e}")

    def login(self) -> bool:
        mt5 = self._import_mt5()
        if self.login_id is None or self.password is None or self.server is None:
            print(
                "[WARNING] MT5 login/password/server tidak lengkap. "
                "Mengasumsikan terminal sudah login secara manual."
            )
            return True
        try:
            result = mt5.login(
                self.login_id,
                password=self.password,
                server=self.server,
            )
            if not result:
                raise RuntimeError(
                    f"MT5 login() gagal. Error code: {mt5.last_error()}"
                )
            return True
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"MT5 login() error: {e}")

    def symbol_info(self, symbol: str) -> Optional[dict]:
        mt5 = self._import_mt5()
        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                print(
                    f"[WARNING] mt5.symbol_info({symbol!r}) return None. "
                    f"Last error: {mt5.last_error()}"
                )
                return None
            return {
                "point": info.point,
                "trade_tick_value": info.trade_tick_value,
                "trade_tick_size": info.trade_tick_size,
                "volume_step": info.volume_step,
                "volume_min": info.volume_min,
                "volume_max": info.volume_max,
                "digits": info.digits,
            }
        except Exception as e:
            print(f"[WARNING] mt5.symbol_info({symbol!r}) error: {e}")
            return None
