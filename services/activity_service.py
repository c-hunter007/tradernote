"""活动日志服务：记录 + 查询。"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Activity, StockPool, User


# ============================================================
# DTO
# ============================================================


@dataclass
class ActivityDTO:
    id: int
    username: str
    action: str
    description: str
    created_at: datetime


# ============================================================
# 记录
# ============================================================


def record_activity(
    session: Session,
    user_id: int,
    action: str,
    description: str,
    pool_id: int,
) -> Activity:
    """写入活动日志。"""
    act = Activity(
        user_id=user_id,
        action=action,
        description=description,
        pool_id=pool_id,
    )
    session.add(act)
    session.flush()

    # 异步飞书推送（仅已设置 webhook 的池）
    pool = session.get(StockPool, pool_id)
    if pool and pool.feishu_webhook:
        user = session.get(User, user_id)
        username_display = user.username if user else "?"
        from services.feishu_service import send_feishu_notification_async
        send_feishu_notification_async(
            webhook_url=pool.feishu_webhook,
            action=action,
            pool_name=pool.name,
            username=username_display,
            description=description,
        )

    return act


# ============================================================
# 查询
# ============================================================


def list_recent_activities(
    session: Session,
    user_id: int,
    limit: int = 20,
) -> list[ActivityDTO]:
    """查询用户可见池的近期活动。

    可见池：私有池 creator_id==user_id + 共享池成员
    管理员：全系统可见
    """
    from database.models import PoolMember, StockPool

    user_obj = session.get(User, user_id)
    if user_obj and user_obj.role == "admin":
        rows = (
            session.query(Activity, User)
            .join(User, Activity.user_id == User.id)
            .order_by(Activity.created_at.desc())
            .limit(limit)
            .all()
        )
    else:
        member_pool_ids = (
            select(PoolMember.pool_id).where(PoolMember.user_id == user_id)
        ).scalar_subquery()

        visible_pool_ids = select(StockPool.id).where(
            (StockPool.creator_id == user_id)
            | (StockPool.id.in_(member_pool_ids))
        )

        rows = (
            session.query(Activity, User)
            .join(User, Activity.user_id == User.id)
            .filter(Activity.pool_id.in_(visible_pool_ids))
            .order_by(Activity.created_at.desc())
            .limit(limit)
            .all()
        )

    return [
        ActivityDTO(
            id=a.id,
            username=u.username,
            action=a.action,
            description=a.description,
            created_at=a.created_at,
        )
        for a, u in rows
    ]
