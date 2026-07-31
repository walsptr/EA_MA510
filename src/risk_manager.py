from dataclasses import dataclass
from typing import Literal, Optional
import math

from src.config import Config


@dataclass(frozen=True)
class SymbolInfo:
    point: float
    trade_tick_value: float
    trade_tick_size: float
    volume_step: float
    volume_min: float
    volume_max: float
    digits: int


@dataclass(frozen=True)
class Signal:
    direction: Literal["BUY", "SELL", "NONE"]
    entry_timeframe_close_price: float


@dataclass(frozen=True)
class TradePlan:
    direction: Literal["BUY", "SELL"]
    lot_size: float
    sl_price: float
    tp_price: float


def round_to_step(value: float, step: float, min_val: float, max_val: float) -> float:
    if step <= 0:
        clamped = max(min_val, min(max_val, value))
        return clamped
    steps = round(value / step)
    rounded = steps * step
    clamped = max(min_val, min(max_val, rounded))
    return clamped


def compute_trade_plan(
    signal: Signal,
    cfg: Config,
    symbol_info: SymbolInfo,
    account_equity: float,
    atr_value: Optional[float] = None,
) -> Optional[TradePlan]:
    if signal.direction == "NONE":
        return None

    point = symbol_info.point
    entry_price = signal.entry_timeframe_close_price
    value_per_point_per_lot = (
        symbol_info.trade_tick_value / symbol_info.trade_tick_size * point
    )

    spread_points = cfg.backtest_spread_points if cfg.mode == "BACKTEST" else 0.0
    if signal.direction == "BUY":
        fill_price = entry_price + (spread_points * point) / 2
    else:
        fill_price = entry_price - (spread_points * point) / 2

    # ========== LANGKAH 1: Tentukan preliminary_sl_distance ==========
    if cfg.sl_mode == "ATR":
        if atr_value is None:
            return None
        preliminary_sl_distance = cfg.sl_atr_multiplier * atr_value
    elif cfg.sl_mode == "FIXED":
        preliminary_sl_distance = cfg.sl_points * point
    elif cfg.sl_mode == "DOLLAR":
        if cfg.sizing_mode == "FIXED_LOT":
            preliminary_lot = cfg.fixed_lot_size
            sl_distance_in_points = cfg.sl_dollar / (
                preliminary_lot * value_per_point_per_lot
            )
            preliminary_sl_distance = sl_distance_in_points * point
        else:
            risk_amount = cfg.sl_dollar
            preliminary_lot = risk_amount / value_per_point_per_lot
            sl_distance_in_points = cfg.sl_dollar / (
                preliminary_lot * value_per_point_per_lot
            )
            preliminary_sl_distance = sl_distance_in_points * point
    else:
        return None

    # ========== LANGKAH 1 (TP): Tentukan preliminary_tp_distance ==========
    if cfg.tp_mode == "ATR":
        if atr_value is None:
            return None
        preliminary_tp_distance = cfg.tp_atr_multiplier * atr_value
    elif cfg.tp_mode == "FIXED":
        preliminary_tp_distance = cfg.tp_points * point
    elif cfg.tp_mode == "DOLLAR":
        if cfg.sizing_mode == "FIXED_LOT":
            preliminary_lot_tp = cfg.fixed_lot_size
            tp_distance_in_points = cfg.tp_dollar / (
                preliminary_lot_tp * value_per_point_per_lot
            )
            preliminary_tp_distance = tp_distance_in_points * point
        else:
            preliminary_lot_tp = cfg.tp_dollar / value_per_point_per_lot
            tp_distance_in_points = cfg.tp_dollar / (
                preliminary_lot_tp * value_per_point_per_lot
            )
            preliminary_tp_distance = tp_distance_in_points * point
    else:
        return None

    # ========== LANGKAH 2: Hitung preliminary_lot dari preliminary_sl_distance ==========
    if cfg.sizing_mode == "FIXED_LOT":
        lot = cfg.fixed_lot_size
    else:
        if cfg.sl_mode == "DOLLAR":
            risk_amount = cfg.sl_dollar
        else:
            risk_amount = account_equity * (cfg.risk_percent_per_trade / 100)
        sl_distance_in_points = preliminary_sl_distance / point
        denominator = sl_distance_in_points * value_per_point_per_lot
        if denominator <= 0:
            return None
        lot = risk_amount / denominator

    # ========== LANGKAH g: round & clamp lot ==========
    lot = round_to_step(
        lot,
        symbol_info.volume_step,
        symbol_info.volume_min,
        symbol_info.volume_max,
    )

    # ========== LANGKAH h: lot < min -> None ==========
    if lot < symbol_info.volume_min:
        return None

    # ========== LANGKAH i: FINAL lot diketahui, hitung ULANG SL/TP jika DOLLAR ==========
    sl_distance = preliminary_sl_distance
    if cfg.sl_mode == "DOLLAR":
        sl_distance_in_points_final = cfg.sl_dollar / (
            lot * value_per_point_per_lot
        )
        sl_distance = sl_distance_in_points_final * point

    tp_distance = preliminary_tp_distance
    if cfg.tp_mode == "DOLLAR":
        tp_distance_in_points_final = cfg.tp_dollar / (
            lot * value_per_point_per_lot
        )
        tp_distance = tp_distance_in_points_final * point

    # ========== Defensive: sl_distance < point -> None ==========
    if sl_distance < point:
        return None

    # ========== LANGKAH e: BUY/SELL sign untuk sl_price & tp_price ==========
    if signal.direction == "BUY":
        sl_price = fill_price - sl_distance
        tp_price = fill_price + tp_distance
    else:
        sl_price = fill_price + sl_distance
        tp_price = fill_price - tp_distance

    # ========== LANGKAH j: Round sl_price & tp_price ke digits ==========
    digits = symbol_info.digits
    sl_price = round(sl_price, digits)
    tp_price = round(tp_price, digits)

    # ========== Final defensive check (SELL: tp < entry < sl, BUY: sl < entry < tp) ==========
    if signal.direction == "BUY":
        if sl_price >= fill_price or tp_price <= fill_price:
            return None
    else:
        if sl_price <= fill_price or tp_price >= fill_price:
            return None

    return TradePlan(
        direction=signal.direction,
        lot_size=lot,
        sl_price=sl_price,
        tp_price=tp_price,
    )
