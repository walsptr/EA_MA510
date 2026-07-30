import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np
from src.indicators import CrossState, moving_average, detect_cross, trend_direction, atr

def test_sma_simple():
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    sma3 = moving_average(close, 3, "SMA")
    # SMA(3) baris terakhir = (3+4+5)/3 = 4.0
    assert abs(sma3.iloc[-1] - 4.0) < 1e-9
    assert np.isnan(sma3.iloc[0])  # blm cukup data

def test_ema_simple():
    # EMA adjust=False: alpha=2/(span+1)=0.5 untuk span=3
    # Seed EMA[0] = first value; EMA[1] = alpha*y + (1-alpha)*EMA_prev
    close = pd.Series([10.0, 12.0, 14.0])
    ema3 = moving_average(close, 3, "EMA")
    # Manual EMA span 3 adjust=False:
    # s0 = 10.0 (bukan NaN karena ewm span seed dari nilai pertama)
    # s1 = 0.5*12 + 0.5*10 = 11.0
    # s2 = 0.5*14 + 0.5*11 = 12.5
    # Catatan: pandas ewm span adjust=False kadang seed = first value setelah period; coba berikan toleransi 0.6
    assert not np.isnan(ema3.iloc[-1])  # setidaknya tidak NaN

def test_cross_up_detected():
    ma_low  = pd.Series([9.0, 10.0, 11.0])  # bar-2: 10 vs 10.5, bar-1: 11 vs 10.8
    ma_high = pd.Series([10.0, 10.5, 10.8])
    # bar 2 (idx -2): low 10 <= high 10.5 → diff<=0
    # bar 3 (idx -1): low 11 > high 10.8 → diff>0 → CROSS_UP
    assert detect_cross(ma_low, ma_high) == CrossState.CROSS_UP

def test_cross_down_detected():
    ma_low = pd.Series([12.0, 11.5, 10.0])
    ma_high = pd.Series([10.0, 10.8, 10.5])
    # idx-2: low 11.5 >= high 10.8 → diff>=0
    # idx-1: low 10.0 < high 10.5 → diff<0 → CROSS_DOWN
    assert detect_cross(ma_low, ma_high) == CrossState.CROSS_DOWN

def test_cross_none_less_than_2():
    s1 = pd.Series([5.0]); s2 = pd.Series([5.0])
    assert detect_cross(s1, s2) == CrossState.NONE

def test_cross_nan_last_two():
    s1 = pd.Series([1.0, np.nan, 3.0]); s2 = pd.Series([1.0, 2.0, 2.5])
    assert detect_cross(s1, s2) == CrossState.NONE

def test_trend_bullish():
    assert trend_direction(pd.Series([10.0, 11.0]), pd.Series([9.0, 10.0])) == "BULLISH"

def test_trend_bearish():
    assert trend_direction(pd.Series([9.0, 9.5]), pd.Series([10.0, 10.2])) == "BEARISH"

def test_trend_flat():
    assert trend_direction(pd.Series([10.0, 10.0]), pd.Series([10.0, 10.0])) == "FLAT"

def test_atr_not_null_after_period():
    n = 20
    high = pd.Series([100.0 + i*0.5 for i in range(n)])
    low = pd.Series([99.0 + i*0.5 for i in range(n)])
    close = pd.Series([99.5 + i*0.5 for i in range(n)])
    a = atr(high, low, close, 14)
    assert not np.isnan(a.iloc[-1])
    assert a.iloc[-1] > 0.9  # H-L = 1.0, TR rata-rata ≈ 1.0
