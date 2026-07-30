from enum import Enum
import pandas as pd
import numpy as np
from typing import Literal


class CrossState(Enum):
    NONE = "none"
    CROSS_UP = "cross_up"
    CROSS_DOWN = "cross_down"


def moving_average(close: pd.Series, period: int, ma_type: str) -> pd.Series:
    if ma_type.upper() == "SMA":
        return close.rolling(window=period).mean()
    elif ma_type.upper() == "EMA":
        return close.ewm(span=period, adjust=False).mean()
    else:
        raise ValueError(f"Unknown ma_type: {ma_type}")


def detect_cross(ma_low: pd.Series, ma_high: pd.Series) -> CrossState:
    if len(ma_low) < 2 or len(ma_high) < 2:
        return CrossState.NONE

    low_last2 = ma_low.iloc[-2:]
    high_last2 = ma_high.iloc[-2:]

    if low_last2.isna().any() or high_last2.isna().any():
        return CrossState.NONE

    prev_diff = ma_low.iloc[-2] - ma_high.iloc[-2]
    curr_diff = ma_low.iloc[-1] - ma_high.iloc[-1]

    if prev_diff <= 0 and curr_diff > 0:
        return CrossState.CROSS_UP
    elif prev_diff >= 0 and curr_diff < 0:
        return CrossState.CROSS_DOWN
    else:
        return CrossState.NONE


def trend_direction(ma_low: pd.Series, ma_high: pd.Series) -> Literal["BULLISH", "BEARISH", "FLAT"]:
    if len(ma_low) < 1 or len(ma_high) < 1:
        return "FLAT"
    if np.isnan(ma_low.iloc[-1]) or np.isnan(ma_high.iloc[-1]):
        return "FLAT"

    if ma_low.iloc[-1] > ma_high.iloc[-1]:
        return "BULLISH"
    elif ma_low.iloc[-1] < ma_high.iloc[-1]:
        return "BEARISH"
    else:
        return "FLAT"


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()
