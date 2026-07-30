from dataclasses import dataclass
from typing import Literal, Any, Optional
import pandas as pd

from src.indicators import moving_average, detect_cross, trend_direction, CrossState
from src.config import Config


@dataclass(frozen=True)
class Signal:
    direction: Literal["BUY", "SELL", "NONE"]
    reason: str
    entry_time: Any
    entry_timeframe_close_price: float


def evaluate_signal(candles: dict[str, pd.DataFrame], cfg: Config) -> Signal:
    entry_df = candles[cfg.entry_timeframe]
    tf1_df = candles[cfg.trend_timeframe_1]
    tf2_df = candles[cfg.trend_timeframe_2]

    min_bars = max(cfg.ma_low, cfg.ma_high) + 1

    if "time" in entry_df.columns:
        last_time = entry_df.time.iloc[-1]
    else:
        last_time = entry_df.index[-1]
    last_close = entry_df.close.iloc[-1]

    if len(entry_df) < min_bars or len(tf1_df) < min_bars or len(tf2_df) < min_bars:
        return Signal(
            direction="NONE",
            reason="insufficient history for MA warm-up",
            entry_time=last_time,
            entry_timeframe_close_price=last_close,
        )

    ma_low_entry = moving_average(entry_df.close, cfg.ma_low, cfg.ma_type)
    ma_high_entry = moving_average(entry_df.close, cfg.ma_high, cfg.ma_type)
    cross = detect_cross(ma_low_entry, ma_high_entry)

    tf1_ma_low = moving_average(tf1_df.close, cfg.ma_low, cfg.ma_type)
    tf1_ma_high = moving_average(tf1_df.close, cfg.ma_high, cfg.ma_type)
    t1_trend = trend_direction(tf1_ma_low, tf1_ma_high)

    tf2_ma_low = moving_average(tf2_df.close, cfg.ma_low, cfg.ma_type)
    tf2_ma_high = moving_average(tf2_df.close, cfg.ma_high, cfg.ma_type)
    t2_trend = trend_direction(tf2_ma_low, tf2_ma_high)

    if cross == CrossState.CROSS_UP and t1_trend == "BULLISH" and t2_trend == "BULLISH":
        return Signal(
            direction="BUY",
            reason="cross_up + t1=BULLISH + t2=BULLISH",
            entry_time=last_time,
            entry_timeframe_close_price=last_close,
        )
    elif cross == CrossState.CROSS_DOWN and t1_trend == "BEARISH" and t2_trend == "BEARISH":
        return Signal(
            direction="SELL",
            reason="cross_down + t1=BEARISH + t2=BEARISH",
            entry_time=last_time,
            entry_timeframe_close_price=last_close,
        )
    else:
        return Signal(
            direction="NONE",
            reason=f"cross={cross.value} t1={t1_trend} t2={t2_trend}",
            entry_time=last_time,
            entry_timeframe_close_price=last_close,
        )
