from datetime import date, datetime, timedelta
from typing import Optional
import random

import pandas as pd
import numpy as np

from src.config import Config


TIMEFRAME_DURATION_MAP: dict[str, timedelta] = {
    "M1": timedelta(minutes=1),
    "M5": timedelta(minutes=5),
    "M15": timedelta(minutes=15),
    "M30": timedelta(minutes=30),
    "H1": timedelta(hours=1),
    "H4": timedelta(hours=4),
    "D1": timedelta(hours=24),
}

TIMEFRAME_MAP: dict[str, Optional[int]] = {
    "M1": None,
    "M5": None,
    "M15": None,
    "M30": None,
    "H1": None,
    "H4": None,
    "D1": None,
}

_SCHEMA_COLUMNS = [
    "time", "close_time", "open", "high", "low", "close",
    "tick_volume", "spread",
]


def _empty_schema_df() -> pd.DataFrame:
    return pd.DataFrame(columns=_SCHEMA_COLUMNS)


def _mt5_timeframe(tf_str: str):
    try:
        import MetaTrader5 as mt5
    except ImportError:
        raise RuntimeError(
            "MetaTrader5 package tidak tersedia. "
            "Install via pip install MetaTrader5 atau gunakan mode synthetic untuk backtest."
        )
    mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    for k, v in mapping.items():
        TIMEFRAME_MAP[k] = v
    if tf_str not in mapping:
        raise ValueError(f"Unknown timeframe: {tf_str}")
    return mapping[tf_str]


def _rates_to_df(rates, timeframe: str) -> pd.DataFrame:
    if rates is None or len(rates) == 0:
        return _empty_schema_df()
    df = pd.DataFrame(rates)
    if "time" not in df.columns:
        df = pd.DataFrame(list(rates))
    if "time" not in df.columns:
        raise RuntimeError(
            f"MT5 rates schema tidak punya kolom 'time'. columns={list(df.columns)}"
        )
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    duration = TIMEFRAME_DURATION_MAP[timeframe]
    df["close_time"] = df["time"] + duration
    if "spread" not in df.columns:
        df["spread"] = 0
    else:
        df["spread"] = df["spread"].fillna(0).astype(int)
    if "tick_volume" not in df.columns:
        df["tick_volume"] = 0
    else:
        df["tick_volume"] = df["tick_volume"].fillna(0).astype(int)
    df = df[_SCHEMA_COLUMNS].sort_values("time").reset_index(drop=True)
    return df


def get_history(
    symbol: str,
    timeframe: str,
    start_date: date,
    end_date: date,
    raise_on_error: bool = False,
) -> pd.DataFrame:
    try:
        import MetaTrader5 as mt5
        tf_const = _mt5_timeframe(timeframe)
        start_dt = datetime(start_date.year, start_date.month, start_date.day)
        end_dt = datetime(
            end_date.year, end_date.month, end_date.day
        ) + timedelta(days=1)
        rates = mt5.copy_rates_range(symbol, tf_const, start_dt, end_dt)
        df = _rates_to_df(rates, timeframe)
        if raise_on_error and len(df) == 0:
            raise RuntimeError(
                f"MT5 history kosong untuk {symbol} TF={timeframe} ({start_date} -> {end_date}). "
                f"Last error: {mt5.last_error()}"
            )
        return df
    except Exception as e:
        if raise_on_error:
            raise
        print(
            f"[WARNING] get_history({symbol!r}, {timeframe!r}, "
            f"{start_date}, {end_date}) error: {e}. Returning empty DataFrame."
        )
        return _empty_schema_df()


def get_latest(symbol: str, timeframe: str, n: int = 200) -> pd.DataFrame:
    try:
        import MetaTrader5 as mt5
        tf_const = _mt5_timeframe(timeframe)
        rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, n)
        return _rates_to_df(rates, timeframe)
    except Exception as e:
        print(
            f"[WARNING] get_latest({symbol!r}, {timeframe!r}, n={n}) "
            f"error: {e}. Returning empty DataFrame."
        )
        return _empty_schema_df()


def _to_dt(d) -> datetime:
    if isinstance(d, datetime):
        return d
    return datetime(d.year, d.month, d.day)


def _pattern_flat(n_candles: int, base_price: float, digits: int) -> list[float]:
    closes = []
    for i in range(n_candles):
        noise_pct = random.uniform(-0.0005, 0.0005)
        c = base_price * (1 + noise_pct)
        closes.append(round(c, digits))
    return closes


