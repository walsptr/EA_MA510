from dataclasses import dataclass, field
from typing import Optional, Literal, Any, List
import pandas as pd

from src.risk_manager import TradePlan, SymbolInfo
from src.config import Config


@dataclass(frozen=True)
class Position:
    ticket: int
    symbol: str
    direction: Literal["BUY", "SELL"]
    open_time: Any
    open_price: float
    lot_size: float
    sl_price: float
    tp_price: float
    magic_number: int
    signal_reason: str
    equity_at_open: float


@dataclass(frozen=True)
class TradeResult:
    success: bool
    position_id: Optional[int]
    message: str
    close_price: Optional[float] = None
    close_time: Optional[Any] = None
    close_reason: Optional[str] = None
    pnl: Optional[float] = None


@dataclass(frozen=True)
class TradeLogEntry:
    trade_id: int
    symbol: str
    direction: Literal["BUY", "SELL"]
    open_time: Any
    open_price: float
    close_time: Optional[Any]
    close_price: Optional[float]
    lot_size: float
    sl_price: float
    tp_price: float
    close_reason: Optional[str]
    pnl: Optional[float]
    pnl_pct_equity: Optional[float]
    balance_after: Optional[float]
    signal_reason: str
    magic_number: int


@dataclass(frozen=True)
class EquityPoint:
    time: Any
    balance: float
    equity: float
    drawdown_pct: float


