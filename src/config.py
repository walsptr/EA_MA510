import os
from dataclasses import dataclass
from datetime import date, time
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


class ConfigError(Exception):
    pass


VALID_TIMEFRAMES = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}


@dataclass(frozen=True)
class Config:
    mode: Literal["BACKTEST", "LIVE"]

    symbol: str
    entry_timeframe: str
    trend_timeframe_1: str
    trend_timeframe_2: str

    ma_low: int
    ma_high: int
    ma_type: Literal["SMA", "EMA"]
    trend_ma_low_1: Optional[int]
    trend_ma_high_1: Optional[int]
    trend_ma_low_2: Optional[int]
    trend_ma_high_2: Optional[int]

    backtest_start_date: Optional[date]
    backtest_end_date: Optional[date]
    backtest_warmup_days: int
    backtest_initial_balance: float
    backtest_spread_points: float
    backtest_slippage_points: float
    backtest_use_mt5: bool

    sizing_mode: Literal["FIXED_LOT", "RISK_PERCENT"]
    fixed_lot_size: Optional[float]
    risk_percent_per_trade: Optional[float]

    sl_mode: Literal["FIXED", "ATR", "DOLLAR"]
    sl_points: Optional[float]
    sl_atr_multiplier: Optional[float]
    sl_dollar: Optional[float]
    tp_mode: Literal["FIXED", "ATR", "DOLLAR"]
    tp_points: Optional[float]
    tp_atr_multiplier: Optional[float]
    tp_dollar: Optional[float]
    atr_period: int

    trailing_stop_enabled: bool
    trailing_stop_points: Optional[float]
    trailing_stop_activation_points: Optional[float]

    exit_on_opposite_signal: bool
    max_concurrent_positions: int
    max_spread_points: Optional[float]
    max_daily_loss_percent: Optional[float]
    trading_window_start: Optional[time]
    trading_window_end: Optional[time]

    magic_number: int
    live_poll_interval_seconds: int
    live_warmup_days: int

    mt5_login: Optional[int]
    mt5_password: Optional[str]
    mt5_server: Optional[str]
    mt5_terminal_path: Optional[str]

    log_level: str
    log_dir: str
    report_dir: str
    display_timezone: str


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None or value.strip() == "":
        return None
    return int(value)


def _parse_optional_float(value: Optional[str]) -> Optional[float]:
    if value is None or value.strip() == "":
        return None
    return float(value)


def _parse_date(value: Optional[str]) -> Optional[date]:
    if value is None or value.strip() == "":
        return None
    return date.fromisoformat(value.strip())


def _parse_hhmm(value: Optional[str]) -> Optional[time]:
    if value is None or value.strip() == "":
        return None
    s = value.strip()
    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid HH:MM: {s!r}")
    hh = int(parts[0])
    mm = int(parts[1])
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        raise ValueError(f"Invalid HH:MM: {s!r}")
    return time(hour=hh, minute=mm)


