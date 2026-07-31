from src.config import Config
from src.indicators import atr
from src.strategy import evaluate_signal, Signal as StrategySignal
from src.risk_manager import compute_trade_plan, SymbolInfo, Signal as RiskSignal, TradePlan
from src.order_executor import BacktestOrderExecutor, TradeLogEntry, EquityPoint, TradeResult
from src.data_feed import (generate_synthetic_candles, get_history, get_synthetic_for_all_timeframes)
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Tuple, List, Optional, Any
import time
import logging


_LOGGER = logging.getLogger("ea_ma510")


def _log_backtest(msg: str) -> None:
    if getattr(_LOGGER, "handlers", None):
        _LOGGER.info(msg)
    else:
        print(msg)


def _format_display_ts(cfg: Config, ts: Any) -> str:
    tz = getattr(cfg, "display_timezone", "UTC") or "UTC"
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert(tz).isoformat()


def _is_within_trading_window(cfg: Config, ts: Any) -> bool:
    start = getattr(cfg, "trading_window_start", None)
    end = getattr(cfg, "trading_window_end", None)
    if start is None or end is None:
        return True
    tz = getattr(cfg, "display_timezone", "UTC") or "UTC"
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    t = t.tz_convert(tz)
    tod = t.time()
    if start < end:
        return start <= tod < end
    return tod >= start or tod < end


def _to_utc_ts(ts: Any) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert("UTC")


def slice_up_to_time(df: pd.DataFrame, t: Any) -> pd.DataFrame:
    """
    RULES.md §8: Hanya return candle dengan close_time <= t.
    Ini adalah NO-LOOK-AHEAD GUARD.
    df harus punya kolom close_time bertipe datetime.
    """
    if df is None or len(df) == 0:
        return df
    if "close_time" not in df.columns:
        return df
    t_ts = pd.Timestamp(t)
    mask = df["close_time"] <= t_ts
    result = df[mask].copy()
    result.index = pd.RangeIndex(len(result))
    return result


def _default_symbol_info(symbol: str) -> SymbolInfo:
    """Fallback SymbolInfo jika MT5 tidak tersedia (mode synthetic)."""
    sym = symbol.upper()
    if "XAU" in sym:
        return SymbolInfo(
            point=0.01,
            trade_tick_value=1.0,
            trade_tick_size=0.01,
            volume_step=0.01,
            volume_min=0.01,
            volume_max=100.0,
            digits=2,
        )
    elif "JPY" in sym:
        return SymbolInfo(point=0.01, trade_tick_value=1.0, trade_tick_size=0.01, volume_step=0.01, volume_min=0.01, volume_max=100.0, digits=3)
    elif "EUR" in sym or "GBP" in sym or "USD" in sym or "AUD" in sym or "NZD" in sym or "CAD" in sym or "CHF" in sym:
        return SymbolInfo(point=0.00001, trade_tick_value=1.0, trade_tick_size=0.00001, volume_step=0.01, volume_min=0.01, volume_max=100.0, digits=5)
    else:
        return SymbolInfo(point=0.01, trade_tick_value=1.0, trade_tick_size=0.01, volume_step=0.01, volume_min=0.01, volume_max=100.0, digits=2)


def _try_get_mt5_symbol_info(cfg: Config) -> Optional[SymbolInfo]:
    """Coba ambil SymbolInfo via MT5 jika tersedia. Jika gagal return None."""
    try:
        from src.mt5_client import MT5Client
        client = MT5Client(cfg)
        if client.initialize():
            client.login()
            info = client.symbol_info(cfg.symbol)
            client.shutdown()
            if info:
                return SymbolInfo(**info)
    except Exception:
        pass
    return None