def _pattern_bull_cross_then_bear(
    n_candles: int, base_price: float, digits: int
) -> list[float]:
    if n_candles < 100:
        n_candles = 100
    closes = []
    bottom_price = base_price * 0.995
    peak_price = base_price * 1.005
    end_down = base_price * 0.998

    seg = n_candles // 5
    seg0_end = seg * 1
    seg1_end = seg * 2
    seg2_end = seg * 3
    seg3_end = seg * 4

    for i in range(n_candles):
        if i < seg0_end:
            t = i / max(seg0_end - 1, 1)
            c = base_price - (base_price - bottom_price) * t
        elif i < seg1_end:
            t = (i - seg0_end) / max(seg1_end - seg0_end - 1, 1)
            mid = (bottom_price + bottom_price * 1.001) / 2
            amp = (bottom_price * 1.001 - bottom_price) / 2
            c = mid + amp * np.sin(t * 4 * np.pi)
        elif i < seg2_end:
            t = (i - seg1_end) / max(seg2_end - seg1_end - 1, 1)
            c = bottom_price + (peak_price - bottom_price) * t
        elif i < seg3_end:
            t = (i - seg2_end) / max(seg3_end - seg2_end - 1, 1)
            c = peak_price - (peak_price - end_down) * t
        else:
            t = (i - seg3_end) / max(n_candles - seg3_end - 1, 1)
            c = end_down + (base_price - end_down) * t
        noise = random.uniform(-base_price * 0.0003, base_price * 0.0003)
        closes.append(round(c + noise, digits))
    return closes


def _pattern_bear_cross(
    n_candles: int, base_price: float, digits: int
) -> list[float]:
    if n_candles < 100:
        n_candles = 100
    closes = []
    peak_price = base_price * 1.005
    bottom_price = base_price * 0.995
    end_up = base_price * 1.002

    seg = n_candles // 5
    seg0_end = seg * 1
    seg1_end = seg * 2
    seg2_end = seg * 3
    seg3_end = seg * 4

    for i in range(n_candles):
        if i < seg0_end:
            t = i / max(seg0_end - 1, 1)
            c = base_price + (peak_price - base_price) * t
        elif i < seg1_end:
            t = (i - seg0_end) / max(seg1_end - seg0_end - 1, 1)
            mid = (peak_price + peak_price * 0.999) / 2
            amp = (peak_price - peak_price * 0.999) / 2
            c = mid + amp * np.sin(t * 4 * np.pi)
        elif i < seg2_end:
            t = (i - seg1_end) / max(seg2_end - seg1_end - 1, 1)
            c = peak_price - (peak_price - bottom_price) * t
        elif i < seg3_end:
            t = (i - seg2_end) / max(seg3_end - seg2_end - 1, 1)
            c = bottom_price + (end_up - bottom_price) * t
        else:
            t = (i - seg3_end) / max(n_candles - seg3_end - 1, 1)
            c = end_up + (base_price - end_up) * t
        noise = random.uniform(-base_price * 0.0003, base_price * 0.0003)
        closes.append(round(c + noise, digits))
    return closes


def generate_synthetic_candles(
    timeframe: str,
    start: date | datetime,
    end: date | datetime,
    pattern: str = "bull_cross_then_bear",
    base_price: float = 2000.0,
    digits: int = 2,
) -> pd.DataFrame:
    duration = TIMEFRAME_DURATION_MAP[timeframe]
    start_dt = _to_dt(start)
    end_dt = _to_dt(end)

    times = []
    t = start_dt
    while t < end_dt:
        times.append(t)
        t = t + duration

    if pattern == "bull_cross_then_bear":
        required_n = 101
        while len(times) < required_n:
            last = times[-1] if times else start_dt
            times.append(last + duration)
        n = len(times)
        closes = _pattern_bull_cross_then_bear(n, base_price, digits)
    elif pattern == "bear_cross":
        required_n = 101
        while len(times) < required_n:
            last = times[-1] if times else start_dt
            times.append(last + duration)
        n = len(times)
        closes = _pattern_bear_cross(n, base_price, digits)
    elif pattern == "flat":
        required_n = 20
        while len(times) < required_n:
            last = times[-1] if times else start_dt
            times.append(last + duration)
        n = len(times)
        closes = _pattern_flat(n, base_price, digits)
    else:
        raise ValueError(f"Unknown pattern: {pattern!r}")

    n = len(times)
    opens = [0.0] * n
    highs = [0.0] * n
    lows = [0.0] * n
    tick_volume = [0] * n
    spread = [0] * n

    prev_close = base_price
    for i in range(n):
        c = closes[i]
        o = prev_close if i > 0 else c
        rng = abs(c - o)
        if rng < base_price * 0.0002:
            rng = base_price * 0.0002
        extra_high = random.uniform(0, rng * 0.5)
        extra_low = random.uniform(0, rng * 0.5)
        h = max(o, c) + extra_high
        l = min(o, c) - extra_low
        opens[i] = round(o, digits)
        highs[i] = round(h, digits)
        lows[i] = round(l, digits)
        tick_volume[i] = random.randint(50, 500)
        spread[i] = random.randint(10, 40)
        prev_close = c

    close_times = [ts + duration for ts in times]

    df = pd.DataFrame({
        "time": pd.to_datetime(times, utc=True),
        "close_time": pd.to_datetime(close_times, utc=True),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "tick_volume": tick_volume,
        "spread": spread,
    })
    df = df.sort_values("time").reset_index(drop=True)
    return df