class BacktestOrderExecutor:
    def __init__(self, initial_balance: float, cfg: Config, symbol_info: SymbolInfo):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self._cfg = cfg
        self._symbol_info = symbol_info
        self.positions: List[Position] = []
        self.trade_log: List[TradeLogEntry] = []
        self.equity_curve: List[EquityPoint] = [
            EquityPoint(time=None, balance=initial_balance, equity=initial_balance, drawdown_pct=0.0)
        ]
        self._trade_id_counter = 0
        self._ticket_counter = 0
        self._peak_equity = initial_balance
        self._ticket_to_trade_id: dict[int, int] = {}

    def _value_per_point_per_lot(self) -> float:
        return self._symbol_info.trade_tick_value / self._symbol_info.trade_tick_size * self._symbol_info.point

    def _running_max_drawdown_pct(self, current_equity: float) -> float:
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity
        if self._peak_equity <= 0:
            return 0.0
        return (self._peak_equity - current_equity) / self._peak_equity * 100

    def _update_equity(self, current_time: Any, mark_to_market_prices: Optional[dict[int, float]] = None) -> None:
        floating_pnl = 0.0
        if mark_to_market_prices:
            for pos in self.positions:
                cp = mark_to_market_prices.get(pos.ticket)
                if cp is not None:
                    floating_pnl += self._simulate_pnl(pos, cp)
        new_equity = self.balance + floating_pnl
        self.equity = new_equity
        dd = self._running_max_drawdown_pct(new_equity)
        if len(self.equity_curve) == 0 or self.equity_curve[-1].time != current_time:
            self.equity_curve.append(
                EquityPoint(time=current_time, balance=self.balance, equity=new_equity, drawdown_pct=dd)
            )

    def _simulate_pnl(self, position: Position, close_price: float) -> float:
        point = self._symbol_info.point
        vppp = self._value_per_point_per_lot()
        if position.direction == "BUY":
            price_diff_pips = (close_price - position.open_price) / point
        else:
            price_diff_pips = (position.open_price - close_price) / point
        return price_diff_pips * position.lot_size * vppp

    def open_position(
        self,
        plan: TradePlan,
        at_time: Any,
        entry_price: float,
        signal_reason: str = "",
        symbol: str = "",
    ) -> TradeResult:
        if plan is None:
            return TradeResult(success=False, position_id=None, message="TradePlan is None")

        point = self._symbol_info.point
        spread_points = self._cfg.backtest_spread_points
        if plan.direction == "BUY":
            open_price = entry_price + (spread_points * point) / 2
        else:
            open_price = entry_price - (spread_points * point) / 2

        self._ticket_counter += 1
        ticket = self._ticket_counter
        pos = Position(
            ticket=ticket,
            symbol=symbol or self._cfg.symbol,
            direction=plan.direction,
            open_time=at_time,
            open_price=open_price,
            lot_size=plan.lot_size,
            sl_price=plan.sl_price,
            tp_price=plan.tp_price,
            magic_number=self._cfg.magic_number,
            signal_reason=signal_reason,
            equity_at_open=self.equity,
        )
        self.positions.append(pos)

        self._trade_id_counter += 1
        tid = self._trade_id_counter
        self._ticket_to_trade_id[ticket] = tid

        entry = TradeLogEntry(
            trade_id=tid,
            symbol=pos.symbol,
            direction=pos.direction,
            open_time=pos.open_time,
            open_price=pos.open_price,
            close_time=None,
            close_price=None,
            lot_size=pos.lot_size,
            sl_price=pos.sl_price,
            tp_price=pos.tp_price,
            close_reason=None,
            pnl=None,
            pnl_pct_equity=None,
            balance_after=None,
            signal_reason=pos.signal_reason,
            magic_number=pos.magic_number,
        )
        self.trade_log.append(entry)
        return TradeResult(
            success=True,
            position_id=ticket,
            message=f"Position #{ticket} {pos.direction} opened at {pos.open_price}",
        )

    def close_position(self, ticket: int, at_time: Any, close_price: float, reason: str) -> TradeResult:
        pos_idx = None
        pos = None
        for i, p in enumerate(self.positions):
            if p.ticket == ticket:
                pos_idx = i
                pos = p
                break
        if pos is None:
            return TradeResult(success=False, position_id=ticket, message=f"Ticket {ticket} not found")

        pnl = self._simulate_pnl(pos, close_price)
        self.balance += pnl

        if ticket in self._ticket_to_trade_id:
            tid = self._ticket_to_trade_id[ticket]
            for log_idx, log_entry in enumerate(self.trade_log):
                if log_entry.trade_id == tid and log_entry.close_time is None:
                    pnl_pct = (pnl / pos.equity_at_open * 100) if pos.equity_at_open != 0 else 0.0
                    new_entry = TradeLogEntry(
                        trade_id=log_entry.trade_id,
                        symbol=log_entry.symbol,
                        direction=log_entry.direction,
                        open_time=log_entry.open_time,
                        open_price=log_entry.open_price,
                        close_time=at_time,
                        close_price=close_price,
                        lot_size=log_entry.lot_size,
                        sl_price=log_entry.sl_price,
                        tp_price=log_entry.tp_price,
                        close_reason=reason,
                        pnl=pnl,
                        pnl_pct_equity=pnl_pct,
                        balance_after=self.balance,
                        signal_reason=log_entry.signal_reason,
                        magic_number=log_entry.magic_number,
                    )
                    self.trade_log[log_idx] = new_entry
                    break

        del self.positions[pos_idx]
        if ticket in self._ticket_to_trade_id:
            del self._ticket_to_trade_id[ticket]

        return TradeResult(
            success=True,
            position_id=ticket,
            message=f"Closed {ticket} with pnl={pnl:.2f}",
            close_price=close_price,
            close_time=at_time,
            close_reason=reason,
            pnl=pnl,
        )

    def check_sl_tp_hits(self, bar: pd.Series) -> List[TradeResult]:
        results: List[TradeResult] = []
        for pos in list(self.positions):
            closed = False
            if pos.direction == "BUY":
                if bar.low <= pos.sl_price:
                    res = self.close_position(
                        pos.ticket,
                        at_time=getattr(bar, "time", None),
                        close_price=pos.sl_price,
                        reason="SL_HIT",
                    )
                    results.append(res)
                    closed = True
                elif bar.high >= pos.tp_price:
                    res = self.close_position(
                        pos.ticket,
                        at_time=getattr(bar, "time", None),
                        close_price=pos.tp_price,
                        reason="TP_HIT",
                    )
                    results.append(res)
                    closed = True
            else:
                if bar.high >= pos.sl_price:
                    res = self.close_position(
                        pos.ticket,
                        at_time=getattr(bar, "time", None),
                        close_price=pos.sl_price,
                        reason="SL_HIT",
                    )
                    results.append(res)
                    closed = True
                elif bar.low <= pos.tp_price:
                    res = self.close_position(
                        pos.ticket,
                        at_time=getattr(bar, "time", None),
                        close_price=pos.tp_price,
                        reason="TP_HIT",
                    )
                    results.append(res)
                    closed = True
        return results

    def get_open_positions(self) -> List[Position]:
        return list(self.positions)

    def can_open_new_position(self, direction: str, max_concurrent: int = 1) -> bool:
        if len(self.positions) >= max_concurrent:
            return False
        for p in self.positions:
            if p.direction == direction:
                return False
        return True

    def close_opposite_positions(self, new_direction: str, at_time: Any, close_price: float) -> List[TradeResult]:
        results: List[TradeResult] = []
        opposite = "SELL" if new_direction == "BUY" else "BUY"
        for pos in list(self.positions):
            if pos.direction == opposite:
                res = self.close_position(
                    pos.ticket,
                    at_time=at_time,
                    close_price=close_price,
                    reason="OPPOSITE_SIGNAL",
                )
                results.append(res)
        return results

    def close_all_positions(
        self,
        at_time: Any,
        close_price_per_ticket: Optional[dict[int, float]] = None,
        reason: str = "EOD_BACKTEST",
    ) -> List[TradeResult]:
        results: List[TradeResult] = []
        for pos in list(self.positions):
            cp = None
            if close_price_per_ticket:
                cp = close_price_per_ticket.get(pos.ticket)
            if cp is None:
                cp = pos.open_price
            res = self.close_position(
                pos.ticket,
                at_time=at_time,
                close_price=cp,
                reason=reason,
            )
            results.append(res)
        return results
