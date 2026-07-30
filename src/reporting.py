import os
import json
from dataclasses import asdict, is_dataclass
from typing import List, Any, Dict, Optional
import pandas as pd
from datetime import datetime, date
from src.config import Config
from src.order_executor import TradeLogEntry, EquityPoint


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _to_serializable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return str(value)
    if isinstance(value, (int, float, str, bool)):
        return value
    if is_dataclass(value):
        return {k: _to_serializable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _to_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_serializable(v) for v in value]
    return str(value)


def _trade_log_to_df(trade_log: List[TradeLogEntry]) -> pd.DataFrame:
    rows = []
    for t in trade_log:
        row = {
            "trade_id": getattr(t, "trade_id", None),
            "symbol": getattr(t, "symbol", None),
            "direction": getattr(t, "direction", None),
            "open_time": getattr(t, "open_time", None),
            "open_price": getattr(t, "open_price", None),
            "close_time": getattr(t, "close_time", None),
            "close_price": getattr(t, "close_price", None),
            "lot_size": getattr(t, "lot_size", None),
            "sl_price": getattr(t, "sl_price", None),
            "tp_price": getattr(t, "tp_price", None),
            "close_reason": getattr(t, "close_reason", None),
            "pnl": getattr(t, "pnl", None),
            "pnl_pct_equity": getattr(t, "pnl_pct_equity", None),
            "balance_after": getattr(t, "balance_after", None),
            "signal_reason": getattr(t, "signal_reason", None),
            "magic_number": getattr(t, "magic_number", None),
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    if "open_time" in df.columns and len(df) > 0:
        df = df.sort_values("open_time", kind="stable").reset_index(drop=True)
    return df


def _equity_curve_to_df(equity_curve: List[EquityPoint]) -> pd.DataFrame:
    rows = []
    for ep in equity_curve:
        rows.append({
            "time": getattr(ep, "time", None),
            "balance": getattr(ep, "balance", None),
            "equity": getattr(ep, "equity", None),
            "drawdown_pct": getattr(ep, "drawdown_pct", None),
        })
    return pd.DataFrame(rows)


def _compute_summary_metrics(trade_log: List[TradeLogEntry], equity_curve: List[EquityPoint], cfg: Config) -> Dict[str, Any]:
    closed = [t for t in trade_log if getattr(t, 'pnl', None) is not None]
    total_trades = len(closed)

    wins = [t for t in closed if t.pnl > 0]
    losses = [t for t in closed if t.pnl < 0]

    win_rate_pct = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0

    sum_wins = sum(t.pnl for t in wins) if wins else 0.0
    sum_losses = sum(t.pnl for t in losses) if losses else 0.0
    if sum_losses < 0 and abs(sum_losses) > 0:
        profit_factor = sum_wins / abs(sum_losses)
    elif total_trades > 0 and len(losses) == 0:
        profit_factor = float("inf") if sum_wins > 0 else 0.0
    else:
        profit_factor = 0.0
    if profit_factor == float("inf"):
        profit_factor = 99999999.9

    total_return_pct = 0.0
    initial_balance = getattr(cfg, "backtest_initial_balance", 1000.0)
    final_balance = initial_balance
    if len(equity_curve) > 0:
        last_ep = equity_curve[-1]
        final_equity = getattr(last_ep, "equity", initial_balance)
        final_balance = getattr(last_ep, "balance", initial_balance)
        if initial_balance > 0:
            total_return_pct = (final_balance - initial_balance) / initial_balance * 100.0

    max_drawdown_pct = 0.0
    if len(equity_curve) > 0:
        dd_values = [getattr(ep, "drawdown_pct", 0.0) or 0.0 for ep in equity_curve]
        try:
            max_drawdown_pct = float(max(dd_values))
        except Exception:
            max_drawdown_pct = 0.0

    expectancy_per_trade = (sum(t.pnl for t in closed) / total_trades) if total_trades > 0 else 0.0

    average_win = (sum(t.pnl for t in wins) / len(wins)) if wins else 0.0
    average_loss = (sum(t.pnl for t in losses) / len(losses)) if losses else 0.0

    largest_win = max((t.pnl for t in wins), default=0.0)
    largest_loss = min((t.pnl for t in losses), default=0.0)

    start_date_str = ""
    end_date_str = ""
    if len(equity_curve) > 0:
        first_t = getattr(equity_curve[0], "time", None)
        last_t = getattr(equity_curve[-1], "time", None)
        if first_t is not None:
            try:
                if isinstance(first_t, (datetime, pd.Timestamp, date)):
                    start_date_str = first_t.strftime("%Y-%m-%d") if hasattr(first_t, "strftime") else str(first_t)[:10]
                else:
                    start_date_str = str(first_t)[:10]
            except Exception:
                start_date_str = ""
        if last_t is not None:
            try:
                if isinstance(last_t, (datetime, pd.Timestamp, date)):
                    end_date_str = last_t.strftime("%Y-%m-%d") if hasattr(last_t, "strftime") else str(last_t)[:10]
                else:
                    end_date_str = str(last_t)[:10]
            except Exception:
                end_date_str = ""

    config_snapshot = _to_serializable(cfg)

    summary = {
        "config_snapshot": config_snapshot,
        "total_trades": total_trades,
        "win_rate_pct": round(win_rate_pct, 4),
        "profit_factor": round(profit_factor, 4),
        "total_return_pct": round(total_return_pct, 4),
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "expectancy_per_trade": round(expectancy_per_trade, 4),
        "average_win": round(average_win, 4),
        "average_loss": round(average_loss, 4),
        "largest_win": round(largest_win, 4),
        "largest_loss": round(largest_loss, 4),
        "start_date": start_date_str,
        "end_date": end_date_str,
    }
    return summary


def generate_report(
    trade_log: List[TradeLogEntry],
    equity_curve: List[EquityPoint],
    output_dir: str,
    cfg: Config,
) -> Dict[str, Any]:
    _ensure_dir(output_dir)

    trades_df = _trade_log_to_df(trade_log)
    trades_csv_path = os.path.join(output_dir, "trades.csv")
    trades_df.to_csv(trades_csv_path, index=False)

    eq_df = _equity_curve_to_df(equity_curve)
    eq_csv_path = os.path.join(output_dir, "equity_curve.csv")
    eq_df.to_csv(eq_csv_path, index=False)

    summary = _compute_summary_metrics(trade_log, equity_curve, cfg)
    summary_json_path = os.path.join(output_dir, "summary.json")
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=_to_serializable, ensure_ascii=False)

    return summary
