"""交易记录服务：账户管理、买卖操作、统计计算。"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from database.models import (
    CompletedTrade,
    Position,
    TradingAccount,
    TradeRecord,
)
from services.akshare_service import fetch_stock_name_from_akshare


# ============================================================
# 账户管理
# ============================================================


def get_or_create_account(session: Session, user_id: int) -> TradingAccount:
    account = session.get(TradingAccount, user_id)
    if account is None:
        account = TradingAccount(
            user_id=user_id,
            available_funds=0.0,
            commission_rate=0.0003,
        )
        session.add(account)
        session.flush()
    return account


def update_account(
    session: Session,
    user_id: int,
    funds: float,
    commission_rate: float,
) -> TradingAccount:
    account = get_or_create_account(session, user_id)
    account.available_funds = funds
    account.commission_rate = commission_rate
    account.updated_at = datetime.now()
    session.flush()
    return account


def reset_account(session: Session, user_id: int) -> None:
    session.query(TradeRecord).filter(TradeRecord.user_id == user_id).delete()
    session.query(CompletedTrade).filter(CompletedTrade.user_id == user_id).delete()
    session.query(Position).filter(Position.user_id == user_id).delete()
    session.query(TradingAccount).filter(TradingAccount.user_id == user_id).delete()
    session.flush()


# ============================================================
# 持仓
# ============================================================


def get_positions(session: Session, user_id: int) -> list[Position]:
    return (
        session.query(Position)
        .filter(Position.user_id == user_id)
        .order_by(Position.stock_code)
        .all()
    )


# ============================================================
# 买入
# ============================================================


def buy_stock(
    session: Session,
    user_id: int,
    stock_code: str,
    stock_name: str,
    price: float,
    quantity: int,
    trade_date: date,
    is_initial: bool = False,
) -> TradeRecord:
    if quantity <= 0:
        raise ValueError("买入数量必须大于 0")
    if price <= 0:
        raise ValueError("买入价格必须大于 0")

    cost = price * quantity
    account = get_or_create_account(session, user_id)
    if not is_initial:
        if account.available_funds < cost:
            raise ValueError(f"可用资金不足，需要 ¥{cost:.2f}，当前 ¥{account.available_funds:.2f}")
        account.available_funds -= cost
        account.updated_at = datetime.now()

    record = TradeRecord(
        user_id=user_id,
        stock_code=stock_code,
        stock_name=stock_name,
        trade_type="buy",
        price=price,
        quantity=quantity,
        trade_date=trade_date,
        commission=0.0,
    )
    session.add(record)

    position = (
        session.query(Position)
        .filter(Position.user_id == user_id, Position.stock_code == stock_code)
        .first()
    )
    if position:
        new_qty = position.quantity + quantity
        position.avg_price = (position.quantity * position.avg_price + price * quantity) / new_qty
        position.quantity = new_qty
        position.total_buy_cost += cost
        if trade_date > position.buy_date:
            position.buy_date = trade_date
    else:
        position = Position(
            user_id=user_id,
            stock_code=stock_code,
            stock_name=stock_name,
            avg_price=price,
            quantity=quantity,
            buy_date=trade_date,
            total_buy_cost=cost,
            total_sell_revenue=0.0,
        )
        session.add(position)

    session.flush()
    return record


# ============================================================
# 卖出
# ============================================================


def sell_stock(
    session: Session,
    user_id: int,
    stock_code: str,
    price: float,
    quantity: int,
    trade_date: date,
) -> TradeRecord:
    if quantity <= 0:
        raise ValueError("卖出数量必须大于 0")
    if price <= 0:
        raise ValueError("卖出价格必须大于 0")

    position = (
        session.query(Position)
        .filter(Position.user_id == user_id, Position.stock_code == stock_code)
        .first()
    )
    if not position:
        raise ValueError(f"没有持仓 {stock_code}")
    if position.quantity < quantity:
        raise ValueError(f"持仓不足：当前 {position.quantity} 股，试图卖出 {quantity} 股")

    if trade_date <= position.buy_date:
        raise ValueError("卖出日期不能早于买入日期的次日（T+1）")

    account = get_or_create_account(session, user_id)
    commission = price * quantity * account.commission_rate
    revenue = price * quantity - commission

    account.available_funds += revenue
    account.updated_at = datetime.now()

    pnl = None
    if quantity == position.quantity:
        position.total_sell_revenue += revenue
        pnl = position.total_sell_revenue - position.total_buy_cost
        return_rate = pnl / position.total_buy_cost if position.total_buy_cost != 0 else 0.0
        completed = CompletedTrade(
            user_id=user_id,
            stock_code=stock_code,
            stock_name=position.stock_name,
            total_buy_cost=position.total_buy_cost,
            total_sell_revenue=position.total_sell_revenue,
            pnl=pnl,
            return_rate=return_rate,
            buy_start_date=position.buy_date,
            sell_end_date=trade_date,
        )
        session.add(completed)
        session.delete(position)
    else:
        position.total_sell_revenue += revenue
        remaining_qty = position.quantity - quantity
        position.avg_price = (position.quantity * position.avg_price - revenue) / remaining_qty
        position.quantity = remaining_qty

    record = TradeRecord(
        user_id=user_id,
        stock_code=stock_code,
        stock_name=position.stock_name if quantity == position.quantity else position.stock_name,
        trade_type="sell",
        price=price,
        quantity=quantity,
        trade_date=trade_date,
        commission=commission,
        pnl=pnl,
    )
    session.add(record)
    session.flush()
    return record


# ============================================================
# 股票名称查询
# ============================================================


def lookup_stock_name(code: str) -> str:
    name = fetch_stock_name_from_akshare(code)
    return name if name else ""


# ============================================================
# 交易记录查询
# ============================================================


@dataclass
class TradePage:
    records: list[TradeRecord]
    total: int
    page: int
    page_size: int
    total_pages: int


def get_trade_history(
    session: Session,
    user_id: int,
    page: int = 1,
    page_size: int = 5,
) -> TradePage:
    query = (
        session.query(TradeRecord)
        .filter(TradeRecord.user_id == user_id)
        .order_by(TradeRecord.trade_date.desc(), TradeRecord.id.desc())
    )
    total = query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size
    records = query.offset(offset).limit(page_size).all()
    return TradePage(
        records=records,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ============================================================
# 统计分析
# ============================================================


@dataclass
class TradingStats:
    total_trades: int = 0
    win_count: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_cost: float = 0.0
    return_rate: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    max_consecutive_losses: int = 0


def get_statistics(
    session: Session,
    user_id: int,
    start_date: date,
    end_date: date,
) -> TradingStats:
    trades = (
        session.query(CompletedTrade)
        .filter(
            CompletedTrade.user_id == user_id,
            CompletedTrade.sell_end_date >= start_date,
            CompletedTrade.sell_end_date <= end_date,
        )
        .order_by(CompletedTrade.sell_end_date.asc())
        .all()
    )

    stats = TradingStats()
    if not trades:
        return stats

    stats.total_trades = len(trades)
    stats.total_pnl = sum(t.pnl for t in trades)
    stats.total_cost = sum(t.total_buy_cost for t in trades)
    stats.return_rate = stats.total_pnl / stats.total_cost if stats.total_cost != 0 else 0.0
    stats.max_profit = max(t.pnl for t in trades)
    stats.max_loss = min(t.pnl for t in trades)
    stats.win_count = sum(1 for t in trades if t.pnl > 0)
    stats.win_rate = stats.win_count / stats.total_trades if stats.total_trades > 0 else 0.0

    current_streak = 0
    for t in trades:
        if t.pnl < 0:
            current_streak += 1
            stats.max_consecutive_losses = max(stats.max_consecutive_losses, current_streak)
        else:
            current_streak = 0

    return stats
