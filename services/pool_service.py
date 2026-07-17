"""股票池管理服务：CRUD + 成员管理 + DTO。"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import PoolMember, PoolStock, StockPool, User
from services.user_service import UserDTO


# ============================================================
# DTO
# ============================================================


@dataclass
class PoolMemberDTO:
    id: int
    user_id: int
    username: str
    role: str  # owner / member
    added_at: datetime


@dataclass
class PoolDTO:
    id: int
    name: str
    type: str  # private / shared
    creator_id: int
    creator_username: str
    created_at: datetime
    member_count: int  # 仅共享池有意义；私有池始终为 0
    active_stock_count: int  # 当前在池中的股票数（status=active）


# ============================================================
# 查询
# ============================================================


def list_my_pools(session: Session, user_id: int) -> list[PoolDTO]:
    """列出当前用户可访问的所有股票池（私有池 + 共享池）。

    私有池：creator_id == user_id
    共享池：creator_id == user_id 或在 pool_members 表中存在记录
    """
    # 子查询：当前用户作为成员的池 ID 列表
    member_pool_ids = select(PoolMember.pool_id).where(PoolMember.user_id == user_id).subquery()

    # 主查询：creator_id == user_id OR pool_id IN (member_pool_ids)
    pools = (
        session.query(StockPool)
        .filter(
            (StockPool.creator_id == user_id)
            | (StockPool.id.in_(select(member_pool_ids.c.pool_id)))
        )
        .order_by(StockPool.created_at.desc())
        .all()
    )

    if not pools:
        return []

    pool_ids = [p.id for p in pools]
    creator_ids = {p.creator_id for p in pools}
    creators = {
        u.id: u.username
        for u in session.query(User).filter(User.id.in_(creator_ids)).all()
    }

    # 成员数（仅共享池）
    member_counts: dict[int, int] = {}
    rows = (
        session.query(PoolMember.pool_id, func.count(PoolMember.id))
        .filter(PoolMember.pool_id.in_(pool_ids))
        .group_by(PoolMember.pool_id)
        .all()
    )
    for pid, cnt in rows:
        member_counts[pid] = cnt

    # 池内活跃股票数
    stock_counts: dict[int, int] = {}
    rows = (
        session.query(PoolStock.pool_id, func.count(PoolStock.id))
        .filter(
            PoolStock.pool_id.in_(pool_ids),
            PoolStock.status == "active",
        )
        .group_by(PoolStock.pool_id)
        .all()
    )
    for pid, cnt in rows:
        stock_counts[pid] = cnt

    return [
        PoolDTO(
            id=p.id,
            name=p.name,
            type=p.type,
            creator_id=p.creator_id,
            creator_username=creators.get(p.creator_id, "?"),
            created_at=p.created_at,
            member_count=member_counts.get(p.id, 0),
            active_stock_count=stock_counts.get(p.id, 0),
        )
        for p in pools
    ]


def get_pool(session: Session, pool_id: int) -> Optional[StockPool]:
    return session.get(StockPool, pool_id)


def get_pool_dto(session: Session, pool_id: int) -> Optional[PoolDTO]:
    """获取单个池的 DTO（含成员数、活跃股票数）。"""
    p = session.get(StockPool, pool_id)
    if not p:
        return None
    creator = session.get(User, p.creator_id)
    member_count = (
        session.query(func.count(PoolMember.id))
        .filter(PoolMember.pool_id == pool_id)
        .scalar()
        or 0
    )
    active_stock_count = (
        session.query(func.count(PoolStock.id))
        .filter(PoolStock.pool_id == pool_id, PoolStock.status == "active")
        .scalar()
        or 0
    )
    return PoolDTO(
        id=p.id,
        name=p.name,
        type=p.type,
        creator_id=p.creator_id,
        creator_username=creator.username if creator else "?",
        created_at=p.created_at,
        member_count=member_count,
        active_stock_count=active_stock_count,
    )


def can_access_pool(session: Session, pool_id: int, user_id: int) -> bool:
    """检查用户是否有权访问该池（owner 或 member）。"""
    p = session.get(StockPool, pool_id)
    if not p:
        return False
    if p.type == "private":
        return p.creator_id == user_id
    # 共享池
    if p.creator_id == user_id:
        return True
    exists = (
        session.query(PoolMember)
        .filter(PoolMember.pool_id == pool_id, PoolMember.user_id == user_id)
        .first()
    )
    return exists is not None


def is_pool_owner(session: Session, pool_id: int, user_id: int) -> bool:
    """检查用户是否为该池的 owner。

    私有池：creator_id == user_id
    共享池：creator_id == user_id 或 member.role == 'owner'
    """
    p = session.get(StockPool, pool_id)
    if not p:
        return False
    if p.type == "private":
        return p.creator_id == user_id
    # 共享池：creator_id 即为 owner，同时检查 pool_members 表
    if p.creator_id == user_id:
        return True
    member = (
        session.query(PoolMember)
        .filter(PoolMember.pool_id == pool_id, PoolMember.user_id == user_id)
        .first()
    )
    return member is not None and member.role == "owner"


def check_duplicate_name(session: Session, user_id: int, name: str) -> bool:
    """检查用户名下是否有同名池（仅软提示，不强制）。

    返回 True 表示存在同名池。
    """
    return (
        session.query(StockPool)
        .filter(StockPool.creator_id == user_id, StockPool.name == name.strip())
        .first()
        is not None
    )


# ============================================================
# 创建 / 删除
# ============================================================


def create_pool(
    session: Session,
    name: str,
    pool_type: str,
    creator_id: int,
) -> StockPool:
    """创建股票池。

    - 若为共享池，自动在 pool_members 表插入 owner 记录
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("股票池名称不能为空")
    if len(name) > 128:
        raise ValueError("股票池名称过长（最多 128 字符）")
    if pool_type not in ("private", "shared"):
        raise ValueError("股票池类型必须为 private 或 shared")

    pool = StockPool(name=name, type=pool_type, creator_id=creator_id)
    session.add(pool)
    session.flush()

    if pool_type == "shared":
        member = PoolMember(
            pool_id=pool.id,
            user_id=creator_id,
            role="owner",
        )
        session.add(member)
        session.flush()

    return pool