def load_config(use_dotenv: bool = True) -> Config:
    if use_dotenv:
        load_dotenv()

    mode_raw = os.environ.get("MODE")
    if mode_raw not in ("BACKTEST", "LIVE"):
        raise ConfigError(f"MODE harus BACKTEST atau LIVE, got: {mode_raw!r}")
    mode: Literal["BACKTEST", "LIVE"] = mode_raw  # type: ignore[assignment]

    symbol = os.environ.get("SYMBOL")
    if symbol is None or symbol.strip() == "":
        raise ConfigError("SYMBOL wajib diisi")
    symbol = symbol.strip()

    entry_timeframe = os.environ.get("ENTRY_TIMEFRAME", "").strip()
    trend_timeframe_1 = os.environ.get("TREND_TIMEFRAME_1", "").strip()
    trend_timeframe_2 = os.environ.get("TREND_TIMEFRAME_2", "").strip()
    for tf_name, tf_val in (
        ("ENTRY_TIMEFRAME", entry_timeframe),
        ("TREND_TIMEFRAME_1", trend_timeframe_1),
        ("TREND_TIMEFRAME_2", trend_timeframe_2),
    ):
        if tf_val not in VALID_TIMEFRAMES:
            raise ConfigError(
                f"{tf_name} tidak valid ({tf_val!r}), harus salah satu: {sorted(VALID_TIMEFRAMES)}"
            )

    ma_low_raw = os.environ.get("MA_LOW")
    ma_high_raw = os.environ.get("MA_HIGH")
    if ma_low_raw is None or ma_low_raw.strip() == "":
        raise ConfigError("MA_LOW wajib diisi")
    if ma_high_raw is None or ma_high_raw.strip() == "":
        raise ConfigError("MA_HIGH wajib diisi")
    ma_low = int(ma_low_raw)
    ma_high = int(ma_high_raw)
    if ma_low <= 0:
        raise ConfigError(f"MA_LOW harus > 0, got: {ma_low}")
    if ma_high <= 0:
        raise ConfigError(f"MA_HIGH harus > 0, got: {ma_high}")
    if ma_low >= ma_high:
        raise ConfigError(f"MA_LOW ({ma_low}) harus < MA_HIGH ({ma_high})")

    ma_type_raw = os.environ.get("MA_TYPE", "EMA").strip().upper()
    if ma_type_raw not in ("SMA", "EMA"):
        raise ConfigError(f"MA_TYPE harus SMA atau EMA, got: {ma_type_raw!r}")
    ma_type: Literal["SMA", "EMA"] = ma_type_raw  # type: ignore[assignment]

    trend_ma_low_1 = _parse_optional_int(os.environ.get("TREND_MA_LOW_1"))
    trend_ma_high_1 = _parse_optional_int(os.environ.get("TREND_MA_HIGH_1"))
    trend_ma_low_2 = _parse_optional_int(os.environ.get("TREND_MA_LOW_2"))
    trend_ma_high_2 = _parse_optional_int(os.environ.get("TREND_MA_HIGH_2"))
    for pair_name, low, high in (
        ("1", trend_ma_low_1, trend_ma_high_1),
        ("2", trend_ma_low_2, trend_ma_high_2),
    ):
        pair_any_set = (low is not None) or (high is not None)
        if not pair_any_set:
            continue
        if low is None or high is None:
            raise ConfigError(
                f"TREND_MA_LOW_{pair_name} dan TREND_MA_HIGH_{pair_name} harus diisi berpasangan."
            )
        if low <= 0:
            raise ConfigError(f"TREND_MA_LOW_{pair_name} harus > 0, got: {low}")
        if high <= 0:
            raise ConfigError(f"TREND_MA_HIGH_{pair_name} harus > 0, got: {high}")
        if low >= high:
            raise ConfigError(
                f"TREND_MA_LOW_{pair_name} ({low}) harus < TREND_MA_HIGH_{pair_name} ({high})"
            )

    backtest_start_date = _parse_date(os.environ.get("BACKTEST_START_DATE"))
    backtest_end_date = _parse_date(os.environ.get("BACKTEST_END_DATE"))
    if mode == "BACKTEST":
        if backtest_start_date is None:
            raise ConfigError("BACKTEST_START_DATE wajib diisi jika MODE=BACKTEST")
        if backtest_end_date is None:
            raise ConfigError("BACKTEST_END_DATE wajib diisi jika MODE=BACKTEST")
        if backtest_start_date >= backtest_end_date:
            raise ConfigError(
                f"BACKTEST_START_DATE ({backtest_start_date}) harus < BACKTEST_END_DATE ({backtest_end_date})"
            )
    backtest_initial_balance = float(os.environ.get("BACKTEST_INITIAL_BALANCE", "1000"))
    if backtest_initial_balance <= 0:
        raise ConfigError(
            f"BACKTEST_INITIAL_BALANCE harus > 0, got: {backtest_initial_balance}"
        )
    backtest_warmup_days = int(os.environ.get("BACKTEST_WARMUP_DAYS", "0"))
    if backtest_warmup_days < 0:
        raise ConfigError(f"BACKTEST_WARMUP_DAYS harus >= 0, got: {backtest_warmup_days}")
    backtest_spread_points = float(os.environ.get("BACKTEST_SPREAD_POINTS", "0"))
    backtest_slippage_points = float(os.environ.get("BACKTEST_SLIPPAGE_POINTS", "0"))

    backtest_use_mt5_raw = os.environ.get("BACKTEST_USE_MT5")
    if backtest_use_mt5_raw is None or backtest_use_mt5_raw.strip() == "":
        backtest_use_mt5 = os.name == "nt"
    else:
        backtest_use_mt5 = _parse_bool(backtest_use_mt5_raw, False)
    if mode == "BACKTEST" and backtest_use_mt5:
        if os.name != "nt":
            raise ConfigError("BACKTEST_USE_MT5=true hanya didukung di Windows.")
        try:
            import MetaTrader5 as _mt5_probe  # noqa: F401
        except ImportError:
            raise ConfigError(
                "BACKTEST_USE_MT5=true tapi package MetaTrader5 belum terinstall. "
                "Install via: pip install MetaTrader5 (Windows-only), atau set BACKTEST_USE_MT5=false untuk synthetic."
            )

    sizing_mode_raw = os.environ.get("SIZING_MODE", "FIXED_LOT").strip().upper()
    if sizing_mode_raw not in ("FIXED_LOT", "RISK_PERCENT"):
        raise ConfigError(
            f"SIZING_MODE harus FIXED_LOT atau RISK_PERCENT, got: {sizing_mode_raw!r}"
        )
    sizing_mode: Literal["FIXED_LOT", "RISK_PERCENT"] = sizing_mode_raw  # type: ignore[assignment]

    fixed_lot_size = _parse_optional_float(os.environ.get("FIXED_LOT_SIZE"))
    risk_percent_per_trade = _parse_optional_float(os.environ.get("RISK_PERCENT_PER_TRADE"))
    if sizing_mode == "FIXED_LOT":
        if fixed_lot_size is None:
            fixed_lot_size = 0.01
        if fixed_lot_size <= 0:
            raise ConfigError(
                f"FIXED_LOT_SIZE harus > 0 jika SIZING_MODE=FIXED_LOT, got: {fixed_lot_size}"
            )
    else:
        if risk_percent_per_trade is None:
            raise ConfigError("RISK_PERCENT_PER_TRADE wajib diisi jika SIZING_MODE=RISK_PERCENT")
        if risk_percent_per_trade <= 0 or risk_percent_per_trade > 100:
            raise ConfigError(
                f"RISK_PERCENT_PER_TRADE harus > 0 dan <= 100 jika SIZING_MODE=RISK_PERCENT, got: {risk_percent_per_trade}"
            )

    sl_mode_raw = os.environ.get("SL_MODE", "FIXED").strip().upper()
    if sl_mode_raw not in ("FIXED", "ATR", "DOLLAR"):
        raise ConfigError(
            f"SL_MODE harus FIXED, ATR, atau DOLLAR, got: {sl_mode_raw!r}"
        )
    sl_mode: Literal["FIXED", "ATR", "DOLLAR"] = sl_mode_raw  # type: ignore[assignment]

    sl_points = _parse_optional_float(os.environ.get("SL_POINTS"))
    sl_atr_multiplier = _parse_optional_float(os.environ.get("SL_ATR_MULTIPLIER"))
    sl_dollar = _parse_optional_float(os.environ.get("SL_DOLLAR"))
    if sl_mode == "FIXED":
        if sl_points is None or sl_points <= 0:
            raise ConfigError(
                f"SL_POINTS wajib ada dan > 0 jika SL_MODE=FIXED, got: {sl_points}"
            )
    elif sl_mode == "ATR":
        if sl_atr_multiplier is None or sl_atr_multiplier <= 0:
            raise ConfigError(
                f"SL_ATR_MULTIPLIER wajib ada dan > 0 jika SL_MODE=ATR, got: {sl_atr_multiplier}"
            )
    else:
        if sl_dollar is None or sl_dollar <= 0:
            raise ConfigError(
                f"SL_DOLLAR wajib ada dan > 0 jika SL_MODE=DOLLAR, got: {sl_dollar}"
            )

    tp_mode_raw = os.environ.get("TP_MODE", "FIXED").strip().upper()
    if tp_mode_raw not in ("FIXED", "ATR", "DOLLAR"):
        raise ConfigError(
            f"TP_MODE harus FIXED, ATR, atau DOLLAR, got: {tp_mode_raw!r}"
        )
    tp_mode: Literal["FIXED", "ATR", "DOLLAR"] = tp_mode_raw  # type: ignore[assignment]

    tp_points = _parse_optional_float(os.environ.get("TP_POINTS"))
    tp_atr_multiplier = _parse_optional_float(os.environ.get("TP_ATR_MULTIPLIER"))
    tp_dollar = _parse_optional_float(os.environ.get("TP_DOLLAR"))
    if tp_mode == "FIXED":
        if tp_points is None or tp_points <= 0:
            raise ConfigError(
                f"TP_POINTS wajib ada dan > 0 jika TP_MODE=FIXED, got: {tp_points}"
            )
    elif tp_mode == "ATR":
        if tp_atr_multiplier is None or tp_atr_multiplier <= 0:
            raise ConfigError(
                f"TP_ATR_MULTIPLIER wajib ada dan > 0 jika TP_MODE=ATR, got: {tp_atr_multiplier}"
            )
    else:
        if tp_dollar is None or tp_dollar <= 0:
            raise ConfigError(
                f"TP_DOLLAR wajib ada dan > 0 jika TP_MODE=DOLLAR, got: {tp_dollar}"
            )

    atr_period = int(os.environ.get("ATR_PERIOD", "14"))
    if atr_period <= 0:
        raise ConfigError(f"ATR_PERIOD harus > 0, got: {atr_period}")

    trailing_stop_enabled = _parse_bool(os.environ.get("TRAILING_STOP_ENABLED"), False)
    trailing_stop_points = _parse_optional_float(os.environ.get("TRAILING_STOP_POINTS"))
    trailing_stop_activation_points = _parse_optional_float(
        os.environ.get("TRAILING_STOP_ACTIVATION_POINTS")
    )
    if trailing_stop_enabled:
        if trailing_stop_points is None or trailing_stop_points <= 0:
            raise ConfigError(
                f"TRAILING_STOP_POINTS wajib ada dan > 0 jika TRAILING_STOP_ENABLED=true, got: {trailing_stop_points}"
            )
        if trailing_stop_activation_points is None or trailing_stop_activation_points <= 0:
            raise ConfigError(
                f"TRAILING_STOP_ACTIVATION_POINTS wajib ada dan > 0 jika TRAILING_STOP_ENABLED=true, got: {trailing_stop_activation_points}"
            )

    exit_on_opposite_signal = _parse_bool(os.environ.get("EXIT_ON_OPPOSITE_SIGNAL"), False)

    max_concurrent_positions_raw = os.environ.get("MAX_CONCURRENT_POSITIONS", "1")
    max_concurrent_positions = int(max_concurrent_positions_raw)
    if max_concurrent_positions < 1:
        raise ConfigError(
            f"MAX_CONCURRENT_POSITIONS harus >= 1, got: {max_concurrent_positions}"
        )

    max_spread_points = _parse_optional_float(os.environ.get("MAX_SPREAD_POINTS"))
    max_daily_loss_percent = _parse_optional_float(os.environ.get("MAX_DAILY_LOSS_PERCENT"))

    trading_window_start_raw = os.environ.get("TRADING_WINDOW_START")
    trading_window_end_raw = os.environ.get("TRADING_WINDOW_END")
    try:
        trading_window_start = _parse_hhmm(trading_window_start_raw)
        trading_window_end = _parse_hhmm(trading_window_end_raw)
    except Exception as e:
        raise ConfigError(f"TRADING_WINDOW_START/END harus format HH:MM. Error: {e}")
    if (trading_window_start is None) != (trading_window_end is None):
        raise ConfigError("TRADING_WINDOW_START dan TRADING_WINDOW_END harus diisi keduanya atau dikosongkan keduanya.")
    if trading_window_start is not None and trading_window_end is not None:
        if trading_window_start == trading_window_end:
            raise ConfigError("TRADING_WINDOW_START dan TRADING_WINDOW_END tidak boleh sama.")

    magic_number = int(os.environ.get("MAGIC_NUMBER", "20260101"))
    live_poll_interval_seconds = int(os.environ.get("LIVE_POLL_INTERVAL_SECONDS", "5"))
    if live_poll_interval_seconds <= 0:
        raise ConfigError(
            f"LIVE_POLL_INTERVAL_SECONDS harus > 0, got: {live_poll_interval_seconds}"
        )
    live_warmup_days = int(os.environ.get("LIVE_WARMUP_DAYS", "0"))
    if live_warmup_days < 0:
        raise ConfigError(f"LIVE_WARMUP_DAYS harus >= 0, got: {live_warmup_days}")

    mt5_login = _parse_optional_int(os.environ.get("MT5_LOGIN"))
    mt5_password_raw = os.environ.get("MT5_PASSWORD")
    mt5_password = mt5_password_raw if mt5_password_raw and mt5_password_raw.strip() else None
    mt5_server_raw = os.environ.get("MT5_SERVER")
    mt5_server = mt5_server_raw if mt5_server_raw and mt5_server_raw.strip() else None
    mt5_terminal_path_raw = os.environ.get("MT5_TERMINAL_PATH")
    mt5_terminal_path = (
        mt5_terminal_path_raw if mt5_terminal_path_raw and mt5_terminal_path_raw.strip() else None
    )

    log_level_raw = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    if log_level_raw not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        raise ConfigError(
            f"LOG_LEVEL harus DEBUG/INFO/WARNING/ERROR, got: {log_level_raw!r}"
        )
    log_level = log_level_raw
    log_dir = os.environ.get("LOG_DIR", "./logs").strip()
    report_dir = os.environ.get("REPORT_DIR", "./reports").strip()
    display_timezone = os.environ.get("DISPLAY_TIMEZONE", "UTC").strip() or "UTC"
    try:
        ZoneInfo(display_timezone)
    except Exception:
        raise ConfigError(f"DISPLAY_TIMEZONE tidak valid: {display_timezone!r}")

    return Config(
        mode=mode,
        symbol=symbol,
        entry_timeframe=entry_timeframe,
        trend_timeframe_1=trend_timeframe_1,
        trend_timeframe_2=trend_timeframe_2,
        ma_low=ma_low,
        ma_high=ma_high,
        ma_type=ma_type,
        trend_ma_low_1=trend_ma_low_1,
        trend_ma_high_1=trend_ma_high_1,
        trend_ma_low_2=trend_ma_low_2,
        trend_ma_high_2=trend_ma_high_2,
        backtest_start_date=backtest_start_date,
        backtest_end_date=backtest_end_date,
        backtest_warmup_days=backtest_warmup_days,
        backtest_initial_balance=backtest_initial_balance,
        backtest_spread_points=backtest_spread_points,
        backtest_slippage_points=backtest_slippage_points,
        backtest_use_mt5=backtest_use_mt5,
        sizing_mode=sizing_mode,
        fixed_lot_size=fixed_lot_size,
        risk_percent_per_trade=risk_percent_per_trade,
        sl_mode=sl_mode,
        sl_points=sl_points,
        sl_atr_multiplier=sl_atr_multiplier,
        sl_dollar=sl_dollar,
        tp_mode=tp_mode,
        tp_points=tp_points,
        tp_atr_multiplier=tp_atr_multiplier,
        tp_dollar=tp_dollar,
        atr_period=atr_period,
        trailing_stop_enabled=trailing_stop_enabled,
        trailing_stop_points=trailing_stop_points,
        trailing_stop_activation_points=trailing_stop_activation_points,
        exit_on_opposite_signal=exit_on_opposite_signal,
        max_concurrent_positions=max_concurrent_positions,
        max_spread_points=max_spread_points,
        max_daily_loss_percent=max_daily_loss_percent,
        trading_window_start=trading_window_start,
        trading_window_end=trading_window_end,
        magic_number=magic_number,
        live_poll_interval_seconds=live_poll_interval_seconds,
        live_warmup_days=live_warmup_days,
        mt5_login=mt5_login,
        mt5_password=mt5_password,
        mt5_server=mt5_server,
        mt5_terminal_path=mt5_terminal_path,
        log_level=log_level,
        log_dir=log_dir,
        report_dir=report_dir,
        display_timezone=display_timezone,
    )