def run_backtest(cfg: Config, use_mt5: bool = False) -> Tuple[List[TradeLogEntry], List[EquityPoint]]:
    """
    Jalankan backtest sesuai AGENTS.md Build Order + RULES.md.
    Return tuple (trade_log_list, equity_curve_list) — list of dataclass instances.
    """

    entry_tf = cfg.entry_timeframe
    tf1 = cfg.trend_timeframe_1
    tf2 = cfg.trend_timeframe_2
    start_date = cfg.backtest_start_date or date(2025, 1, 1)
    end_date = cfg.backtest_end_date or date(2025, 1, 31)
    warmup_days = getattr(cfg, "backtest_warmup_days", 0) or 0
    fetch_start_date = start_date - timedelta(days=warmup_days)
    start_ts = pd.Timestamp(datetime(start_date.year, start_date.month, start_date.day)).tz_localize("UTC")

    symbol_info: Optional[SymbolInfo] = None

    if use_mt5:
        try:
            import MetaTrader5 as _mt5_probe  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "use_mt5=True tapi package MetaTrader5 tidak tersedia. "
                "Install MetaTrader5 (Windows-only) atau jalankan dengan use_mt5=False."
            ) from e

        from src.mt5_client import MT5Client

        client = MT5Client(cfg)
        client.initialize()
        client.login()
        try:
            entry_history = get_history(cfg.symbol, entry_tf, fetch_start_date, end_date, raise_on_error=True)
            tf1_history = get_history(cfg.symbol, tf1, fetch_start_date, end_date, raise_on_error=True)
            tf2_history = get_history(cfg.symbol, tf2, fetch_start_date, end_date, raise_on_error=True)
            info = client.symbol_info(cfg.symbol)
            if info:
                symbol_info = SymbolInfo(**info)
        finally:
            client.shutdown()
    else:
        try:
            dfs = get_synthetic_for_all_timeframes(cfg)
            entry_history = dfs[entry_tf].copy()
            tf1_history = dfs[tf1].copy()
            tf2_history = dfs[tf2].copy()
        except Exception:
            entry_history = generate_synthetic_candles(entry_tf, fetch_start_date, end_date, pattern="bull_cross_then_bear")
            tf1_history = generate_synthetic_candles(tf1, fetch_start_date, end_date, pattern="bull_cross_then_bear")
            tf2_history = generate_synthetic_candles(tf2, fetch_start_date, end_date, pattern="bull_cross_then_bear")

    print(
        f"[BACKTEST] Data siap -> {entry_tf}:{len(entry_history)} bars, "
        f"{tf1}:{len(tf1_history)} bars, {tf2}:{len(tf2_history)} bars "
        f"(sumber={'MT5 riil' if use_mt5 else 'SYNTHETIC'}). Loop dimulai..."
    )

    for df in (entry_history, tf1_history, tf2_history):
        if df is not None and len(df) > 0:
            df.index = pd.RangeIndex(len(df))

    if symbol_info is None:
        symbol_info = _default_symbol_info(cfg.symbol)

    executor = BacktestOrderExecutor(cfg.backtest_initial_balance, cfg, symbol_info)

    entry_min_bars = max(
        cfg.ma_low,
        cfg.ma_high,
        cfg.trend_ma_low_1 or 0,
        cfg.trend_ma_high_1 or 0,
        cfg.trend_ma_low_2 or 0,
        cfg.trend_ma_high_2 or 0,
    ) + 1
    warmup_bars = entry_min_bars + 5

    total_entry = len(entry_history)
    process_start = time.time()
    last_progress_pct = -1
    last_processed_bar: Optional[pd.Series] = None

    for i in range(total_entry):
        if i < warmup_bars:
            continue

        pct_done = int(i * 100 / max(total_entry, 1))
        progress_bucket = pct_done // 5
        if progress_bucket != last_progress_pct:
            last_progress_pct = progress_bucket
            elapsed = time.time() - process_start
            bars_done = i - warmup_bars
            bars_remaining = max(total_entry - i, 0)
            eta_sec = int((elapsed / max(bars_done, 1)) * bars_remaining) if bars_done > 5 else -1
            print(
                f"[BACKTEST] {pct_done:3d}% | bar {i}/{total_entry} | "
                f"elapsed {int(elapsed)}s | "
                f"{'ETA ' + str(eta_sec) + 's' if eta_sec >= 0 else 'ETA ???'}"
            )

        bar = entry_history.iloc[i]
        last_processed_bar = bar
        bar_time_utc = _to_utc_ts(bar.time)
        if bar_time_utc < start_ts:
            continue
        bar_close_time = bar.close_time
        bar_close_price = bar.close

        entry_slice = entry_history.iloc[: i + 1].copy()
        entry_slice.index = pd.RangeIndex(len(entry_slice))
        tf1_slice = slice_up_to_time(tf1_history, bar_close_time)
        tf2_slice = slice_up_to_time(tf2_history, bar_close_time)

        mark_prices = {}
        for pos in executor.get_open_positions():
            mark_prices[pos.ticket] = bar_close_price
        executor._update_equity(bar.time, mark_to_market_prices=mark_prices)

        executor.check_sl_tp_hits(bar)
        if executor.balance <= 0:
            stop_time = bar.close_time if "close_time" in bar.index else bar.time
            _log_backtest(
                f"[BACKTEST] STOP: balance <= 0 after processing closes | bar={i}/{total_entry - 1} | time={_format_display_ts(cfg, stop_time)} | balance={executor.balance:.2f}"
            )
            break

        atr_value: Optional[float] = None
        if cfg.sl_mode == "ATR" or cfg.tp_mode == "ATR":
            from src.indicators import atr as atr_fn
            if "high" in entry_slice.columns and "low" in entry_slice.columns and "close" in entry_slice.columns:
                atr_series = atr_fn(entry_slice.high, entry_slice.low, entry_slice.close, cfg.atr_period)
                atr_clean = atr_series.dropna()
                if len(atr_clean) > 0:
                    atr_value = float(atr_clean.iloc[-1])

        candles_dict = {
            entry_tf: entry_slice,
            tf1: tf1_slice,
            tf2: tf2_slice,
        }
        signal = evaluate_signal(candles_dict, cfg)

        if signal.direction != "NONE":
            if cfg.exit_on_opposite_signal:
                executor.close_opposite_positions(signal.direction, at_time=bar.time, close_price=bar_close_price)

            if not _is_within_trading_window(cfg, bar.time):
                continue

            if not executor.can_open_new_position(signal.direction, cfg.max_concurrent_positions):
                continue

            if cfg.mode == "LIVE" and cfg.max_spread_points is not None and "spread" in bar.index:
                if bar.spread > cfg.max_spread_points:
                    continue

            risk_sig = RiskSignal(
                direction=signal.direction,
                entry_timeframe_close_price=signal.entry_timeframe_close_price,
            )
            plan = compute_trade_plan(risk_sig, cfg, symbol_info, executor.equity, atr_value)

            if plan is None:
                continue

            executor.open_position(
                plan=plan,
                at_time=bar.time,
                entry_price=signal.entry_timeframe_close_price,
                signal_reason=signal.reason,
                symbol=cfg.symbol,
            )

    final_bar: Optional[pd.Series] = None
    if last_processed_bar is not None:
        final_bar = last_processed_bar
    elif total_entry > 0:
        final_bar = entry_history.iloc[-1]

    if final_bar is not None:
        last_time = final_bar.time
        last_close = final_bar.close
        tickets_map = {}
        for pos in executor.get_open_positions():
            tickets_map[pos.ticket] = last_close
        executor.close_all_positions(at_time=last_time, close_price_per_ticket=tickets_map, reason="EOD_BACKTEST")
        executor._update_equity(last_time, mark_to_market_prices={})

    total_elapsed = time.time() - process_start
    print(
        f"[BACKTEST] SELESAI dalam {int(total_elapsed)}s. "
        f"{len(executor.trade_log)} trade(s) tercatat."
    )

    return (executor.trade_log, executor.equity_curve)