def delete_pool(session: Session, pool_id: int) -> None:
    """删除股票池及其所有关联数据。

    级联删除：pool_members → analysis_images → analysis_notes → pool_stocks → stock_pools
    磁盘图片文件同步删除（避免空间泄漏）。

    注意：必须通过 ORM 对象删除（session.delete）触发 cascade；
    批量 query.delete() 不会触发 ORM 级联，会因外键约束失败。
    """
    p = session.get(StockPool, pool_id)
    if not p:
        raise ValueError("股票池不存在")

    # 1. 同步删除池内股票关联的磁盘图片文件
    from services.analysis_service import delete_images_for_pool_stock
    pool_stocks = (
        session.query(PoolStock).filter(PoolStock.pool_id == pool_id).all()
    )
    for ps in pool_stocks:
        delete_images_for_pool_stock(session, ps.id)

    # 2. 通过 ORM 删除池本身（cascade="all, delete-orphan" 会自动级联删除
    #    members 和 pool_stocks；pool_stocks 的级联会进一步删除 notes 和 images）
    session.delete(p)
    session.flush()


# ============================================================
# 成员管理
# ============================================================


def list_pool_members(session: Session, pool_id: int) -> list[PoolMemberDTO]:
    """列出共享池的所有成员（按加入时间排序，owner 在前）。"""
    rows = (
        session.query(PoolMember, User)
        .join(User, PoolMember.user_id == User.id)
        .filter(PoolMember.pool_id == pool_id)
        .order_by(PoolMember.role.desc(), PoolMember.added_at.asc())
        .all()
    )
    return [
        PoolMemberDTO(
            id=m.id,
            user_id=m.user_id,
            username=u.username,
            role=m.role,
            added_at=m.added_at,
        )
        for m, u in rows
    ]


