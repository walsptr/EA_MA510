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

    trend_ma_pair_1_enabled = cfg.trend_ma_low_1 is not None and cfg.trend_ma_high_1 is not None
    trend_ma_pair_2_enabled = cfg.trend_ma_low_2 is not None and cfg.trend_ma_high_2 is not None
    trend_ma_enabled = trend_ma_pair_1_enabled or trend_ma_pair_2_enabled
    entry_min_bars = max(
        cfg.ma_low,
        cfg.ma_high,
        (cfg.trend_ma_low_1 or 0) if trend_ma_pair_1_enabled else 0,
        (cfg.trend_ma_high_1 or 0) if trend_ma_pair_1_enabled else 0,
        (cfg.trend_ma_low_2 or 0) if trend_ma_pair_2_enabled else 0,
        (cfg.trend_ma_high_2 or 0) if trend_ma_pair_2_enabled else 0,
    ) + 1
    trend_min_bars = max(cfg.ma_low, cfg.ma_high) + 1

    if "time" in entry_df.columns:
        last_time = entry_df.time.iloc[-1]
    else:
        last_time = entry_df.index[-1]
    last_close = entry_df.close.iloc[-1]

    if len(entry_df) < entry_min_bars or len(tf1_df) < trend_min_bars or len(tf2_df) < trend_min_bars:
        return Signal(
            direction="NONE",
            reason="insufficient history for MA warm-up",
            entry_time=last_time,
            entry_timeframe_close_price=last_close,
        )

    ma_low_entry = moving_average(entry_df.close, cfg.ma_low, cfg.ma_type)
    ma_high_entry = moving_average(entry_df.close, cfg.ma_high, cfg.ma_type)
    cross = detect_cross(ma_low_entry, ma_high_entry)

    entry_trend_1: Optional[str] = None
    entry_trend_2: Optional[str] = None
    if trend_ma_pair_1_enabled:
        tma1_low = moving_average(entry_df.close, int(cfg.trend_ma_low_1), cfg.ma_type)
        tma1_high = moving_average(entry_df.close, int(cfg.trend_ma_high_1), cfg.ma_type)
        entry_trend_1 = trend_direction(tma1_low, tma1_high)

    if trend_ma_pair_2_enabled:
        tma2_low = moving_average(entry_df.close, int(cfg.trend_ma_low_2), cfg.ma_type)
        tma2_high = moving_average(entry_df.close, int(cfg.trend_ma_high_2), cfg.ma_type)
        entry_trend_2 = trend_direction(tma2_low, tma2_high)

    tf1_ma_low = moving_average(tf1_df.close, cfg.ma_low, cfg.ma_type)
    tf1_ma_high = moving_average(tf1_df.close, cfg.ma_high, cfg.ma_type)
    t1_trend = trend_direction(tf1_ma_low, tf1_ma_high)

    tf2_ma_low = moving_average(tf2_df.close, cfg.ma_low, cfg.ma_type)
    tf2_ma_high = moving_average(tf2_df.close, cfg.ma_high, cfg.ma_type)
    t2_trend = trend_direction(tf2_ma_low, tf2_ma_high)

    if cross == CrossState.CROSS_UP and t1_trend == "BULLISH" and t2_trend == "BULLISH":
        if trend_ma_enabled and not (
            (not trend_ma_pair_1_enabled or entry_trend_1 == "BULLISH")
            and (not trend_ma_pair_2_enabled or entry_trend_2 == "BULLISH")
        ):
            return Signal(
                direction="NONE",
                reason=f"cross={cross.value} entry_trend_1={entry_trend_1} entry_trend_2={entry_trend_2} t1={t1_trend} t2={t2_trend}",
                entry_time=last_time,
                entry_timeframe_close_price=last_close,
            )
        return Signal(
            direction="BUY",
            reason=(
                "cross_up + t1=BULLISH + t2=BULLISH"
                if not trend_ma_enabled
                else (
                    "cross_up + "
                    + ("entry_trend_1=BULLISH + " if trend_ma_pair_1_enabled else "")
                    + ("entry_trend_2=BULLISH + " if trend_ma_pair_2_enabled else "")
                    + "t1=BULLISH + t2=BULLISH"
                )
            ),
            entry_time=last_time,
            entry_timeframe_close_price=last_close,
        )
    elif cross == CrossState.CROSS_DOWN and t1_trend == "BEARISH" and t2_trend == "BEARISH":
        if trend_ma_enabled and not (
            (not trend_ma_pair_1_enabled or entry_trend_1 == "BEARISH")
            and (not trend_ma_pair_2_enabled or entry_trend_2 == "BEARISH")
        ):
            return Signal(
                direction="NONE",
                reason=f"cross={cross.value} entry_trend_1={entry_trend_1} entry_trend_2={entry_trend_2} t1={t1_trend} t2={t2_trend}",
                entry_time=last_time,
                entry_timeframe_close_price=last_close,
            )
        return Signal(
            direction="SELL",
            reason=(
                "cross_down + t1=BEARISH + t2=BEARISH"
                if not trend_ma_enabled
                else (
                    "cross_down + "
                    + ("entry_trend_1=BEARISH + " if trend_ma_pair_1_enabled else "")
                    + ("entry_trend_2=BEARISH + " if trend_ma_pair_2_enabled else "")
                    + "t1=BEARISH + t2=BEARISH"
                )
            ),
            entry_time=last_time,
            entry_timeframe_close_price=last_close,
        )
    else:
        if trend_ma_enabled:
            return Signal(
                direction="NONE",
                reason=f"cross={cross.value} entry_trend_1={entry_trend_1} entry_trend_2={entry_trend_2} t1={t1_trend} t2={t2_trend}",
                entry_time=last_time,
                entry_timeframe_close_price=last_close,
            )
        return Signal(
            direction="NONE",
            reason=f"cross={cross.value} t1={t1_trend} t2={t2_trend}",
            entry_time=last_time,
            entry_timeframe_close_price=last_close,
        )
