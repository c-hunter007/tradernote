"""操作计划服务：CRUD + DTO。"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from database.models import OperationPlan, PoolStock, Stock, StockPool, User


# ============================================================
# DTO
# ============================================================


@dataclass
class PlanDTO:
    id: int
    pool_stock_id: int
    user_id: int
    username: str
    plan_date: date
    content: str
    status: str  # pending / completed
    created_at: datetime
    updated_at: datetime
    completion_note: Optional[str] = None  # 完成情况记录
    completed_at: Optional[datetime] = None  # 完成时间
    # 关联信息
    code: str = ""
    name: str = ""
    market: str = ""
    pool_name: str = ""
    pool_id: int = 0


# ============================================================
# 内部构造
# ============================================================


def _plan_to_dto(session: Session, plan: OperationPlan) -> PlanDTO:
    ps = session.get(PoolStock, plan.pool_stock_id)
    stock = session.get(Stock, ps.stock_id) if ps else None
    pool = session.get(StockPool, ps.pool_id) if ps else None
    user = session.get(User, plan.user_id)
    return PlanDTO(
        id=plan.id,
        pool_stock_id=plan.pool_stock_id,
        user_id=plan.user_id,
        username=user.username if user else "?",
        plan_date=plan.plan_date,
        content=plan.content,
        status=plan.status,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        completion_note=plan.completion_note,
        completed_at=plan.completed_at,
        code=stock.code if stock else "?",
        name=stock.name if stock else "?",
        market=stock.market if stock else "?",
        pool_name=pool.name if pool else "?",
        pool_id=ps.pool_id if ps else 0,
    )


# ============================================================
# CRUD
# ============================================================


def create_plan(
    session: Session,
    pool_stock_id: int,
    user_id: int,
    plan_date: date,
    content: str,
) -> PlanDTO:
    """创建操作计划。"""
    content = (content or "").strip()
    if not content:
        raise ValueError("计划内容不能为空")
    if not plan_date:
        raise ValueError("操作日期不能为空")

    ps = session.get(PoolStock, pool_stock_id)
    if not ps:
        raise ValueError("股票不存在")
    if ps.status != "active":
        raise ValueError("该股票已移出股票池，无法创建操作计划")

    plan = OperationPlan(
        pool_stock_id=pool_stock_id,
        user_id=user_id,
        plan_date=plan_date,
        content=content,
        status="pending",
    )
    session.add(plan)
    session.flush()

    from services.activity_service import record_activity
    record_activity(
        session, user_id, "create_plan",
        f"对 {ps.stock.code} {ps.stock.name} 创建了操作计划：{content[:40]}",
        ps.pool_id,
    )

    return _plan_to_dto(session, plan)


def update_plan(
    session: Session,
    plan_id: int,
    user_id: int,
    plan_date: date,
    content: str,
) -> PlanDTO:
    """编辑操作计划（仅本人可编辑）。"""
    plan = session.get(OperationPlan, plan_id)
    if not plan:
        raise ValueError("操作计划不存在")
    if plan.user_id != user_id:
        raise ValueError("只能编辑自己的操作计划")
    if plan.status == "completed":
        raise ValueError("已完成的操作计划不能编辑")

    content = (content or "").strip()
    if not content:
        raise ValueError("计划内容不能为空")
    if not plan_date:
        raise ValueError("操作日期不能为空")

    plan.plan_date = plan_date
    plan.content = content
    plan.updated_at = datetime.now()
    session.flush()

    return _plan_to_dto(session, plan)


def delete_plan(session: Session, plan_id: int, user_id: int) -> None:
    """删除操作计划（仅本人可删除）。"""
    plan = session.get(OperationPlan, plan_id)
    if not plan:
        raise ValueError("操作计划不存在")
    if plan.user_id != user_id:
        raise ValueError("只能删除自己的操作计划")

    ps = session.get(PoolStock, plan.pool_stock_id)
    session.delete(plan)
    session.flush()

    from services.activity_service import record_activity
    record_activity(
        session, user_id, "delete_plan",
        f"删除了对 {ps.stock.code} {ps.stock.name} 的操作计划",
        ps.pool_id,
    )


def complete_plan(session: Session, plan_id: int, user_id: int, completion_note: str = "") -> PlanDTO:
    """完成操作计划（仅本人可操作）。

    completion_note: 用户记录的完成情况（可空）。
    """
    plan = session.get(OperationPlan, plan_id)
    if not plan:
        raise ValueError("操作计划不存在")
    if plan.user_id != user_id:
        raise ValueError("只能操作自己的计划")
    if plan.status == "completed":
        raise ValueError("该计划已完成")

    plan.status = "completed"
    plan.completion_note = (completion_note or "").strip() or None
    plan.completed_at = datetime.now()
    plan.updated_at = datetime.now()
    session.flush()

    from services.activity_service import record_activity
    ps = session.get(PoolStock, plan.pool_stock_id)
    desc = f"完成了对 {ps.stock.code} {ps.stock.name} 的操作计划"
    if plan.completion_note:
        desc += f"\n💬 完成情况：{plan.completion_note}"
    record_activity(session, user_id, "complete_plan", desc, ps.pool_id)

    return _plan_to_dto(session, plan)


# ============================================================
# 查询
# ============================================================


def list_plans_by_pool_stock(
    session: Session,
    pool_stock_id: int,
) -> list[PlanDTO]:
    """列出某只股票的操作计划（按日期倒序）。"""
    plans = (
        session.query(OperationPlan)
        .filter(OperationPlan.pool_stock_id == pool_stock_id)
        .order_by(OperationPlan.plan_date.desc(), OperationPlan.created_at.desc())
        .all()
    )
    return [_plan_to_dto(session, p) for p in plans]


def list_plans_by_pool_and_date(
    session: Session,
    pool_id: int,
    plan_date: date,
) -> list[PlanDTO]:
    """列出某池中某日期的操作计划（按股票分组）。"""
    plans = (
        session.query(OperationPlan)
        .join(PoolStock, OperationPlan.pool_stock_id == PoolStock.id)
        .filter(PoolStock.pool_id == pool_id, OperationPlan.plan_date == plan_date)
        .order_by(PoolStock.stock_id, OperationPlan.created_at.desc())
        .all()
    )
    return [_plan_to_dto(session, p) for p in plans]


def list_plans_by_user(
    session: Session,
    user_id: int,
    limit: int = 100,
    offset: int = 0,
) -> list[PlanDTO]:
    """列出用户的所有操作计划（按日期倒序）。"""
    plans = (
        session.query(OperationPlan)
        .filter(OperationPlan.user_id == user_id)
        .order_by(OperationPlan.plan_date.desc(), OperationPlan.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_plan_to_dto(session, p) for p in plans]


def list_plans_for_user_pools(
    session: Session,
    user_id: int,
    plan_date: date,
) -> list[PlanDTO]:
    """列出用户可见池中某日期的所有操作计划。"""
    from database.models import PoolMember
    from sqlalchemy import select

    member_pool_ids = select(PoolMember.pool_id).where(PoolMember.user_id == user_id).subquery()
    visible_pool_ids = (
        select(StockPool.id).where(
            (StockPool.creator_id == user_id)
            | (StockPool.id.in_(select(member_pool_ids.c.pool_id)))
        )
    ).scalar_subquery()

    plans = (
        session.query(OperationPlan)
        .join(PoolStock, OperationPlan.pool_stock_id == PoolStock.id)
        .filter(
            PoolStock.pool_id.in_(visible_pool_ids),
            OperationPlan.plan_date == plan_date,
        )
        .order_by(PoolStock.stock_id, OperationPlan.created_at.desc())
        .all()
    )
    return [_plan_to_dto(session, p) for p in plans]


def get_plan(session: Session, plan_id: int) -> Optional[PlanDTO]:
    """获取单个操作计划。"""
    plan = session.get(OperationPlan, plan_id)
    if not plan:
        return None
    return _plan_to_dto(session, plan)


def get_plan_stats(session: Session, user_id: int) -> tuple[int, int, float]:
    """获取用户操作计划的统计信息。

    返回 (total, completed, rate)。
    """
    from sqlalchemy import func

    total = (
        session.query(func.count(OperationPlan.id))
        .filter(OperationPlan.user_id == user_id)
        .scalar()
        or 0
    )
    completed = (
        session.query(func.count(OperationPlan.id))
        .filter(OperationPlan.user_id == user_id, OperationPlan.status == "completed")
        .scalar()
        or 0
    )
    rate = round((completed / total * 100), 1) if total > 0 else 0.0
    return total, completed, rate