def list_pool_member_user_ids(session: Session, pool_id: int) -> set[int]:
    """返回当前池所有成员的用户 ID 集合（用于排除已加入的用户）。"""
    rows = (
        session.query(PoolMember.user_id)
        .filter(PoolMember.pool_id == pool_id)
        .all()
    )
    return {r[0] for r in rows}


def list_candidate_users(session: Session, pool_id: int) -> list[UserDTO]:
    """列出可被邀请的用户：active 且不在当前成员列表中。

    返回 UserDTO（纯数据对象），避免 session 关闭后访问属性触发
    DetachedInstanceError。
    """
    existing = list_pool_member_user_ids(session, pool_id)
    q = session.query(User).filter(User.is_active.is_(True))
    if existing:
        q = q.filter(~User.id.in_(existing))
    users = q.order_by(User.username).all()
    return [
        UserDTO(
            id=u.id,
            username=u.username,
            role=u.role,
            is_active=u.is_active,
            created_by=u.created_by,
            created_by_username=None,
        )
        for u in users
    ]


def add_member(session: Session, pool_id: int, user_id: int) -> PoolMember:
    """添加成员到共享池（仅 owner 可调用）。

    - 自动添加为 member 角色
    """
    p = session.get(StockPool, pool_id)
    if not p:
        raise ValueError("股票池不存在")
    if p.type != "shared":
        raise ValueError("仅共享池可添加成员")

    user = session.get(User, user_id)
    if not user:
        raise ValueError("用户不存在")
    if not user.is_active:
        raise ValueError("用户已被禁用，无法添加")

    existing = (
        session.query(PoolMember)
        .filter(PoolMember.pool_id == pool_id, PoolMember.user_id == user_id)
        .first()
    )
    if existing:
        raise ValueError(f"用户 {user.username} 已是该池成员")

    member = PoolMember(
        pool_id=pool_id,
        user_id=user_id,
        role="member",
    )
    session.add(member)
    session.flush()
    return member


def remove_member(session: Session, pool_id: int, user_id: int) -> None:
    """从共享池中移除成员（仅 owner 可调用）。

    - 不能移除 owner
    """
    p = session.get(StockPool, pool_id)
    if not p:
        raise ValueError("股票池不存在")
    if p.type != "shared":
        raise ValueError("仅共享池可移除成员")

    member = (
        session.query(PoolMember)
        .filter(PoolMember.pool_id == pool_id, PoolMember.user_id == user_id)
        .first()
    )
    if not member:
        raise ValueError("该用户不是该池成员")
    if member.role == "owner":
        raise ValueError("不能移除池 owner，请先由其他管理员操作")

    session.delete(member)
    session.flush()


# ============================================================
# 飞书 Webhook
# ============================================================

FEISHU_WEBHOOK_PREFIX = "https://open.feishu.cn/open-apis/bot/v2/hook/"


def validate_feishu_webhook(url: str) -> tuple[bool, str]:
    """校验飞书 Webhook URL 格式。

    规则：以 https://open.feishu.cn/open-apis/bot/v2/hook/ 开头
          且其后有非空内容（Hook ID）。
    """
    if not url.startswith(FEISHU_WEBHOOK_PREFIX):
        return False, "Webhook 地址必须以 https://open.feishu.cn/open-apis/bot/v2/hook/ 开头"
    suffix = url[len(FEISHU_WEBHOOK_PREFIX):].strip()
    if not suffix:
        return False, "Webhook 地址缺少 Hook ID"
    return True, ""


def set_feishu_webhook(
    session: Session,
    pool_id: int,
    user_id: int,
    webhook_url: str | None,
) -> StockPool:
    """设置/清空飞书 Webhook。仅池主(creator)可操作。"""
    pool = session.get(StockPool, pool_id)
    if not pool:
        raise ValueError("股票池不存在")
    if pool.creator_id != user_id:
        raise ValueError("仅池主可设置 Webhook")

    url = (webhook_url or "").strip()
    if url:
        ok, msg = validate_feishu_webhook(url)
        if not ok:
            raise ValueError(msg)
        pool.feishu_webhook = url
    else:
        pool.feishu_webhook = None
    session.flush()
    return pool