def _resample_entry_to_higher(
    entry_df: pd.DataFrame,
    entry_tf: str,
    higher_tf: str,
) -> pd.DataFrame:
    entry_dur = TIMEFRAME_DURATION_MAP[entry_tf]
    higher_dur = TIMEFRAME_DURATION_MAP[higher_tf]
    ratio = int(higher_dur / entry_dur)
    if ratio <= 0:
        ratio = 1

    rows = []
    for start_idx in range(0, len(entry_df), ratio):
        chunk = entry_df.iloc[start_idx:start_idx + ratio]
        if len(chunk) == 0:
            continue
        rows.append({
            "time": chunk.time.iloc[0],
            "close_time": chunk.close_time.iloc[-1],
            "open": chunk.open.iloc[0],
            "high": chunk.high.max(),
            "low": chunk.low.min(),
            "close": chunk.close.iloc[-1],
            "tick_volume": int(chunk.tick_volume.sum()),
            "spread": int(chunk.spread.iloc[-1]),
        })
    df = pd.DataFrame(rows, columns=_SCHEMA_COLUMNS)
    return df


def get_synthetic_for_all_timeframes(cfg: Config) -> dict[str, pd.DataFrame]:
    start = cfg.backtest_start_date or date(2025, 1, 1)
    end = cfg.backtest_end_date or date(2025, 1, 31)

    entry_tf = cfg.entry_timeframe
    entry_duration = TIMEFRAME_DURATION_MAP[entry_tf]
    entry_start_dt = _to_dt(start)
    entry_end_needed = entry_start_dt + entry_duration * 200
    entry_end_dt = max(_to_dt(end), entry_end_needed)

    entry_df = generate_synthetic_candles(
        entry_tf, entry_start_dt, entry_end_dt,
        pattern="bull_cross_then_bear",
        base_price=2000.0, digits=2,
    )

    tf1 = cfg.trend_timeframe_1
    tf1_df = _resample_entry_to_higher(entry_df, entry_tf, tf1)
    if len(tf1_df) < 20:
        tf1_start = _to_dt(start)
        tf1_dur = TIMEFRAME_DURATION_MAP[tf1]
        tf1_end = tf1_start + tf1_dur * 100
        tf1_df = generate_synthetic_candles(
            tf1, tf1_start, tf1_end,
            pattern="flat",
            base_price=2000.0, digits=2,
        )
        base = 2000.0
        trend_closes = []
        for i in range(len(tf1_df)):
            base += base * 0.001
            trend_closes.append(round(base, 2))
        tf1_df["close"] = trend_closes
        tf1_df["open"] = [tf1_df["close"].iloc[0]] + trend_closes[:-1]
        tf1_df["high"] = tf1_df[["open", "close"]].max(axis=1) * 1.0005
        tf1_df["low"] = tf1_df[["open", "close"]].min(axis=1) * 0.9995

    tf2 = cfg.trend_timeframe_2
    tf2_df = _resample_entry_to_higher(entry_df, entry_tf, tf2)
    if len(tf2_df) < 20:
        tf2_start = _to_dt(start)
        tf2_dur = TIMEFRAME_DURATION_MAP[tf2]
        tf2_end = tf2_start + tf2_dur * 100
        tf2_df = generate_synthetic_candles(
            tf2, tf2_start, tf2_end,
            pattern="flat",
            base_price=2000.0, digits=2,
        )
        base = 2000.0
        trend_closes = []
        for i in range(len(tf2_df)):
            base += base * 0.001
            trend_closes.append(round(base, 2))
        tf2_df["close"] = trend_closes
        tf2_df["open"] = [tf2_df["close"].iloc[0]] + trend_closes[:-1]
        tf2_df["high"] = tf2_df[["open", "close"]].max(axis=1) * 1.0005
        tf2_df["low"] = tf2_df[["open", "close"]].min(axis=1) * 0.9995

    return {
        entry_tf: entry_df,
        tf1: tf1_df,
        tf2: tf2_df,
    }
